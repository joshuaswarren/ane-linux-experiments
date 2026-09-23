/*
 * vk-submit-lat: per-round-trip Vulkan submit+wait latency breakdown.
 *
 * Measures, on one compute queue with one timeline semaphore (the honeykrisp
 * pattern used by the Parakeet TDT loop):
 *   clock      - clock_gettime() overhead (sanity)
 *   noopsleep  - blocking wait on an already-signaled point
 *   submitonly - back-to-back vkQueueSubmit, single wait at the end
 *   rtsleep    - submit; blocking timeline wait            (TDT pattern)
 *   rtpoll     - submit; busy-poll vkWaitSemaphores(timeout=0)
 *   rthybrid   - submit; busy-poll up to --poll-us, then block
 *   emptyrt    - empty submit (syncobj-only) + blocking wait
 *   nanowake   - clock_nanosleep(200us) actual wake delta (scheduler ref)
 *
 * Usage: vk-submit-lat [--n N] [--poll-us US] [--cpu N] [--samples PREFIX]
 * Prints one JSON line per mode.
 * Build: cc -O2 -o vk-submit-lat vk-submit-lat.c -lvulkan -lpthread
 */
#define _GNU_SOURCE
#include <inttypes.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include <vulkan/vulkan.h>

#include "lat_spv.h"

#define die(...) do { fprintf(stderr, __VA_ARGS__); exit(1); } while (0)

