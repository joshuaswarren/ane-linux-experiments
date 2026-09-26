// vk_lat: Vulkan submission/sync latency chain microbench (honeykrisp/T8103).
// Modes:
//   single      one dispatch (+barrier) per submit, blocking vkWaitSemaphores
//   poll        same, busy-poll GetSemaphoreCounterValue
//   spinblock   same, spin ~200us then block
//   batch N     N dispatches (full barrier after each) in ONE submit, blocking
//   batchnb N   N dispatches, NO barriers, one submit
// Segments per iteration (ns): record submit gpu_start gpu_exec wakeup
// GPU timestamps made absolute via calibration submit vs CLOCK_MONOTONIC.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>
#include <sched.h>
#include <vulkan/vulkan.h>

#define CK(x) do { VkResult _r = (x); if (_r) { fprintf(stderr, "vk err %d at %d\n", _r, __LINE__); exit(1); } } while (0)

static struct {
    VkInstance inst; VkPhysicalDevice pd; VkDevice dev; VkQueue queue;
    float ts_period;
    VkBuffer buf; VkDeviceMemory mem;
    VkDescriptorSetLayout dsl; VkDescriptorPool dpool; VkDescriptorSet dset;
    VkPipelineLayout playout; VkPipeline pipe;
    VkCommandPool cpool; VkCommandBuffer cb; VkQueryPool qpool; VkSemaphore sem;
} C;

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}
static int cmp_u64(const void *a, const void *b) {
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return x < y ? -1 : x > y;
}
static uint64_t pctl(uint64_t *v, int n, double p) {
    qsort(v, n, sizeof(uint64_t), cmp_u64);
    return v[(int)(p * (n - 1))];
}
static double ms(uint64_t ns) { return (double)ns / 1e6; }

static void barrier_cmd(VkCommandBuffer cb) {
    VkMemoryBarrier mb = {.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER};
    mb.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
    mb.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
    vkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                         VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, 0,
                         1, &mb, 0, NULL, 0, NULL);
}

static uint32_t rec_iter(VkCommandBuffer cb, int it, const char *mode, int bcount) {
    int bar = strncmp(mode, "batchnb", 7) != 0;
    uint32_t q = 2 * (uint32_t)it;
    if (!strncmp(mode, "batch", 5)) {
        for (int i = 0; i < bcount; i++) {
            if (i == 0)
                vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, C.qpool, q);
            vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, C.pipe);
            vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, C.playout,
                                    0, 1, &C.dset, 0, NULL);
            vkCmdDispatch(cb, 1, 1, 1);
            if (bar) barrier_cmd(cb);
            if (i == bcount - 1)
                vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, C.qpool, q + 1);
        }
    } else {
        vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, C.qpool, q);
        vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, C.pipe);
        vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, C.playout,
                                0, 1, &C.dset, 0, NULL);
        vkCmdDispatch(cb, 1, 1, 1);
        barrier_cmd(cb);
        vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, C.qpool, q + 1);
    }
    return q;
}

static uint64_t ts_off = 0;  // host_ns - dev_ticks*period

static void wait_value(uint64_t value, const char *mode, uint64_t t_submit_done) {
    if (!strcmp(mode, "poll")) {
        uint64_t cur = 0;
        for (;;) {
            if (vkGetSemaphoreCounterValue(C.dev, C.sem, &cur) == VK_SUCCESS &&
                cur >= value)
                return;
            sched_yield();
        }
    } else if (!strcmp(mode, "spinblock")) {
        while (now_ns() < t_submit_done + 200000)
            sched_yield();
        VkSemaphoreWaitInfo wi = {.sType = VK_STRUCTURE_TYPE_SEMAPHORE_WAIT_INFO,
            .semaphoreCount = 1, .pSemaphores = &C.sem, .pValues = &value};
        CK(vkWaitSemaphores(C.dev, &wi, 500000000ull));
    } else {
        VkSemaphoreWaitInfo wi = {.sType = VK_STRUCTURE_TYPE_SEMAPHORE_WAIT_INFO,
            .semaphoreCount = 1, .pSemaphores = &C.sem, .pValues = &value};
        CK(vkWaitSemaphores(C.dev, &wi, 500000000ull));
    }
}

