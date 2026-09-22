/* coop_prefill_bench.c — standalone Vulkan harness timing the REAL prefill
 * coopmat QMM shader (qmm_coopmat.comp variants) on honeykrisp, in the
 * tools/q4-bw-bench tradition. Also bit-verifies a candidate against the
 * base shader on identical inputs.
 *
 * Usage: coop_prefill_bench <cand.spv> <m> <n> <k> <reps> [ref.spv]
 *   - compiles <cand.spv> (must be built with -DX_BF16 -DOUT_BF16), fills
 *     random Q4/bf16 inputs, times m*n*k*2 FLOP; if ref.spv given, runs it
 *     into a second output and compares raw bits (mismatches -> exit 3).
 * Prints one JSON line.
 */
#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>
#define WARMUP 3
#define PC_WORDS 30
#define PC_SIZE (PC_WORDS * 4)

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}
static int cmp_d(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}
static uint32_t *read_spv(const char *p, long *sz) {
    FILE *f = fopen(p, "rb");
    if (!f) { perror(p); exit(1); }
    fseek(f, 0, SEEK_END); *sz = ftell(f); fseek(f, 0, SEEK_SET);
    uint32_t *spv = malloc((size_t)*sz);
    if (fread(spv, 1, (size_t)*sz, f) != (size_t)*sz) { perror("read"); exit(1); }
    fclose(f);
    return spv;
}
static uint32_t rnd_state = 0x12345678u;
static uint32_t rnd(void) {
    rnd_state ^= rnd_state << 13; rnd_state ^= rnd_state >> 17;
    rnd_state ^= rnd_state << 5;
    return rnd_state;
}

int main(int argc, char **argv) {
    if (argc != 6 && argc != 7) {
        fprintf(stderr, "usage: %s cand.spv m n k reps [ref.spv]\n", argv[0]);
        return 2;
    }
    const char *cand_path = argv[1];
    uint32_t m = strtoul(argv[2], NULL, 10);
    uint32_t n = strtoul(argv[3], NULL, 10);
    uint32_t k = strtoul(argv[4], NULL, 10);
    int reps = atoi(argv[5]);
    int have_ref = argc == 7;
    long cand_sz, ref_sz = 0;
    uint32_t *cand_spv = read_spv(cand_path, &cand_sz);
    uint32_t *ref_spv = have_ref ? read_spv(argv[6], &ref_sz) : NULL;

    VkApplicationInfo app = { .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO, .apiVersion = VK_API_VERSION_1_3 };
    VkInstanceCreateInfo ici = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &app };
    VkInstance inst;
    if (vkCreateInstance(&ici, NULL, &inst) != VK_SUCCESS) { fprintf(stderr, "vkCreateInstance failed\n"); return 1; }
    uint32_t nd = 0; vkEnumeratePhysicalDevices(inst, &nd, NULL);
    VkPhysicalDevice devs[8]; vkEnumeratePhysicalDevices(inst, &nd, devs);
    VkPhysicalDevice pd = NULL; char dname[256] = "?";
    for (uint32_t i = 0; i < nd; i++) {
        VkPhysicalDeviceProperties p; vkGetPhysicalDeviceProperties(devs[i], &p);
        if (strstr(p.deviceName, "llvmpipe") || strstr(p.deviceName, "lavapipe") ||
            strstr(p.deviceName, "softpipe")) continue;
        pd = devs[i]; snprintf(dname, sizeof dname, "%s", p.deviceName); break;
    }
    if (!pd) { fprintf(stderr, "no hardware device\n"); return 1; }
    uint32_t qf = 0xFFFFFFFFu, nq = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(pd, &nq, NULL);
    VkQueueFamilyProperties qp[16]; vkGetPhysicalDeviceQueueFamilyProperties(pd, &nq, qp);
    for (uint32_t i = 0; i < nq; i++) if (qp[i].queueFlags & VK_QUEUE_COMPUTE_BIT) { qf = i; break; }
    if (qf == 0xFFFFFFFFu) { fprintf(stderr, "no compute queue\n"); return 1; }

    const char *exts[] = { "VK_KHR_shader_float16_int8", "VK_KHR_cooperative_matrix" };
    float prio = 1.0f;
    VkDeviceQueueCreateInfo qci = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = qf, .queueCount = 1, .pQueuePriorities = &prio };
    VkPhysicalDeviceCooperativeMatrixFeaturesKHR cmfeat = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_COOPERATIVE_MATRIX_FEATURES_KHR, .cooperativeMatrix = VK_TRUE };
    VkPhysicalDeviceFloat16Int8FeaturesKHR f16feat = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FLOAT16_INT8_FEATURES_KHR, .pNext = &cmfeat, .shaderFloat16 = VK_TRUE };
    VkPhysicalDeviceFeatures2 feat2 = { .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, .pNext = &f16feat };
    VkDeviceCreateInfo dci = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .pNext = &feat2,
        .queueCreateInfoCount = 1, .pQueueCreateInfos = &qci,
        .enabledExtensionCount = 2, .ppEnabledExtensionNames = exts };
    VkDevice dev;
    if (vkCreateDevice(pd, &dci, NULL, &dev) != VK_SUCCESS) { fprintf(stderr, "vkCreateDevice failed\n"); return 1; }
    VkQueue queue; vkGetDeviceQueue(dev, qf, 0, &queue);

    VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(pd, &mp);