static uint64_t
now_ns(void)
{
   struct timespec ts;
   clock_gettime(CLOCK_MONOTONIC, &ts);
   return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static int
cmp_u64(const void *a, const void *b)
{
   uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
   return x < y ? -1 : (x > y ? 1 : 0);
}

static void
print_summary(const char *mode, uint64_t *samples, uint32_t n,
              const uint64_t *submit_samples)
{
   uint64_t *v = malloc(sizeof(uint64_t) * n);
   memcpy(v, samples, sizeof(uint64_t) * n);
   qsort(v, n, sizeof(*v), cmp_u64);
   uint64_t sum = 0;
   for (uint32_t i = 0; i < n; i++)
      sum += samples[i];
   printf("{\"mode\": \"%s\", \"n\": %u, \"min_us\": %" PRIu64
          ", \"p50_us\": %" PRIu64 ", \"p90_us\": %" PRIu64
          ", \"p99_us\": %" PRIu64 ", \"mean_us\": %.2f",
          mode, n, v[0], v[n / 2], v[(uint32_t)(n * 0.90)],
          v[(uint32_t)(n * 0.99)], (double)sum / 1000.0 / n);
   if (submit_samples) {
      uint64_t ssum = 0;
      for (uint32_t i = 0; i < n; i++)
         ssum += submit_samples[i];
      printf(", \"mean_submit_us\": %.2f", (double)ssum / 1000.0 / n);
   }
   printf("}\n");
   free(v);
   fflush(stdout);
}

static void
pin_cpu(int cpu)
{
   cpu_set_t set;
   CPU_ZERO(&set);
   CPU_SET(cpu, &set);
   if (pthread_setaffinity_np(pthread_self(), sizeof(set), &set))
      die("pthread_setaffinity_np(%d) failed\n", cpu);
}

struct ctx {
   VkInstance instance;
   VkPhysicalDevice pdev;
   VkDevice dev;
   VkQueue queue;
   uint32_t qf;
   VkPipeline pipeline;
   VkPipelineLayout playout;
   VkBuffer buf;
   VkDeviceMemory mem;
   uint64_t buf_addr;
   VkSemaphore timeline;
   VkCommandPool cpool;
   VkCommandBuffer cb;
   uint64_t point;
};

static void
ctx_create(struct ctx *c)
{
   *c = (struct ctx){0};

   VkApplicationInfo app = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
                            .apiVersion = VK_API_VERSION_1_2};
   VkInstanceCreateInfo ici = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
                               .pApplicationInfo = &app};
   if (vkCreateInstance(&ici, NULL, &c->instance) != VK_SUCCESS)
      die("vkCreateInstance failed\n");

   uint32_t npd = 8;
   VkPhysicalDevice pds[8];
   if (vkEnumeratePhysicalDevices(c->instance, &npd, pds) != VK_SUCCESS ||
       npd == 0)
      die("no physical devices\n");
   c->pdev = pds[0];

   uint32_t qf_count = 0;
   vkGetPhysicalDeviceQueueFamilyProperties(c->pdev, &qf_count, NULL);
   VkQueueFamilyProperties qfp[16];
   if (qf_count > 16)
      qf_count = 16;
   vkGetPhysicalDeviceQueueFamilyProperties(c->pdev, &qf_count, qfp);
   for (uint32_t i = 0; i < qf_count; i++) {
      if (qfp[i].queueFlags & VK_QUEUE_COMPUTE_BIT) {
         c->qf = i;
         break;
      }
   }

   float prio = 1.0f;
   VkDeviceQueueCreateInfo qci = {
      .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
      .queueFamilyIndex = c->qf,
      .queueCount = 1,
      .pQueuePriorities = &prio,
   };
   VkPhysicalDeviceVulkan12Features f12 = {
      .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES,
      .timelineSemaphore = VK_TRUE,
      .bufferDeviceAddress = VK_TRUE,
   };
   VkDeviceCreateInfo dci = {
      .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
      .pNext = &f12,
      .queueCreateInfoCount = 1,
      .pQueueCreateInfos = &qci,
   };
   if (vkCreateDevice(c->pdev, &dci, NULL, &c->dev) != VK_SUCCESS)
      die("vkCreateDevice failed\n");
   vkGetDeviceQueue(c->dev, c->qf, 0, &c->queue);

   VkShaderModuleCreateInfo smci = {
      .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
      .codeSize = sizeof(lat_spv),
      .pCode = lat_spv,
   };
   VkShaderModule sm;
   if (vkCreateShaderModule(c->dev, &smci, NULL, &sm) != VK_SUCCESS)
      die("vkCreateShaderModule failed\n");
   VkPushConstantRange pcr = {.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT,
                              .size = 8, .offset = 0};
   VkPipelineLayoutCreateInfo plci = {
      .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
      .pushConstantRangeCount = 1,
      .pPushConstantRanges = &pcr,
   };
   if (vkCreatePipelineLayout(c->dev, &plci, NULL, &c->playout) != VK_SUCCESS)
      die("vkCreatePipelineLayout failed\n");
   VkComputePipelineCreateInfo cpci = {
      .sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
      .stage = {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                .stage = VK_SHADER_STAGE_COMPUTE_BIT,
                .module = sm,
                .pName = "main"},
      .layout = c->playout,
   };
   if (vkCreateComputePipelines(c->dev, VK_NULL_HANDLE, 1, &cpci, NULL,
                                &c->pipeline) != VK_SUCCESS)
      die("vkCreateComputePipelines failed\n");
   vkDestroyShaderModule(c->dev, sm, NULL);

   VkBufferCreateInfo bci = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
                             .size = 4096,
                             .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT};
   if (vkCreateBuffer(c->dev, &bci, NULL, &c->buf) != VK_SUCCESS)
      die("vkCreateBuffer failed\n");
   VkMemoryRequirements mr;
   vkGetBufferMemoryRequirements(c->dev, c->buf, &mr);
   VkPhysicalDeviceMemoryProperties mp;
   vkGetPhysicalDeviceMemoryProperties(c->pdev, &mp);
   int32_t mi = -1;
   for (uint32_t i = 0; i < mp.memoryTypeCount; i++) {
      if ((mr.memoryTypeBits & (1u << i)) &&
          (mp.memoryTypes[i].propertyFlags & VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)) {
         mi = i;
         break;
      }
   }
   if (mi < 0)
      die("no device local memory type\n");
   VkMemoryAllocateInfo mai = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
                               .allocationSize = mr.size,
                               .memoryTypeIndex = (uint32_t)mi};
   if (vkAllocateMemory(c->dev, &mai, NULL, &c->mem) != VK_SUCCESS)
      die("vkAllocateMemory failed\n");
   vkBindBufferMemory(c->dev, c->buf, c->mem, 0);
   VkBufferDeviceAddressInfo bdai = {
      .sType = VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO, .buffer = c->buf};
   c->buf_addr = vkGetBufferDeviceAddress(c->dev, &bdai);

   VkSemaphoreTypeCreateInfo stci = {
      .sType = VK_STRUCTURE_TYPE_SEMAPHORE_TYPE_CREATE_INFO,
      .semaphoreType = VK_SEMAPHORE_TYPE_TIMELINE,
      .initialValue = 0};
   VkSemaphoreCreateInfo sci = {.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,
                                .pNext = &stci};
   if (vkCreateSemaphore(c->dev, &sci, NULL, &c->timeline) != VK_SUCCESS)
      die("vkCreateSemaphore failed\n");

   VkCommandPoolCreateInfo cpi = {
      .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
      .queueFamilyIndex = c->qf};
   if (vkCreateCommandPool(c->dev, &cpi, NULL, &c->cpool) != VK_SUCCESS)
      die("command pool\n");
   VkCommandBufferAllocateInfo cbai = {
      .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
      .commandPool = c->cpool,
      .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
      .commandBufferCount = 1};
   if (vkAllocateCommandBuffers(c->dev, &cbai, &c->cb) != VK_SUCCESS)
      die("command buffer\n");

   VkPhysicalDeviceProperties2 p2 = {
      .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2};
   VkPhysicalDeviceDriverProperties dp = {
      .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
   p2.pNext = &dp;
   vkGetPhysicalDeviceProperties2(c->pdev, &p2);
   printf("{\"device\": \"%s\", \"driver\": \"%s\", \"driver_id\": %d, "
          "\"driver_version\": \"%s\", \"api\": \"%d.%d\"}\n",
          p2.properties.deviceName, dp.driverName, dp.driverID,
          dp.driverInfo,
          VK_VERSION_MAJOR(p2.properties.apiVersion),
          VK_VERSION_MINOR(p2.properties.apiVersion));
   fflush(stdout);
}

