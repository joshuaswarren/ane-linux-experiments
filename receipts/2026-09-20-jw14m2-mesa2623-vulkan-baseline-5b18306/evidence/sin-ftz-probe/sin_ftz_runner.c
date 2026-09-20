/* sin-FTZ probe runner: dispatches sin_ftz.spv with push-constant x and
 * prints input/sin/echo bit patterns. Usage: sin_ftz_runner <shader.spv> */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>

static uint32_t qfam(VkPhysicalDevice pd) {
    uint32_t n = 0; vkGetPhysicalDeviceQueueFamilyProperties(pd, &n, NULL);
    VkQueueFamilyProperties *q = malloc(n * sizeof(*q));
    vkGetPhysicalDeviceQueueFamilyProperties(pd, &n, q);
    uint32_t i; for (i = 0; i < n; i++) if (q[i].queueFlags & VK_QUEUE_COMPUTE_BIT) break;
    if (i == n) { fprintf(stderr, "no compute queue\n"); exit(2); }
    free(q); return i;
}

int main(int argc, char **argv) {
    if (argc != 2) { fprintf(stderr, "usage: %s shader.spv\n", argv[0]); return 1; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("shader"); return 1; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    unsigned *code = malloc((size_t)sz); fread(code, 1, (size_t)sz, f); fclose(f);

    VkApplicationInfo app = {VK_STRUCTURE_TYPE_APPLICATION_INFO, NULL, "sinftz", 0, "sinftz", 0, VK_MAKE_VERSION(1,3,0)};
    VkInstanceCreateInfo ici = {VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, NULL, 0, &app, 0, NULL, 0, NULL};
    VkInstance inst; VkResult r = vkCreateInstance(&ici, NULL, &inst);
    if (r) { fprintf(stderr, "vkCreateInstance %d\n", r); return 1; }

    uint32_t nd = 0; vkEnumeratePhysicalDevices(inst, &nd, NULL);
    VkPhysicalDevice *pds = malloc(nd * sizeof(*pds));
    vkEnumeratePhysicalDevices(inst, &nd, pds);
    VkPhysicalDevice pd = pds[0];

    /* identity + float-controls properties */
    VkPhysicalDeviceDriverProperties drv = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
    VkPhysicalDeviceFloatControlsProperties fc = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FLOAT_CONTROLS_PROPERTIES, &drv};
    VkPhysicalDeviceProperties2 p2 = {VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, &fc};
    vkGetPhysicalDeviceProperties2(pd, &p2);
    printf("device=%s api=%u.%u.%u driverID=%d driverName=%s driverInfo=%s conf=%u.%u.%u.%u denormFlushToF32=%u\n",
           p2.properties.deviceName, VK_API_VERSION_MAJOR(p2.properties.apiVersion),
           VK_API_VERSION_MINOR(p2.properties.apiVersion), VK_API_VERSION_PATCH(p2.properties.apiVersion),
           (int)drv.driverID, drv.driverName, drv.driverInfo,
           drv.conformanceVersion.major, drv.conformanceVersion.minor,
           drv.conformanceVersion.patch, drv.conformanceVersion.subminor,
           fc.shaderDenormFlushToZeroFloat32);

    uint32_t fam = qfam(pd);
    float prio = 1.0f;
    VkDeviceQueueCreateInfo qc = {VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, NULL, 0, fam, 1, &prio};
    VkDeviceCreateInfo dci = {VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, NULL, 0, 1, &qc, 0, NULL, 0, NULL, NULL};
    VkDevice dev; if ((r = vkCreateDevice(pd, &dci, NULL, &dev))) { fprintf(stderr, "vkCreateDevice %d\n", r); return 1; }
    VkQueue queue; vkGetDeviceQueue(dev, fam, 0, &queue);

    /* output buffer: 4 floats host-visible */
    VkBufferCreateInfo bci = {VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, NULL, 0, 16,
                              VK_BUFFER_USAGE_STORAGE_BUFFER_BIT, VK_SHARING_MODE_EXCLUSIVE, 0, NULL};
    VkBuffer buf; vkCreateBuffer(dev, &bci, NULL, &buf);
    VkMemoryRequirements mr; vkGetBufferMemoryRequirements(dev, buf, &mr);
    VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(pd, &mp);
    uint32_t mi; for (mi = 0; mi < mp.memoryTypeCount; mi++) {
        if ((mr.memoryTypeBits & (1u << mi)) &&
            (mp.memoryTypes[mi].propertyFlags & (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))
            == (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) break;
    }
    VkMemoryAllocateInfo mai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, NULL, mr.size, mi};
    VkDeviceMemory mem; vkAllocateMemory(dev, &mai, NULL, &mem);
    vkBindBufferMemory(dev, buf, mem, 0);
    void *map; vkMapMemory(dev, mem, 0, 16, 0, &map);

    VkDescriptorSetLayoutBinding bind = {0, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_COMPUTE_BIT, NULL};
    VkDescriptorSetLayoutCreateInfo dlci = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, NULL, 0, 1, &bind};
    VkDescriptorSetLayout dsl; vkCreateDescriptorSetLayout(dev, &dlci, NULL, &dsl);
    VkDescriptorPoolSize psz = {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1};
    VkDescriptorPoolCreateInfo dpci = {VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, NULL, 0, 1, 1, &psz};
    VkDescriptorPool pool; vkCreateDescriptorPool(dev, &dpci, NULL, &pool);
    VkDescriptorSetAllocateInfo dsai = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, NULL, pool, 1, &dsl};
    VkDescriptorSet set; vkAllocateDescriptorSets(dev, &dsai, &set);
    VkDescriptorBufferInfo bi = {buf, 0, VK_WHOLE_SIZE};
    VkWriteDescriptorSet wr = {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, set, 0, 0, 1,
                               VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, NULL, &bi, NULL};
    vkUpdateDescriptorSets(dev, 1, &wr, 0, NULL);

    VkShaderModuleCreateInfo smci = {VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, NULL, 0, (size_t)sz, code};
    VkShaderModule sm; vkCreateShaderModule(dev, &smci, NULL, &sm);
    VkPipelineShaderStageCreateInfo stage = {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
        NULL, 0, VK_SHADER_STAGE_COMPUTE_BIT, sm, "main", NULL};
    VkPushConstantRange pcr = {VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(float)};
    VkPipelineLayoutCreateInfo plci = {VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, NULL, 0, 1, &dsl, 1, &pcr};
    VkPipelineLayout playout; vkCreatePipelineLayout(dev, &plci, NULL, &playout);
    VkComputePipelineCreateInfo cpci = {VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, NULL, 0, stage, playout, NULL, 0};
    VkPipeline pipe; vkCreateComputePipelines(dev, NULL, 1, &cpci, NULL, &pipe);

    VkCommandPoolCreateInfo cpoi = {VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, NULL, 0, fam};
    VkCommandPool cpool; vkCreateCommandPool(dev, &cpoi, NULL, &cpool);

    /* test vector: +smallest subnormal, -smallest subnormal, 0.5 normal, +0.0 */
    const unsigned xs[4] = {0x00000001u, 0x80000001u, 0x3f000000u, 0x00000000u};
    for (int t = 0; t < 4; t++) {
        VkCommandBufferAllocateInfo cbai = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, NULL, cpool,
                                            VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1};
        VkCommandBuffer cb; vkAllocateCommandBuffers(dev, &cbai, &cb);
        VkCommandBufferBeginInfo bbi = {VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, NULL,
                                        VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT, NULL};
        vkBeginCommandBuffer(cb, &bbi);
        vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipe);
        vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, playout, 0, 1, &set, 0, NULL);
        vkCmdPushConstants(cb, playout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(float), &xs[t]);
        vkCmdDispatch(cb, 1, 1, 1);
        vkEndCommandBuffer(cb);
        VkSubmitInfo si = {VK_STRUCTURE_TYPE_SUBMIT_INFO, NULL, 0, NULL, NULL, 1, &cb, 0, NULL};
        vkQueueSubmit(queue, 1, &si, NULL);
        vkQueueWaitIdle(queue);
        vkFreeCommandBuffers(dev, cpool, 1, &cb);
        unsigned *o = (unsigned *)map;
        printf("x=%08x sin=%08x echo=%08x\n", xs[t], o[0], o[1]);
    }
    printf("PROBE-DONE\n");
    return 0;
}
