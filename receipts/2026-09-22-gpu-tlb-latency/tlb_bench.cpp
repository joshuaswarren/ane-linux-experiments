// TLB latency microbench for AGX (Honeykrisp): pointer-chase latency over
// 16-byte steps with the next-step index stored in the data (true serial
// dependency). Four access shapes are baked into the chase data:
//   0/4 dense      consecutive steps (one page per 16 KiB)
//   1/5 stride16k  one step per 16 KiB page
//   2/6 stride2m   one step per 2 MiB region
//   3/7 hot16k     all steps inside one 16 KiB page
// Modes 4-7 repeat 0-3 with the src buffer allocated host-visible instead
// of device-local (--memtype host selects the memory type instead; the
// default run reports both via separate invocations).
// Build: g++ -std=c++17 -O2 -o tlb_bench tlb_bench.cpp -ldl
// Run:   flock /tmp/m1-gpu.lock sh -c 'cd /var/tmp/gputlb &&
//        VK_DRIVER_FILES=<icd> ./tlb_bench --memtype local|host'
#include <vulkan/vulkan.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <string>
#include <vector>

#define LIBVK "libvulkan.so.1"

struct VkTable {
  void* handle{nullptr};
  VkInstance inst{VK_NULL_HANDLE};
  VkDevice dev{VK_NULL_HANDLE};
#define VK_FN(name) PFN_vk##name name{nullptr}
  VK_FN(GetInstanceProcAddr);
  VK_FN(GetDeviceProcAddr);
  VK_FN(CreateInstance);
  VK_FN(DestroyInstance);
  VK_FN(EnumeratePhysicalDevices);
  VK_FN(GetPhysicalDeviceProperties);
  VK_FN(GetPhysicalDeviceMemoryProperties);
  VK_FN(GetPhysicalDeviceQueueFamilyProperties);
  VK_FN(CreateDevice);
  VK_FN(DestroyDevice);
  VK_FN(GetDeviceQueue);
  VK_FN(CreateBuffer);
  VK_FN(DestroyBuffer);
  VK_FN(GetBufferMemoryRequirements);
  VK_FN(AllocateMemory);
  VK_FN(FreeMemory);
  VK_FN(BindBufferMemory);
  VK_FN(MapMemory);
  VK_FN(UnmapMemory);
  VK_FN(CreateShaderModule);
  VK_FN(DestroyShaderModule);
  VK_FN(CreateDescriptorSetLayout);
  VK_FN(DestroyDescriptorSetLayout);
  VK_FN(CreatePipelineLayout);
  VK_FN(DestroyPipelineLayout);
  VK_FN(CreateComputePipelines);
  VK_FN(DestroyPipeline);
  VK_FN(CreateDescriptorPool);
  VK_FN(DestroyDescriptorPool);
  VK_FN(AllocateDescriptorSets);
  VK_FN(UpdateDescriptorSets);
  VK_FN(CreateCommandPool);
  VK_FN(DestroyCommandPool);
  VK_FN(AllocateCommandBuffers);
  VK_FN(BeginCommandBuffer);
  VK_FN(EndCommandBuffer);
  VK_FN(QueueSubmit);
  VK_FN(QueueWaitIdle);
  VK_FN(CmdBindPipeline);
  VK_FN(CmdBindDescriptorSets);
  VK_FN(CmdPushConstants);
  VK_FN(CmdDispatch);
  VK_FN(DeviceWaitIdle);
#undef VK_FN
} g_vk;

#define LOAD_INST(fn) g_vk.fn = (PFN_vk##fn)dlsym(g_vk.handle, "vk" #fn)
#define LOAD_DEV(fn) g_vk.fn = (PFN_vk##fn)g_vk.GetDeviceProcAddr(g_vk.dev, "vk" #fn)

static VkPhysicalDeviceMemoryProperties mp_cached;

static uint32_t find_memtype(const VkPhysicalDeviceMemoryProperties& mp,
                             uint32_t bits, VkMemoryPropertyFlags want) {
  for (uint32_t i = 0; i < mp.memoryTypeCount; ++i)
    if (bits & (1u << i) && (mp.memoryTypes[i].propertyFlags & want) == want)
      return i;
  fprintf(stderr, "no memtype want=0x%x bits=0x%x\n", (unsigned)want, bits);
  exit(2);
}

struct Buf {
  VkBuffer buf{VK_NULL_HANDLE};
  VkDeviceMemory mem{VK_NULL_HANDLE};
};


