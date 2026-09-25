// Copyright © 2026 Joshua Warren / mlx-omarchy contributors.
// SPDX-License-Identifier: MIT

// In-process ANE island submission. Compiles with MLX_OMARCHY_ANE_DEVICE=1
// against the same pinned omarchy-ane headers as the worker exe and links
// worker_libane.cpp + bundle.cpp + manifest.cpp into the host process: the
// pipe, the child process, and the per-submit IPC framing are gone. Tile
// layout, dispatch plan, and manifest validation are the worker's own code
// (AneDevice via libane, load_bundle) -- NOT a reimplementation from ane.h.
//
// Safety contract, preserved by other means in-process:
//   - The submit executes on one persistent C++ thread; the caller's wait
//     is bounded by the active deadline (per-submit, or the open batch's
//     absolute deadline). The host thread is never blocked unbounded.
//   - The host-global quarantine file (/run/lock/mlx-omarchy-ane/quarantine,
//     non-empty = quarantined for this boot) is checked before every
//     submit; a non-empty file adopts quarantine and refuses.
//   - On a deadline miss the device completion state is uncertain, exactly
//     like a killed worker child: the session sets in-process quarantine,
//     best-effort writes the boot id into the quarantine file, returns
//     timeout, and refuses every later submit. There is no retry. The
//     submit thread may still be inside the blocking ANE ioctl; a kernel
//     ioctl cannot be killed safely, so the thread is abandoned and its
//     session leaked by ane_inproc_close (bounded by process lifetime).

#ifdef MLX_OMARCHY_ANE_DEVICE

#include "mlx/backend/omarchy/ane/worker.h"

#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

// Declared in tools/mlx-omarchy-ane-worker/main.cpp; defined in
// worker_libane.cpp, which this shim links.
namespace mlx::core::omarchy::ane {
std::unique_ptr<AneDevice> make_libane_device(const std::string& library);
}