#define NBUF 6
    size_t buf_words[NBUF];
    buf_words[0] = (size_t)m * k / 2;         /* x: u32 words */
    buf_words[1] = (size_t)n * k / 8;         /* w: u32 words */
    buf_words[2] = (size_t)n * (k / 64) * 2 / 4; /* scales: u16 -> u32 words */
    buf_words[3] = buf_words[2];              /* biases */
    buf_words[4] = (size_t)m * n * 2 / 4;     /* out cand */
    buf_words[5] = have_ref ? buf_words[4] : 0;
    VkBuffer bufs[NBUF]; VkDeviceMemory mems[NBUF];
    void *maps[NBUF];
    for (int i = 0; i < NBUF; i++) {
        if (buf_words[i] == 0) { bufs[i] = VK_NULL_HANDLE; continue; }
        VkBufferCreateInfo bci = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
            .size = buf_words[i] * 4, .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT };
        if (vkCreateBuffer(dev, &bci, NULL, &bufs[i]) != VK_SUCCESS) { fprintf(stderr, "buffer %d failed\n", i); return 1; }
        VkMemoryRequirements mr; vkGetBufferMemoryRequirements(dev, bufs[i], &mr);
        const uint32_t want = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
        uint32_t mti = 0; while (!(mr.memoryTypeBits & (1u << mti)) ||
            (mp.memoryTypes[mti].propertyFlags & want) != want) mti++;
        VkMemoryAllocateInfo mai = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
            .allocationSize = mr.size, .memoryTypeIndex = mti };
        if (vkAllocateMemory(dev, &mai, NULL, &mems[i]) != VK_SUCCESS) { fprintf(stderr, "alloc %d failed\n", i); return 1; }
        vkBindBufferMemory(dev, bufs[i], mems[i], 0);
        vkMapMemory(dev, mems[i], 0, VK_WHOLE_SIZE, 0, &maps[i]);
        uint32_t *h = maps[i];
        for (size_t j = 0; j < buf_words[i]; j++) h[j] = (i == 2 || i == 3) ? rnd() : rnd();
    }

    VkDescriptorSetLayoutBinding binds[5];
    for (int i = 0; i < 5; i++)
        binds[i] = (VkDescriptorSetLayoutBinding){ .binding = (uint32_t)i,
            .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .descriptorCount = 1,
            .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT };
    VkDescriptorSetLayoutCreateInfo dlci = { .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, .bindingCount = 5, .pBindings = binds };
    VkDescriptorSetLayout dsl;
    if (vkCreateDescriptorSetLayout(dev, &dlci, NULL, &dsl) != VK_SUCCESS) { fprintf(stderr, "dsl failed\n"); return 1; }
    VkPushConstantRange pcr = { .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT, .offset = 0, .size = PC_SIZE };
    VkPipelineLayoutCreateInfo plci = { .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount = 1, .pSetLayouts = &dsl, .pushConstantRangeCount = 1, .pPushConstantRanges = &pcr };
    VkPipelineLayout pl;
    if (vkCreatePipelineLayout(dev, &plci, NULL, &pl) != VK_SUCCESS) { fprintf(stderr, "pl failed\n"); return 1; }

    uint32_t pc[PC_WORDS] = {0};
    pc[11] = m; pc[12] = n; pc[13] = k;      /* matrix_m/n/k */
    pc[18] = 1;                              /* shape[0] = batch */
    pc[19] = n * k / 8;                      /* shape[1] = w batch words */
    pc[20] = n * (k / 64);                   /* shape[2] = scales/biases */

    VkDescriptorPoolSize psize = { .type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .descriptorCount = 5 };
    VkDescriptorPoolCreateInfo dpci = { .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, .maxSets = 1, .poolSizeCount = 1, .pPoolSizes = &psize };
    VkDescriptorPool pool; vkCreateDescriptorPool(dev, &dpci, NULL, &pool);
    VkDescriptorSetAllocateInfo dsai = { .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, .descriptorPool = pool, .descriptorSetCount = 1, .pSetLayouts = &dsl };
    VkDescriptorSet dset; vkAllocateDescriptorSets(dev, &dsai, &dset);
    VkWriteDescriptorSet wrs[5];
    VkDescriptorBufferInfo dbi[5];
    for (int i = 0; i < 5; i++) {
        dbi[i] = (VkDescriptorBufferInfo){ .buffer = bufs[i], .offset = 0, .range = VK_WHOLE_SIZE };
        wrs[i] = (VkWriteDescriptorSet){ .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
            .dstSet = dset, .dstBinding = (uint32_t)i, .descriptorCount = 1,
            .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .pBufferInfo = &dbi[i] };
    }
    vkUpdateDescriptorSets(dev, 5, wrs, 0, NULL);

    VkCommandPoolCreateInfo cpi = { .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .queueFamilyIndex = qf };
    VkCommandPool cpool; vkCreateCommandPool(dev, &cpi, NULL, &cpool);
    VkCommandBufferAllocateInfo cbai = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool = cpool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1 };
    VkCommandBuffer cmd; vkAllocateCommandBuffers(dev, &cbai, &cmd);

    /* pipeline builder for one spv -> one grid */
    VkPipeline pipes[2] = {VK_NULL_HANDLE, VK_NULL_HANDLE};
    long sizes[2] = { cand_sz, ref_sz };
    for (int p = 0; p < (have_ref ? 2 : 1); p++) {
        VkShaderModuleCreateInfo smci = { .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
            .codeSize = (size_t)sizes[p], .pCode = p == 0 ? cand_spv : ref_spv };
        VkShaderModule sm;
        if (vkCreateShaderModule(dev, &smci, NULL, &sm) != VK_SUCCESS) { fprintf(stderr, "shader module %d failed\n", p); return 1; }
        VkPipelineShaderStageCreateInfo ss = { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            .stage = VK_SHADER_STAGE_COMPUTE_BIT, .module = sm, .pName = "main" };
        VkComputePipelineCreateInfo cpci = { .sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, .stage = ss, .layout = pl };
        if (vkCreateComputePipelines(dev, NULL, 1, &cpci, NULL, &pipes[p]) != VK_SUCCESS) {
            fprintf(stderr, "pipeline failed (%s)\n", p == 0 ? cand_path : argv[6]); return 1;
        }
    }

    /* the shader hardcodes TILE_N=32 and TILE_M=32 today */
    uint32_t gx = (n + 31u) / 32u, gy = (m + 31u) / 32u;
    double times[64];
    if (reps > 64) reps = 64;
    for (int r = 0; r < WARMUP + reps; r++) {
        vkResetCommandBuffer(cmd, 0);
        VkCommandBufferBeginInfo bi = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO };
        vkBeginCommandBuffer(cmd, &bi);
        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipes[0]);
        vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 1, &dset, 0, NULL);
        vkCmdPushConstants(cmd, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, PC_SIZE, pc);
        vkCmdDispatch(cmd, gx, gy, 1);
        vkEndCommandBuffer(cmd);
        VkSubmitInfo si = { .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &cmd };
        double t0 = now_s();
        vkQueueSubmit(queue, 1, &si, NULL);
        vkQueueWaitIdle(queue);
        double t1 = now_s();
        if (r >= WARMUP) times[r - WARMUP] = t1 - t0;
    }
    qsort(times, reps, sizeof(double), cmp_d);
    double med = times[reps / 2], mn = times[0];
    double gflop = 2.0 * m * n * k / 1e9;

    uint64_t sum = 0;
    {
        uint32_t *h = maps[4];
        for (size_t j = 0; j < buf_words[4]; j++) sum += h[j];
    }
    long mismatch = -1;
    double maxdiff = -1.0;
    if (have_ref) {
        /* ref pass */
        vkResetCommandBuffer(cmd, 0);
        VkCommandBufferBeginInfo bi = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO };
        vkBeginCommandBuffer(cmd, &bi);
        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipes[1]);
        vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 1, &dset, 0, NULL);
        /* rebind output to buf 5 */
        VkDescriptorBufferInfo dbi2 = { .buffer = bufs[5], .offset = 0, .range = VK_WHOLE_SIZE };
        VkWriteDescriptorSet wr2 = { .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
            .dstSet = dset, .dstBinding = 4, .descriptorCount = 1,
            .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .pBufferInfo = &dbi2 };
        vkUpdateDescriptorSets(dev, 1, &wr2, 0, NULL);
        vkCmdPushConstants(cmd, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, PC_SIZE, pc);
        vkCmdDispatch(cmd, gx, gy, 1);
        vkEndCommandBuffer(cmd);
        VkSubmitInfo si = { .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &cmd };
        vkQueueSubmit(queue, 1, &si, NULL);
        vkQueueWaitIdle(queue);
        uint16_t *a = maps[4], *b = maps[5];
        mismatch = 0;
        for (size_t j = 0; j < (size_t)m * n; j++) {
            if (a[j] != b[j]) {
                mismatch++;
                union { uint32_t u; float f; } xa, xb;
                xa.u = (uint32_t)a[j] << 16; xb.u = (uint32_t)b[j] << 16;
                double d = fabs((double)xa.f - (double)xb.f);
                if (d > maxdiff) maxdiff = d;
            }
        }
        /* restore binding for any further use */
        vkUpdateDescriptorSets(dev, 1, &wrs[4], 0, NULL);
    }

    printf("{\"cand\":\"%s\",\"ref\":\"%s\",\"device\":\"%s\",\"m\":%u,\"n\":%u,\"k\":%u,"
           "\"gx\":%u,\"gy\":%u,\"ms_med\":%.3f,\"ms_min\":%.3f,"
           "\"tflops_med\":%.3f,\"tflops_min\":%.3f,\"checksum\":%llu,\"mismatch\":%ld,\"maxdiff\":%g}\n",
           cand_path, have_ref ? argv[6] : "", dname, m, n, k, gx, gy,
           med * 1e3, mn * 1e3, gflop / med / 1e3, gflop / mn / 1e3,
           (unsigned long long)sum, mismatch, maxdiff);
    return mismatch > 0 ? 3 : 0;
}