static Buf make_buf(VkBufferCreateInfo ci, VkMemoryPropertyFlags want) {
  Buf b;
  if (g_vk.CreateBuffer(g_vk.dev, &ci, nullptr, &b.buf) != VK_SUCCESS) exit(6);
  VkMemoryRequirements mr;
  g_vk.GetBufferMemoryRequirements(g_vk.dev, b.buf, &mr);
  VkMemoryAllocateInfo mai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
  mai.allocationSize = mr.size;
  mai.memoryTypeIndex = find_memtype(mp_cached, mr.memoryTypeBits, want);
  if (g_vk.AllocateMemory(g_vk.dev, &mai, nullptr, &b.mem) != VK_SUCCESS) exit(7);
  g_vk.BindBufferMemory(g_vk.dev, b.buf, b.mem, 0);
  return b;
}

int main(int argc, char** argv) {
  const char* memtype = "local";
  for (int i = 1; i < argc; ++i)
    if (!strcmp(argv[i], "--memtype") && i + 1 < argc) memtype = argv[++i];

  g_vk.handle = dlopen(LIBVK, RTLD_NOW | RTLD_LOCAL);
  if (!g_vk.handle) return fprintf(stderr, "dlopen: %s\n", dlerror()), 1;
  LOAD_INST(GetInstanceProcAddr);
  LOAD_INST(GetDeviceProcAddr);
  LOAD_INST(CreateInstance);
  LOAD_INST(DestroyInstance);
  LOAD_INST(EnumeratePhysicalDevices);

  VkApplicationInfo ai{VK_STRUCTURE_TYPE_APPLICATION_INFO};
  ai.apiVersion = VK_API_VERSION_1_1;
  VkInstanceCreateInfo ici{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
  ici.pApplicationInfo = &ai;
  if (g_vk.CreateInstance(&ici, nullptr, &g_vk.inst) != VK_SUCCESS) return 3;

  VkPhysicalDevice phys[8];
  uint32_t n = 8;
  g_vk.EnumeratePhysicalDevices(g_vk.inst, &n, phys);
  if (!n) return 4;
  VkPhysicalDevice pd = phys[0];

  g_vk.GetPhysicalDeviceProperties = (PFN_vkGetPhysicalDeviceProperties)
      g_vk.GetInstanceProcAddr(g_vk.inst, "vkGetPhysicalDeviceProperties");
  g_vk.GetPhysicalDeviceMemoryProperties = (PFN_vkGetPhysicalDeviceMemoryProperties)
      g_vk.GetInstanceProcAddr(g_vk.inst, "vkGetPhysicalDeviceMemoryProperties");
  g_vk.GetPhysicalDeviceQueueFamilyProperties = (PFN_vkGetPhysicalDeviceQueueFamilyProperties)
      g_vk.GetInstanceProcAddr(g_vk.inst, "vkGetPhysicalDeviceQueueFamilyProperties");
  VkPhysicalDeviceProperties props;
  g_vk.GetPhysicalDeviceProperties(pd, &props);
  g_vk.GetPhysicalDeviceMemoryProperties(pd, &mp_cached);
  fprintf(stderr, "driver: %s timestampPeriod=%f\n", props.deviceName,
          props.limits.timestampPeriod);

  uint32_t qfam = 0, qcount = 0;
  g_vk.GetPhysicalDeviceQueueFamilyProperties(pd, &qcount, nullptr);
  std::vector<VkQueueFamilyProperties> qfp(qcount);
  g_vk.GetPhysicalDeviceQueueFamilyProperties(pd, &qcount, qfp.data());
  for (uint32_t i = 0; i < qcount; ++i)
    if (qfp[i].queueFlags & VK_QUEUE_COMPUTE_BIT) { qfam = i; break; }

  LOAD_INST(CreateDevice);
  float prio = 1.0f;
  VkDeviceQueueCreateInfo qci{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
  qci.queueFamilyIndex = qfam;
  qci.queueCount = 1;
  qci.pQueuePriorities = &prio;
  VkDeviceCreateInfo dci{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
  dci.queueCreateInfoCount = 1;
  dci.pQueueCreateInfos = &qci;
  if (g_vk.CreateDevice(pd, &dci, nullptr, &g_vk.dev) != VK_SUCCESS) return 5;

  LOAD_DEV(DestroyDevice);
  LOAD_DEV(GetDeviceQueue);
  LOAD_DEV(CreateBuffer);
  LOAD_DEV(DestroyBuffer);
  LOAD_DEV(GetBufferMemoryRequirements);
  LOAD_DEV(AllocateMemory);
  LOAD_DEV(FreeMemory);
  LOAD_DEV(BindBufferMemory);
  LOAD_DEV(MapMemory);
  LOAD_DEV(UnmapMemory);
  LOAD_DEV(CreateShaderModule);
  LOAD_DEV(DestroyShaderModule);
  LOAD_DEV(CreateDescriptorSetLayout);
  LOAD_DEV(DestroyDescriptorSetLayout);
  LOAD_DEV(CreatePipelineLayout);
  LOAD_DEV(DestroyPipelineLayout);
  LOAD_DEV(CreateComputePipelines);
  LOAD_DEV(DestroyPipeline);
  LOAD_DEV(CreateDescriptorPool);
  LOAD_DEV(DestroyDescriptorPool);
  LOAD_DEV(AllocateDescriptorSets);
  LOAD_DEV(UpdateDescriptorSets);
  LOAD_DEV(CreateCommandPool);
  LOAD_DEV(DestroyCommandPool);
  LOAD_DEV(AllocateCommandBuffers);
  LOAD_DEV(BeginCommandBuffer);
  LOAD_DEV(EndCommandBuffer);
  LOAD_DEV(QueueSubmit);
  LOAD_DEV(QueueWaitIdle);
  LOAD_DEV(CmdBindPipeline);
  LOAD_DEV(CmdBindDescriptorSets);
  LOAD_DEV(CmdPushConstants);
  LOAD_DEV(CmdDispatch);
  LOAD_DEV(DeviceWaitIdle);

  VkQueue queue;
  g_vk.GetDeviceQueue(g_vk.dev, qfam, 0, &queue);

  const VkDeviceSize bufsz = 256ull << 20;
  const uint32_t nelem = (uint32_t)(bufsz / 16);   // 16-byte steps
  VkBufferCreateInfo bci{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
  bci.size = bufsz;
  bci.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;

  bool host = !strcmp(memtype, "host");
  VkMemoryPropertyFlags srcwant = host ? (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                                          VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)
                                       : VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT;
  Buf srcb = make_buf(bci, srcwant);
  Buf sinkb = make_buf(bci, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                                VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);

  // descriptor layout: 2 storage buffers
  VkDescriptorSetLayoutBinding lb[2]{};
  lb[0] = {0, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_COMPUTE_BIT, nullptr};
  lb[1] = {1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_COMPUTE_BIT, nullptr};
  VkDescriptorSetLayoutCreateInfo dlci{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
  dlci.bindingCount = 2;
  dlci.pBindings = lb;
  VkDescriptorSetLayout dsl;
  g_vk.CreateDescriptorSetLayout(g_vk.dev, &dlci, nullptr, &dsl);

  VkPushConstantRange pcr{VK_SHADER_STAGE_COMPUTE_BIT, 0, 12};
  VkPipelineLayoutCreateInfo plci{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
  plci.setLayoutCount = 1;
  plci.pSetLayouts = &dsl;
  plci.pushConstantRangeCount = 1;
  plci.pPushConstantRanges = &pcr;
  VkPipelineLayout pl;
  g_vk.CreatePipelineLayout(g_vk.dev, &plci, nullptr, &pl);

  FILE* f = fopen("/var/tmp/gputlb/tlb_read.spv", "rb");
  if (!f) return fprintf(stderr, "missing /var/tmp/gputlb/tlb_read.spv\n"), 8;
  fseek(f, 0, SEEK_END);
  long spvsz = ftell(f);
  fseek(f, 0, SEEK_SET);
  std::vector<uint32_t> spv(spvsz / 4);
  if (fread(spv.data(), 1, spvsz, f) != (size_t)spvsz) return 8;
  fclose(f);
  VkShaderModuleCreateInfo smci{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
  smci.codeSize = spv.size() * 4;
  smci.pCode = spv.data();
  VkShaderModule sm;
  g_vk.CreateShaderModule(g_vk.dev, &smci, nullptr, &sm);

  VkComputePipelineCreateInfo cpci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
  cpci.stage = {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO};
  cpci.stage.stage = VK_SHADER_STAGE_COMPUTE_BIT;
  cpci.stage.module = sm;
  cpci.stage.pName = "main";
  cpci.layout = pl;
  VkPipeline pipe;
  if (g_vk.CreateComputePipelines(g_vk.dev, VK_NULL_HANDLE, 1, &cpci, nullptr, &pipe) != VK_SUCCESS)
    return 9;

  VkDescriptorPoolSize ps{VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 2};
  VkDescriptorPoolCreateInfo dpci{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
  dpci.maxSets = 1;
  dpci.poolSizeCount = 1;
  dpci.pPoolSizes = &ps;
  VkDescriptorPool dp;
  g_vk.CreateDescriptorPool(g_vk.dev, &dpci, nullptr, &dp);
  VkDescriptorSetAllocateInfo dsai{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};
  dsai.descriptorPool = dp;
  dsai.descriptorSetCount = 1;
  dsai.pSetLayouts = &dsl;
  VkDescriptorSet ds;
  g_vk.AllocateDescriptorSets(g_vk.dev, &dsai, &ds);
  VkDescriptorBufferInfo dbi[2] = {{srcb.buf, 0, VK_WHOLE_SIZE}, {sinkb.buf, 0, VK_WHOLE_SIZE}};
  VkWriteDescriptorSet wr[2]{};
  for (int i = 0; i < 2; ++i) {
    wr[i] = {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};
    wr[i].dstSet = ds;
    wr[i].dstBinding = (uint32_t)i;
    wr[i].descriptorCount = 1;
    wr[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    wr[i].pBufferInfo = &dbi[i];
  }
  g_vk.UpdateDescriptorSets(g_vk.dev, 2, wr, 0, nullptr);

  VkCommandPoolCreateInfo cpi{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};
  cpi.queueFamilyIndex = qfam;
  VkCommandPool cp;
  g_vk.CreateCommandPool(g_vk.dev, &cpi, nullptr, &cp);
  VkCommandBufferAllocateInfo cbai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
  cbai.commandPool = cp;
  cbai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
  cbai.commandBufferCount = 1;
  VkCommandBuffer cmd;
  g_vk.AllocateCommandBuffers(g_vk.dev, &cbai, &cmd);

  // chase fill: for step st, words[4*st+3] = next step (in words)
  const uint32_t nstep = nelem;
  auto fill_chase = [&](uint32_t mode) {
    void* p = nullptr;
    if (g_vk.MapMemory(g_vk.dev, srcb.mem, 0, VK_WHOLE_SIZE, 0, &p) != VK_SUCCESS)
      return fprintf(stderr, "src map failed\n"), -1;
    uint32_t* w = (uint32_t*)p;
    uint32_t stride_step = 1;                       // dense
    if (mode == 1 || mode == 5) stride_step = 4097;      // ~16 KiB, coprime with 2^24
    if (mode == 2 || mode == 6) stride_step = 524289;    // ~2 MiB, coprime
    if (mode == 3 || mode == 7) stride_step = 0;         // same page
    for (uint32_t st = 0; st < nstep; ++st) {
      uint32_t nxt = (stride_step ? (st + stride_step) % nstep : st) * 4;
      w[st * 4 + 0] = 0x5a5a0000u | st;
      w[st * 4 + 1] = 0x5a5a0000u | st;
      w[st * 4 + 2] = 0x5a5a0000u | st;
      w[st * 4 + 3] = nxt;
    }
    g_vk.UnmapMemory(g_vk.dev, srcb.mem);
    return 0;
  };
  if (fill_chase(0) != 0) return 10;

  const uint32_t STEPS = 512;   // serialized chase steps per invocation
  const uint32_t WGS = 512;     // workgroups of 32 -> 16384 lanes
  double rep_ms[7];

  const char* names[8] = {"dense", "stride16k", "stride2m", "hot16k",
                          "dense_spread", "stride16k_spread", "stride2m_spread", "hot16k_spread"};
  const uint32_t wgs_list[] = {32, 128, 512, 2048};
  const int NWGS = 4;
  for (uint32_t m = 0; m < 8; ++m) {
    uint32_t fillmode = m % 4;
    if (fill_chase(fillmode) != 0) return 11;
    uint32_t spacing = (m >= 4) ? (4 * nstep) / (2048 * 32) * 4 : 0;
    if (spacing < 4) spacing = 4;
    for (int wi = 0; wi < NWGS; ++wi) {
    uint32_t WGS = wgs_list[wi];
    for (int rep = 0; rep < 7; ++rep) {
      uint32_t pcs[3] = {STEPS, nelem * 4, spacing};
      VkCommandBufferBeginInfo bi{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
      bi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
      g_vk.BeginCommandBuffer(cmd, &bi);
      g_vk.CmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipe);
      g_vk.CmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 1, &ds, 0, nullptr);
      g_vk.CmdPushConstants(cmd, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, 12, pcs);
      g_vk.CmdDispatch(cmd, WGS, 1, 1);
      g_vk.EndCommandBuffer(cmd);
      VkSubmitInfo si{VK_STRUCTURE_TYPE_SUBMIT_INFO};
      si.commandBufferCount = 1;
      si.pCommandBuffers = &cmd;
      auto t0 = std::chrono::steady_clock::now();
      g_vk.QueueSubmit(queue, 1, &si, nullptr);
      g_vk.QueueWaitIdle(queue);
      rep_ms[rep] = std::chrono::duration<double, std::milli>(
          std::chrono::steady_clock::now() - t0).count();
    }
    std::sort(rep_ms, rep_ms + 7);
    double med = rep_ms[3];
    printf("{\"memtype\":\"%s\",\"mode\":\"%s\",\"lanes\":%u,\"steps\":%u,"
           "\"ms_med\":%.3f,\"ns_per_step\":%.1f}\n",
           memtype, names[m], WGS * 32, STEPS, med, med * 1e6 / STEPS);
    fflush(stdout);
    }
  }
  fprintf(stderr, "done\n");
  return 0;
}