namespace {

namespace ane = mlx::core::omarchy::ane;

constexpr const char* kQuarantinePath = "/run/lock/mlx-omarchy-ane/quarantine";

std::string one_line(std::string text) {
  for (char& c : text) {
    if (c == '\n' || c == '\r') c = ' ';
  }
  return text;
}

std::string read_quarantine() {
  std::ifstream in(kQuarantinePath, std::ios::binary);
  if (!in) {
    return {}; // unprovisioned host: no quarantine signal
  }
  std::string value((std::istreambuf_iterator<char>(in)),
                    std::istreambuf_iterator<char>());
  while (!value.empty() && (value.back() == '\n' || value.back() == '\r')) {
    value.pop_back();
  }
  return value;
}

// Best-effort: quarantine provisioning is root-owned; on a host without
// it the in-process quarantine still holds for this process.
void write_quarantine_best_effort() {
  std::ifstream boot("/proc/sys/kernel/random/boot_id");
  std::string boot_id;
  std::getline(boot, boot_id);
  if (boot_id.empty()) {
    return;
  }
  std::ofstream out(kQuarantinePath, std::ios::binary | std::ios::trunc);
  if (out) {
    out << boot_id << "\n";
  }
}

using Buffer = std::vector<uint8_t>;

// Caller input payload: borrowed pointer, valid for the duration of one
// submit (the caller blocks until the submit completes or times out).
using Span = std::pair<const uint8_t*, uint64_t>;

// Caller output buffer: unpacking reads write straight into it, so a
// manifest output crosses the shim boundary with zero copies.
struct Sink {
  uint8_t* data;
  uint64_t cap;
};

// Faithful port of the worker's execute_plan (worker.cpp): dispatch plan
// over resident programs, manifest bindings route tensors by name, the
// device owns packing/unpacking (ane_pack_rows / ane_unpack_rows).
// Inputs are borrowed spans; sunk outputs bypass the intermediate map.
void execute_plan(
    ane::AneDevice& device,
    const ane::AneBundle& bundle,
    const std::map<std::string, Span>& inputs,
    const std::map<std::string, Sink>& sinks,
    std::map<std::string, Buffer>& produced) {
  auto lookup = [&](const std::string& name) -> Span {
    auto made = produced.find(name);
    if (made != produced.end() && !made->second.empty()) {
      return {made->second.data(), made->second.size()};
    }
    auto input = inputs.find(name);
    if (input != inputs.end()) {
      return input->second;
    }
    return {nullptr, 0};
  };
  for (auto index : bundle.manifest.dispatch_plan) {
    if (index >= bundle.programs.size() ||
        index >= bundle.manifest.programs.size()) {
      throw ane::AneDeviceError("dispatch plan references unknown program");
    }
    const auto& validated = bundle.programs[index];
    const auto& program = bundle.manifest.programs[index];
    for (size_t position = 0; position < program.inputs.size(); ++position) {
      const auto& binding = program.inputs[position];
      const Span& span = lookup(binding.tensor);
      if (span.first == nullptr) {
        throw ane::AneDeviceError(
            "program '" + program.payload + "' input tensor '" +
            binding.tensor + "' has no staged value");
      }
      if (span.second < binding.logical_bytes) {
        throw ane::AneDeviceError(
            "tensor '" + binding.tensor + "' payload is " +
            std::to_string(span.second) + " bytes, manifest "
            "requires " + std::to_string(binding.logical_bytes));
      }
      device.send(validated.manifest_index,
                  static_cast<uint32_t>(position), binding,
                  span.first, span.second);
    }
    device.exec(validated.manifest_index);
    for (size_t position = 0; position < program.outputs.size(); ++position) {
      const auto& binding = program.outputs[position];
      auto sink = sinks.find(binding.tensor);
      if (sink != sinks.end() && binding.logical_bytes <= sink->second.cap) {
        // Zero-copy: unpack straight into the caller's buffer.
        device.read(validated.manifest_index,
                    static_cast<uint32_t>(position), binding,
                    sink->second.data, binding.logical_bytes);
        continue;
      }
      Buffer buffer(binding.logical_bytes);
      device.read(validated.manifest_index,
                  static_cast<uint32_t>(position), binding,
                  buffer.data(), buffer.size());
      produced[binding.tensor] = std::move(buffer);
    }
  }
  for (const auto& tensor : bundle.manifest.outputs) {
    if (sinks.count(tensor.name)) {
      continue; // delivered directly into the caller's buffer
    }
    if (!produced.count(tensor.name)) {
      throw ane::AneDeviceError(
          "manifest output '" + tensor.name + "' was never produced");
    }
  }
}

enum Outcome : int {
  ANE_INPROC_OK = 0,
  ANE_INPROC_BAD_ARGS = 1,
  ANE_INPROC_REFUSED = 2,
  ANE_INPROC_TIMEOUT = 3,
  ANE_INPROC_DEVICE_FAILED = 4,
};

struct Executed {
  bool ok{false};
  std::string error;
};

// Accumulates device-phase nanoseconds for the submit in flight; the
// submit thread is the only writer between job submission and pickup.
struct TimingDevice final : ane::AneDevice {
  explicit TimingDevice(std::unique_ptr<ane::AneDevice> inner)
      : inner_(std::move(inner)) {}

  std::string describe() const override { return inner_->describe(); }
  void load(const ane::AneValidatedProgram& program) override {
    inner_->load(program);
  }
  void release() override { inner_->release(); }

  void send(size_t manifest_index, uint32_t channel,
            const ane::AneProgramBinding& binding, const uint8_t* data,
            size_t size) override {
    const auto begin = std::chrono::steady_clock::now();
    inner_->send(manifest_index, channel, binding, data, size);
    send_ns += std::chrono::duration_cast<std::chrono::nanoseconds>(
                   std::chrono::steady_clock::now() - begin)
                   .count();
  }
  void exec(size_t manifest_index) override {
    const auto begin = std::chrono::steady_clock::now();
    inner_->exec(manifest_index);
    exec_ns += std::chrono::duration_cast<std::chrono::nanoseconds>(
                   std::chrono::steady_clock::now() - begin)
                   .count();
  }
  void read(size_t manifest_index, uint32_t channel,
            const ane::AneProgramBinding& binding, uint8_t* out,
            size_t size) override {
    const auto begin = std::chrono::steady_clock::now();
    inner_->read(manifest_index, channel, binding, out, size);
    read_ns += std::chrono::duration_cast<std::chrono::nanoseconds>(
                   std::chrono::steady_clock::now() - begin)
                   .count();
  }