int main(int argc, char **argv) {
    const char *mode = argc > 1 ? argv[1] : "single";
    int bcount = argc > 2 ? atoi(argv[2]) : 64;
    int iters = argc > 3 ? atoi(argv[3]) : 300;

    CK(vkCreateInstance(&(VkInstanceCreateInfo){
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pApplicationInfo = &(VkApplicationInfo){
            .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
            .apiVersion = VK_MAKE_API_VERSION(0, 1, 3, 0)}}, NULL, &C.inst));
    uint32_t nd = 1;
    CK(vkEnumeratePhysicalDevices(C.inst, &nd, &C.pd));
    uint32_t nq = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(C.pd, &nq, NULL);
    VkQueueFamilyProperties qp[8];
    vkGetPhysicalDeviceQueueFamilyProperties(C.pd, &nq, qp);
    uint32_t qf = 0;
    for (uint32_t i = 0; i < nq; i++)
        if (qp[i].queueFlags & VK_QUEUE_COMPUTE_BIT) { qf = i; break; }
    float prio = 1.0f;
    VkDeviceQueueCreateInfo qci = {.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = qf, .queueCount = 1, .pQueuePriorities = &prio};
    CK(vkCreateDevice(C.pd, &(VkDeviceCreateInfo){
        .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .queueCreateInfoCount = 1, .pQueueCreateInfos = &qci}, NULL, &C.dev));
    vkGetDeviceQueue(C.dev, qf, 0, &C.queue);

    VkPhysicalDeviceProperties pp;
    vkGetPhysicalDeviceProperties(C.pd, &pp);
    C.ts_period = pp.limits.timestampPeriod;
    fprintf(stderr, "device=%s tsPeriod=%.1fns tsValidBits=%u\n",
            pp.deviceName, C.ts_period, qp[qf].timestampValidBits);

    CK(vkCreateBuffer(C.dev, &(VkBufferCreateInfo){
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = 4096,
        .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT}, NULL, &C.buf));
    VkMemoryRequirements mr;
    vkGetBufferMemoryRequirements(C.dev, C.buf, &mr);
    VkPhysicalDeviceMemoryProperties mp;
    vkGetPhysicalDeviceMemoryProperties(C.pd, &mp);
    uint32_t mi = 0;
    for (uint32_t i = 0; i < mp.memoryTypeCount; i++)
        if ((mr.memoryTypeBits >> i) & 1 &&
            (mp.memoryTypes[i].propertyFlags & VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)) { mi = i; break; }
    CK(vkAllocateMemory(C.dev, &(VkMemoryAllocateInfo){
        .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = mr.size, .memoryTypeIndex = mi}, NULL, &C.mem));
    CK(vkBindBufferMemory(C.dev, C.buf, C.mem, 0));

    VkDescriptorSetLayoutBinding lb = {0, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1,
        VK_SHADER_STAGE_COMPUTE_BIT, NULL};
    CK(vkCreateDescriptorSetLayout(C.dev, &(VkDescriptorSetLayoutCreateInfo){
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
        .bindingCount = 1, .pBindings = &lb}, NULL, &C.dsl));
    CK(vkCreateDescriptorPool(C.dev, &(VkDescriptorPoolCreateInfo){
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, .maxSets = 1,
        .poolSizeCount = 1,
        .pPoolSizes = &(VkDescriptorPoolSize){VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1}},
        NULL, &C.dpool));
    CK(vkAllocateDescriptorSets(C.dev, &(VkDescriptorSetAllocateInfo){
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
        .descriptorPool = C.dpool, .descriptorSetCount = 1,
        .pSetLayouts = &C.dsl}, &C.dset));
    VkDescriptorBufferInfo dbi = {C.buf, 0, VK_WHOLE_SIZE};
    vkUpdateDescriptorSets(C.dev, 1, &(VkWriteDescriptorSet){
        .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstSet = C.dset,
        .dstBinding = 0, .descriptorCount = 1,
        .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
        .pBufferInfo = &dbi}, 0, NULL);
    CK(vkCreatePipelineLayout(C.dev, &(VkPipelineLayoutCreateInfo){
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 1, .pSetLayouts = &C.dsl}, NULL, &C.playout));

    FILE *f = fopen("ping.spv", "rb");
    if (!f) { fprintf(stderr, "ping.spv missing\n"); return 1; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    uint32_t *code = malloc(sz);
    if (fread(code, 1, sz, f) != (size_t)sz) return 1;
    fclose(f);
    VkShaderModule sm;
    CK(vkCreateShaderModule(C.dev, &(VkShaderModuleCreateInfo){
        .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize = sz, .pCode = code}, NULL, &sm));
    CK(vkCreateComputePipelines(C.dev, NULL, 1, &(VkComputePipelineCreateInfo){
        .sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
        .layout = C.playout,
        .stage = {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                  .stage = VK_SHADER_STAGE_COMPUTE_BIT, .module = sm,
                  .pName = "main"}}, NULL, &C.pipe));

    CK(vkCreateCommandPool(C.dev, &(VkCommandPoolCreateInfo){
        .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
        .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,
        .queueFamilyIndex = qf}, NULL, &C.cpool));
    CK(vkAllocateCommandBuffers(C.dev, &(VkCommandBufferAllocateInfo){
        .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool = C.cpool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
        .commandBufferCount = 1}, &C.cb));
    CK(vkCreateQueryPool(C.dev, &(VkQueryPoolCreateInfo){
        .sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,
        .queryType = VK_QUERY_TYPE_TIMESTAMP,
        .queryCount = 2 * (uint32_t)iters + 4}, NULL, &C.qpool));
    CK(vkCreateSemaphore(C.dev, &(VkSemaphoreCreateInfo){
        .sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO,
        .pNext = &(VkSemaphoreTypeCreateInfo){
            .sType = VK_STRUCTURE_TYPE_SEMAPHORE_TYPE_CREATE_INFO,
            .semaphoreType = VK_SEMAPHORE_TYPE_TIMELINE, .initialValue = 0}},
        NULL, &C.sem));

    // ---- calibration: empty submit, timestamp + timeline signal
    vkResetQueryPool(C.dev, C.qpool, 0, 1);
    CK(vkResetCommandBuffer(C.cb, 0));
    CK(vkBeginCommandBuffer(C.cb, &(VkCommandBufferBeginInfo){
        .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO}));
    vkCmdWriteTimestamp(C.cb, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, C.qpool, 0);
    CK(vkEndCommandBuffer(C.cb));
    uint64_t value = 1;
    VkTimelineSemaphoreSubmitInfo ctsi = {
        .sType = VK_STRUCTURE_TYPE_TIMELINE_SEMAPHORE_SUBMIT_INFO,
        .signalSemaphoreValueCount = 1, .pSignalSemaphoreValues = &value};
    VkSemaphoreWaitInfo cwi = {.sType = VK_STRUCTURE_TYPE_SEMAPHORE_WAIT_INFO,
        .semaphoreCount = 1, .pSemaphores = &C.sem, .pValues = &value};
    VkSubmitInfo csi = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .pNext = &ctsi,
        .commandBufferCount = 1, .pCommandBuffers = &C.cb,
        .signalSemaphoreCount = 1, .pSignalSemaphores = &C.sem};
    uint64_t t0 = now_ns();
    CK(vkQueueSubmit(C.queue, 1, &csi, NULL));
    CK(vkWaitSemaphores(C.dev, &cwi, 500000000ull));
    uint64_t t1 = now_ns();
    static uint64_t tsbuf[2 * 4096 + 4];
    CK(vkGetQueryPoolResults(C.dev, C.qpool, 0, 1, sizeof(tsbuf), tsbuf,
                             8, VK_QUERY_RESULT_64_BIT));
    ts_off = (t0 + t1) / 2 - (uint64_t)((double)tsbuf[0] * C.ts_period);
    fprintf(stderr, "calib submit->wake=%llu ns\n", (unsigned long long)(t1 - t0));

    // ---- measured loop
    int warm = iters / 5;
    uint64_t *r_rec = calloc(iters, 8), *r_sub = calloc(iters, 8),
             *r_start = calloc(iters, 8), *r_exec = calloc(iters, 8),
             *r_wake = calloc(iters, 8), *r_wall = calloc(iters, 8);
    vkResetQueryPool(C.dev, C.qpool, 0, 2 * (uint32_t)iters);
    uint64_t sem_value = 1;
    for (int it = 0; it < iters; it++) {
        CK(vkResetCommandBuffer(C.cb, 0));
        uint64_t r0 = now_ns();
        CK(vkBeginCommandBuffer(C.cb, &(VkCommandBufferBeginInfo){
            .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO}));
        rec_iter(C.cb, it, mode, bcount);
        CK(vkEndCommandBuffer(C.cb));
        uint64_t r1 = now_ns();

        value = ++sem_value;
        VkTimelineSemaphoreSubmitInfo tsi = {
            .sType = VK_STRUCTURE_TYPE_TIMELINE_SEMAPHORE_SUBMIT_INFO,
            .signalSemaphoreValueCount = 1, .pSignalSemaphoreValues = &value};
        VkSubmitInfo si = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .pNext = &tsi,
            .commandBufferCount = 1, .pCommandBuffers = &C.cb,
            .signalSemaphoreCount = 1, .pSignalSemaphores = &C.sem};
        uint64_t s0 = now_ns();
        CK(vkQueueSubmit(C.queue, 1, &si, NULL));
        uint64_t s1 = now_ns();

        wait_value(value, mode, s1);
        uint64_t w1 = now_ns();

        static uint64_t ts[2 * 4096 + 4];
        CK(vkGetQueryPoolResults(C.dev, C.qpool, 2 * it, 2, sizeof(ts), ts,
                                 8, VK_QUERY_RESULT_64_BIT));
        if (it >= warm) {
            uint64_t gs = ts_off + (uint64_t)((double)ts[0] * C.ts_period);
            uint64_t ge = ts_off + (uint64_t)((double)ts[1] * C.ts_period);
            int k = it - warm;
            r_rec[k] = r1 - r0;
            r_sub[k] = s1 - s0;
            r_start[k] = gs > s1 ? gs - s1 : 0;
            r_exec[k] = ge - gs;
            r_wake[k] = w1 > ge ? w1 - ge : 0;
            r_wall[k] = w1 - r0;
        }
    }
    int n = iters - warm;
    printf("%s N=%d iters=%d (measured %d)\n", mode, bcount, iters, n);
    printf("  segment      p50      p99     mean   (us)\n");
    printf("  record    %8.2f %8.2f %8.2f\n", ms(pctl(r_rec, n, .5)) * 1e3,
           ms(pctl(r_rec, n, .99)) * 1e3, ms(pctl(r_rec, n, .5)) * 1e3);
    printf("  submit    %8.2f %8.2f\n", ms(pctl(r_sub, n, .5)) * 1e3,
           ms(pctl(r_sub, n, .99)) * 1e3);
    printf("  gpu_start %8.2f %8.2f\n", ms(pctl(r_start, n, .5)) * 1e3,
           ms(pctl(r_start, n, .99)) * 1e3);
    printf("  gpu_exec  %8.2f %8.2f\n", ms(pctl(r_exec, n, .5)) * 1e3,
           ms(pctl(r_exec, n, .99)) * 1e3);
    printf("  wakeup    %8.2f %8.2f\n", ms(pctl(r_wake, n, .5)) * 1e3,
           ms(pctl(r_wake, n, .99)) * 1e3);
    printf("  wall      %8.2f %8.2f\n", ms(pctl(r_wall, n, .5)) * 1e3,
           ms(pctl(r_wall, n, .99)) * 1e3);
    double mean_exec = 0, mean_start = 0, mean_wake = 0, mean_wall = 0;
    for (int i = 0; i < n; i++) {
        mean_exec += (double)r_exec[i] / n; mean_start += (double)r_start[i] / n;
        mean_wake += (double)r_wake[i] / n; mean_wall += (double)r_wall[i] / n;
    }
    printf("  mean: exec=%.2fus start=%.2fus wake=%.2fus wall=%.2fus per-dispatch_exec=%.3fus\n",
           mean_exec / 1e3, mean_start / 1e3, mean_wake / 1e3, mean_wall / 1e3,
           mean_exec / 1e3 / (strncmp(mode, "batch", 5) ? 1 : bcount));
    return 0;
}