/* One submit: record + dispatch + signal timeline point. */
static uint64_t
submit_signal(struct ctx *c, uint64_t value)
{
   uint64_t t0 = now_ns();

   vkResetCommandBuffer(c->cb, 0);
   VkCommandBufferBeginInfo bi = {
      .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
   if (vkBeginCommandBuffer(c->cb, &bi) != VK_SUCCESS)
      die("begin failed\n");
   vkCmdBindPipeline(c->cb, VK_PIPELINE_BIND_POINT_COMPUTE, c->pipeline);
   uint32_t pc[2] = {(uint32_t)c->buf_addr, (uint32_t)(c->buf_addr >> 32)};
   vkCmdPushConstants(c->cb, c->playout, VK_SHADER_STAGE_COMPUTE_BIT, 0, 8, pc);
   vkCmdDispatch(c->cb, 1, 1, 1);
   if (vkEndCommandBuffer(c->cb) != VK_SUCCESS)
      die("end failed\n");

   VkTimelineSemaphoreSubmitInfo tsi = {
      .sType = VK_STRUCTURE_TYPE_TIMELINE_SEMAPHORE_SUBMIT_INFO,
      .signalSemaphoreValueCount = 1,
      .pSignalSemaphoreValues = &value};
   VkSubmitInfo si = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO,
                      .pNext = &tsi,
                      .commandBufferCount = 1,
                      .pCommandBuffers = &c->cb,
                      .signalSemaphoreCount = 1,
                      .pSignalSemaphores = &c->timeline};
   if (vkQueueSubmit(c->queue, 1, &si, VK_NULL_HANDLE) != VK_SUCCESS)
      die("vkQueueSubmit failed\n");
   c->point = value;
   return now_ns() - t0;
}