  std::unique_ptr<ane::AneDevice> inner_;
  uint64_t send_ns{0};
  uint64_t exec_ns{0};
  uint64_t read_ns{0};
};

struct Session {
  std::unique_ptr<TimingDevice> device;
  std::vector<ane::AneBundle> bundles;

  std::mutex mu;
  std::condition_variable cv;
  bool quit{false};
  bool job{false};
  size_t bundle_index{0};
  std::map<std::string, Span> inputs;
  std::map<std::string, Sink> sinks;
  std::map<std::string, uint64_t> expected;
  Executed result;

  bool quarantined{false};
  std::string reason;
  std::chrono::steady_clock::time_point batch_until{};
  bool batching{false};
  uint64_t last_send_ns{0};
  uint64_t last_exec_ns{0};
  uint64_t last_read_ns{0};

  std::thread loop; // persistent submit thread
};

void enter_quarantine(Session* s, const std::string& why) {
  s->quarantined = true;
  s->reason = why;
  write_quarantine_best_effort();
}

void submit_loop(Session* s) {
  std::unique_lock<std::mutex> lk(s->mu);
  for (;;) {
    s->cv.wait(lk, [&] { return s->job || s->quit; });
    if (s->quit) {
      return;
    }
    Executed done;
    try {
      std::map<std::string, Buffer> produced;
      execute_plan(*s->device, s->bundles[s->bundle_index], s->inputs,
                   s->sinks, produced);
      done.ok = true;
    } catch (const std::exception& error) {
      done.error = one_line(error.what());
    }
    s->inputs.clear();
    s->sinks.clear();
    s->result = std::move(done);
    s->job = false;
    lk.unlock();
    s->cv.notify_all();
    lk.lock();
  }
}

} // namespace

extern "C" {

typedef void* ane_inproc_t;

ane_inproc_t ane_inproc_open(
    const char* libane_library,
    const char* const* bundle_dirs,
    int bundle_count,
    char* error,
    int error_cap) {
  auto fail = [&](const std::string& why) {
    if (error != nullptr && error_cap > 0) {
      std::snprintf(error, static_cast<size_t>(error_cap), "%s",
                    why.c_str());
    }
    return nullptr;
  };
  if (libane_library == nullptr || bundle_dirs == nullptr ||
      bundle_count <= 0) {
    return fail("ane_inproc_open: bad arguments");
  }
  if (!read_quarantine().empty()) {
    return fail("ANE runtime is quarantined for this boot; reboot required");
  }
  auto* s = new Session();
  try {
    // Every program of every bundle is loaded into one device, so the
    // device keys must be unique across bundles: each bundle's programs
    // are offset by the programs already claimed (same as the worker's
    // resident open).
    size_t base = 0;
    for (int i = 0; i < bundle_count; ++i) {
      s->bundles.push_back(ane::load_bundle(bundle_dirs[i]));
      for (auto& program : s->bundles.back().programs) {
        program.manifest_index += base;
      }
      base += s->bundles.back().programs.size();
    }
    s->device = std::make_unique<TimingDevice>(
        ane::make_libane_device(libane_library));
    for (const auto& bundle : s->bundles) {
      for (const auto& program : bundle.programs) {
        s->device->load(program);
      }
    }
  } catch (const std::exception& error) {
    std::string why = one_line(error.what());
    delete s;
    return fail("ane_inproc_open failed: " + why);
  }
  s->loop = std::thread(submit_loop, s);
  return s;
}

int ane_inproc_quarantined(ane_inproc_t handle) {
  auto* s = static_cast<Session*>(handle);
  if (s == nullptr) {
    return 1;
  }
  std::lock_guard<std::mutex> lk(s->mu);
  return s->quarantined ? 1 : 0;
}

int ane_inproc_reason(ane_inproc_t handle, char* error, int error_cap) {
  auto* s = static_cast<Session*>(handle);
  if (s == nullptr || error == nullptr || error_cap <= 0) {
    return -1;
  }
  std::lock_guard<std::mutex> lk(s->mu);
  std::snprintf(error, static_cast<size_t>(error_cap), "%s",
                s->reason.c_str());
  return 0;
}

int ane_inproc_begin_batch(ane_inproc_t handle, int deadline_ms) {
  auto* s = static_cast<Session*>(handle);
  if (s == nullptr || deadline_ms <= 0) {
    return ANE_INPROC_BAD_ARGS;
  }
  std::lock_guard<std::mutex> lk(s->mu);
  if (s->quarantined) {
    return ANE_INPROC_REFUSED;
  }
  s->batch_until =
      std::chrono::steady_clock::now() +
      std::chrono::milliseconds(deadline_ms);
  s->batching = true;
  return ANE_INPROC_OK;
}

int ane_inproc_end_batch(ane_inproc_t handle) {
  auto* s = static_cast<Session*>(handle);
  if (s == nullptr) {
    return ANE_INPROC_BAD_ARGS;
  }
  std::lock_guard<std::mutex> lk(s->mu);
  s->batching = false;
  return ANE_INPROC_OK;
}

int ane_inproc_submit(
    ane_inproc_t handle,
    int bundle_index,
    const char* const* in_names,
    const uint8_t* const* in_data,
    const uint64_t* in_sizes,
    int in_count,
    const char* const* out_names,
    int out_count,
    uint8_t* const* out_data,
    uint64_t* out_sizes,
    int deadline_ms,
    char* error,
    int error_cap) {
  auto fail = [&](int code, const std::string& why) {
    if (error != nullptr && error_cap > 0) {
      std::snprintf(error, static_cast<size_t>(error_cap), "%s", why.c_str());
    }
    return code;
  };
  auto* s = static_cast<Session*>(handle);
  if (s == nullptr || in_names == nullptr || in_data == nullptr ||
      in_sizes == nullptr || out_names == nullptr ||
      (out_count > 0 && (out_data == nullptr || out_sizes == nullptr))) {
    return fail(ANE_INPROC_BAD_ARGS, "ane_inproc_submit: bad arguments");
  }
  {
    std::lock_guard<std::mutex> lk(s->mu);
    if (s->quarantined) {
      return fail(ANE_INPROC_REFUSED,
                  "refused: quarantined: " + s->reason);
    }
  }
  // Host-global quarantine is checked before every submit.
  if (!read_quarantine().empty()) {
    std::lock_guard<std::mutex> lk(s->mu);
    s->quarantined = true;
    s->reason = "host quarantine file is set";
    return fail(ANE_INPROC_REFUSED,
                "refused: ANE quarantined for this boot");
  }
  if (bundle_index < 0 ||
      static_cast<size_t>(bundle_index) >= s->bundles.size()) {
    return fail(ANE_INPROC_BAD_ARGS,
                "ane_inproc_submit: unknown bundle index");
  }
  // Borrow the caller's input pointers and prevalidate the outputs
  // against the manifest. The caller blocks until the submit completes
  // or the deadline expires, so the borrowed memory stays valid while
  // the submit thread reads it.
  const auto& bundle = s->bundles[static_cast<size_t>(bundle_index)];
  std::map<std::string, Span> inputs;
  for (int i = 0; i < in_count; ++i) {
    if (in_names[i] == nullptr ||
        (in_sizes[i] > 0 && in_data[i] == nullptr)) {
      return fail(ANE_INPROC_BAD_ARGS,
                  "ane_inproc_submit: bad input descriptor");
    }
    inputs[in_names[i]] = Span{in_data[i], in_sizes[i]};
  }
  std::map<std::string, uint64_t> logical; // manifest output name -> bytes
  for (const auto& program : bundle.manifest.programs) {
    for (const auto& binding : program.outputs) {
      logical[binding.tensor] = binding.logical_bytes;
    }
  }
  std::map<std::string, Sink> sinks;
  std::map<std::string, uint64_t> expected;
  for (int i = 0; i < out_count; ++i) {
    if (out_names[i] == nullptr) {
      return fail(ANE_INPROC_BAD_ARGS,
                  "ane_inproc_submit: bad output descriptor");
    }
    auto found = logical.find(out_names[i]);
    if (found == logical.end()) {
      return fail(ANE_INPROC_BAD_ARGS,
                  std::string("unknown manifest output '") +
                      out_names[i] + "'");
    }
    if (out_data[i] == nullptr || out_sizes[i] < found->second) {
      return fail(ANE_INPROC_BAD_ARGS,
                  std::string("output '") + out_names[i] +
                      "' buffer smaller than manifest logical bytes");
    }
    sinks[out_names[i]] = Sink{out_data[i], out_sizes[i]};
    expected[out_names[i]] = found->second;
  }

  const auto per_submit =
      std::chrono::steady_clock::now() +
      std::chrono::milliseconds(deadline_ms);
  {
    std::unique_lock<std::mutex> lk(s->mu);
    s->inputs = std::move(inputs);
    s->sinks = std::move(sinks);
    s->bundle_index = static_cast<size_t>(bundle_index);
    s->result = Executed{};
    s->device->send_ns = 0;
    s->device->exec_ns = 0;
    s->device->read_ns = 0;
    s->job = true;
    const auto until = s->batching ? s->batch_until : per_submit;
    lk.unlock();
    s->cv.notify_all();
    lk.lock();
    if (!s->cv.wait_until(lk, until, [&] { return !s->job; })) {
      // Device completion state is uncertain: quarantine, refuse, no retry.
      enter_quarantine(
          s, "submit deadline expired; device state uncertain");
      return fail(ANE_INPROC_TIMEOUT,
                  "submit deadline expired; quarantined, no retry");
    }
    if (!s->result.ok) {
      // A clean named failure from the plan/device: session is over.
      s->quarantined = true;
      s->reason = s->result.error;
      return fail(ANE_INPROC_DEVICE_FAILED, s->result.error);
    }
    s->last_send_ns = s->device->send_ns;
    s->last_exec_ns = s->device->exec_ns;
    s->last_read_ns = s->device->read_ns;
  }
  for (int i = 0; i < out_count; ++i) {
    out_sizes[i] = expected[out_names[i]];
  }
  return ANE_INPROC_OK;
}

int ane_inproc_timings(
    ane_inproc_t handle,
    uint64_t* send_ns,
    uint64_t* exec_ns,
    uint64_t* read_ns) {
  auto* s = static_cast<Session*>(handle);
  if (s == nullptr || send_ns == nullptr || exec_ns == nullptr ||
      read_ns == nullptr) {
    return -1;
  }
  std::lock_guard<std::mutex> lk(s->mu);
  *send_ns = s->last_send_ns;
  *exec_ns = s->last_exec_ns;
  *read_ns = s->last_read_ns;
  return 0;
}

void ane_inproc_close(ane_inproc_t handle) {
  auto* s = static_cast<Session*>(handle);
  if (s == nullptr) {
    return;
  }
  {
    std::lock_guard<std::mutex> lk(s->mu);
    if (s->quarantined) {
      // The submit thread may still be inside the ANE ioctl; it cannot
      // be killed safely and its Session must outlive it. Leak both,
      // bounded by process lifetime.
      return;
    }
    s->quit = true;
  }
  s->cv.notify_all();
  s->loop.join();
  s->device->release();
  delete s;
}

} // extern "C"

#endif // MLX_OMARCHY_ANE_DEVICE