static void
submit_empty_signal(struct ctx *c, uint64_t value)
{
   VkTimelineSemaphoreSubmitInfo tsi = {
      .sType = VK_STRUCTURE_TYPE_TIMELINE_SEMAPHORE_SUBMIT_INFO,
      .signalSemaphoreValueCount = 1,
      .pSignalSemaphoreValues = &value};
   VkSubmitInfo si = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO,
                      .pNext = &tsi,
                      .signalSemaphoreCount = 1,
                      .pSignalSemaphores = &c->timeline};
   if (vkQueueSubmit(c->queue, 1, &si, VK_NULL_HANDLE) != VK_SUCCESS)
      die("empty vkQueueSubmit failed\n");
   c->point = value;
}

static void
wait_blocking(struct ctx *c, uint64_t value)
{
   VkSemaphoreWaitInfo wi = {.sType = VK_STRUCTURE_TYPE_SEMAPHORE_WAIT_INFO,
                             .semaphoreCount = 1,
                             .pSemaphores = &c->timeline,
                             .pValues = &value};
   if (vkWaitSemaphores(c->dev, &wi, UINT64_MAX) != VK_SUCCESS)
      die("vkWaitSemaphores failed\n");
}

/* Busy-poll with timeout-0 waits; falls back to a blocking wait once the
 * poll budget is exhausted. budget_ns == 0 polls forever. */
static void
wait_poll(struct ctx *c, uint64_t value, uint64_t budget_ns)
{
   VkSemaphoreWaitInfo wi = {.sType = VK_STRUCTURE_TYPE_SEMAPHORE_WAIT_INFO,
                             .semaphoreCount = 1,
                             .pSemaphores = &c->timeline,
                             .pValues = &value};
   uint64_t deadline = budget_ns ? now_ns() + budget_ns : UINT64_MAX;
   for (;;) {
      if (vkWaitSemaphores(c->dev, &wi, 0) == VK_SUCCESS)
         return;
      if (budget_ns && now_ns() >= deadline) {
         wait_blocking(c, value);
         return;
      }
   }
}

static void
dump_samples(const char *path, const uint64_t *samples, uint32_t n)
{
   FILE *f = fopen(path, "w");
   if (!f)
      return;
   for (uint32_t i = 0; i < n; i++)
      fprintf(f, "%" PRIu64 "\n", samples[i]);
   fclose(f);
}

int
main(int argc, char **argv)
{
   uint32_t n = 2000, n_empty = 1000;
   uint64_t poll_us = 300;
   int cpu = -1;
   const char *samples_prefix = NULL;

   for (int i = 1; i < argc; i++) {
      if (!strcmp(argv[i], "--n"))
         n = strtoul(argv[++i], NULL, 0);
      else if (!strcmp(argv[i], "--poll-us"))
         poll_us = strtoull(argv[++i], NULL, 0);
      else if (!strcmp(argv[i], "--cpu"))
         cpu = atoi(argv[++i]);
      else if (!strcmp(argv[i], "--samples"))
         samples_prefix = argv[++i];
      else
         die("unknown arg %s\n", argv[i]);
   }

   if (cpu < 0)
      cpu = (int)sysconf(_SC_NPROCESSORS_CONF) - 1;
   pin_cpu(cpu);

   static struct ctx ctx_storage;
   struct ctx *c = &ctx_storage;
   ctx_create(c);

   uint32_t max_n = n > n_empty ? n : n_empty;
   uint64_t *samples = malloc(sizeof(uint64_t) * max_n);
   uint64_t *sub_times = malloc(sizeof(uint64_t) * max_n);
   uint64_t *keep_sleep = malloc(sizeof(uint64_t) * n);
   uint64_t *keep_poll = malloc(sizeof(uint64_t) * n);
   if (!samples || !sub_times || !keep_sleep || !keep_poll)
      die("oom\n");

   /* Warmup */
   for (uint32_t i = 1; i <= 64; i++)
      submit_signal(c, i);
   wait_blocking(c, 64);

   /* clock overhead */
   {
      uint64_t t0 = now_ns();
      for (uint32_t i = 0; i < 1000; i++)
         (void)now_ns();
      printf("{\"mode\": \"clock\", \"ns_per_call\": %" PRIu64 "}\n",
             (now_ns() - t0) / 1000);
   }

   /* noopsleep: blocking wait on already-signaled point */
   {
      for (uint32_t i = 0; i < n; i++) {
         uint64_t v = c->point;
         uint64_t t0 = now_ns();
         wait_blocking(c, v);
         samples[i] = now_ns() - t0;
      }
      print_summary("noopsleep", samples, n, NULL);
   }

   /* submitonly: back-to-back submits, one wait at the end */
   {
      uint64_t base = c->point;
      uint64_t t0 = now_ns();
      for (uint32_t i = 1; i <= n; i++)
         submit_signal(c, base + i);
      uint64_t t1 = now_ns();
      wait_blocking(c, base + n);
      uint64_t t2 = now_ns();
      printf("{\"mode\": \"submitonly\", \"n\": %u, \"per_submit_us\": %.2f, "
             "\"drain_us\": %.2f}\n",
             n, (double)(t1 - t0) / 1000.0 / n, (double)(t2 - t1) / 1000.0);
      c->point = base + n;
   }

   /* rtsleep: submit + blocking wait (the TDT pattern) */
   {
      uint64_t base = c->point;
      for (uint32_t i = 1; i <= n; i++) {
         uint64_t t0 = now_ns();
         sub_times[i - 1] = submit_signal(c, base + i);
         wait_blocking(c, base + i);
         samples[i - 1] = now_ns() - t0;
      }
      c->point = base + n;
      memcpy(keep_sleep, samples, sizeof(uint64_t) * n);
      print_summary("rtsleep", samples, n, sub_times);
   }

   /* rtpoll: submit + busy poll with timeout-0 waits */
   {
      uint64_t base = c->point;
      for (uint32_t i = 1; i <= n; i++) {
         uint64_t t0 = now_ns();
         submit_signal(c, base + i);
         wait_poll(c, base + i, 0);
         samples[i - 1] = now_ns() - t0;
      }
      c->point = base + n;
      memcpy(keep_poll, samples, sizeof(uint64_t) * n);
      print_summary("rtpoll", samples, n, NULL);
   }

   /* rthybrid: poll for poll_us then block */
   {
      uint64_t base = c->point;
      uint64_t budget = poll_us * 1000;
      for (uint32_t i = 1; i <= n; i++) {
         uint64_t t0 = now_ns();
         submit_signal(c, base + i);
         wait_poll(c, base + i, budget);
         samples[i - 1] = now_ns() - t0;
      }
      c->point = base + n;
      print_summary("rthybrid", samples, n, NULL);
   }

   /* emptyrt: syncobj-only submit + blocking wait */
   {
      uint64_t base = c->point;
      for (uint32_t i = 1; i <= n_empty; i++) {
         uint64_t t0 = now_ns();
         submit_empty_signal(c, base + i);
         wait_blocking(c, base + i);
         samples[i - 1] = now_ns() - t0;
      }
      c->point = base + n_empty;
      print_summary("emptyrt", samples, n_empty, NULL);
   }

   /* nanowake: scheduler wake reference */
   {
      for (uint32_t i = 0; i < 500; i++) {
         struct timespec ts = {.tv_nsec = 200000};
         uint64_t t0 = now_ns();
         clock_nanosleep(CLOCK_MONOTONIC, 0, &ts, NULL);
         samples[i] = now_ns() - t0;
      }
      print_summary("nanowake200us", samples, 500, NULL);
   }

   if (samples_prefix) {
      char path[512];
      snprintf(path, sizeof(path), "%s.rtsleep", samples_prefix);
      dump_samples(path, keep_sleep, n);
      snprintf(path, sizeof(path), "%s.rtpoll", samples_prefix);
      dump_samples(path, keep_poll, n);
   }

   printf("{\"done\": true}\n");
   return 0;
}
