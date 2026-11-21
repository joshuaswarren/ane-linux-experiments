// hwx_normalise.cpp — post-compile normaliser for Apple ANECCompile H16/H17 containers.
//
// ANECCompile's H17 output is refused by the Linux ane driver's load validator
// (drivers/accel/ane/ane_h16_hwx.c + ane_h16_tasks.h, aurora ddd95a7af8fc2).
// This pass rewrites the container to what that validator accepts:
//   1. __TEXT segment flags word: ANECCompile writes 4, driver requires 0.
//   2. Drops the compiler's opcode 0x31 "rt.version" note (unknown to the driver).
//      Every file-absolute offset past the removed command is shifted.
//   3. Rebuilds the program base table in segment order at +0x70 (u64 vm + zero
//      tail per slot, kernel section slot next, rest zero) and zeroes +0x60.
//   4. Program +0x880 = 0x461c4000, the driver's expected trailer constant
//      (non-mixed 0x8a0 programs only; mixed 0x8c0 is refused here).
//   5. Task-stream prologue word: 0 for H17 subtype, 1 for H16.
//   6. Symbol table: keeps only Mach-O section symbols (type 0xe/0xf with a
//      nonzero section index); stabs and debug entries are dropped.
// The task stream after the prologue word and every file-backed weight byte are
// left exactly as the compiler wrote them.
//
// Usage: hwx_normalise FILE.hwx        (normalises in place)
// Exit 0 = normalised; nonzero = error, file left unchanged.

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace {

constexpr uint32_t kMagic = 0xbeefface;
constexpr uint32_t kSubtypeH16 = 7;
constexpr uint32_t kSubtypeH17 = 9;
constexpr uint32_t kTextSegFlags = 0;      // driver wants 0 on __TEXT
constexpr uint32_t kTrailerConstant = 0x461c4000;
constexpr uint32_t kProgramLen = 0x8a0;    // non-mixed program command length

uint32_t le32(const uint8_t* b, size_t o) {
  return uint32_t(b[o]) | uint32_t(b[o + 1]) << 8 | uint32_t(b[o + 2]) << 16 |
         uint32_t(b[o + 3]) << 24;
}

uint64_t le64(const uint8_t* b, size_t o) {
  return uint64_t(le32(b, o)) | uint64_t(le32(b, o + 4)) << 32;
}

void put32(uint8_t* b, size_t o, uint32_t v) {
  b[o] = v & 0xff;
  b[o + 1] = (v >> 8) & 0xff;
  b[o + 2] = (v >> 16) & 0xff;
  b[o + 3] = (v >> 24) & 0xff;
}

void put64(uint8_t* b, size_t o, uint64_t v) {
  put32(b, o, uint32_t(v));
  put32(b, o + 4, uint32_t(v >> 32));
}

struct SectionRef {
  size_t header;     // file offset of the 80-byte section header
  uint32_t offset;   // section offset field
  uint32_t reloff;
};

struct SegmentRef {
  size_t header;     // file offset of the 0x19 command
  uint64_t file;     // segment file-offset field
};

int fail(const std::string& what) {
  std::fprintf(stderr, "hwx_normalise: %s\n", what.c_str());
  return 1;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    std::fprintf(stderr, "usage: hwx_normalise FILE.hwx\n");
    return 2;
  }
  const char* path = argv[1];
  std::FILE* f = std::fopen(path, "rb");
  if (!f) return fail("cannot open file");
  std::vector<uint8_t> b;
  uint8_t buf[65536];
  size_t n;
  while ((n = std::fread(buf, 1, sizeof(buf), f)) > 0)
    b.insert(b.end(), buf, buf + n);
  std::fclose(f);

  // ---- Phase A: parse, collect everything the fixes need. ----
  if (b.size() < 32) return fail("file too small");
  if (le32(b.data(), 0) != kMagic) return fail("magic is not 0xbeefface");
  const uint32_t subtype = le32(b.data(), 8);
  if (subtype != kSubtypeH16 && subtype != kSubtypeH17)
    return fail("subtype is neither H16 (7) nor H17 (9)");
  const uint32_t count = le32(b.data(), 16);
  const uint32_t length = le32(b.data(), 20);
  const size_t command_end = 32 + size_t(length);

  size_t text_seg = 0, program = 0, symtab = 0;
  bool have_text_seg = false, have_program = false, have_symtab = false;
  std::vector<size_t> notes;             // opcode 0x31 positions
  std::vector<uint32_t> note_lens;       // their command lengths, before edits
  size_t last_annotation = 0;            // annotation command ending latest
  std::vector<uint64_t> surface_vms;     // segment order
  uint64_t kernel_vm = 0;
  std::vector<SectionRef> sections;
  std::vector<SegmentRef> file_backed;   // segments with a file range
  size_t text_data_off = 0, text_data_size = 0;

  size_t pos = 32;
  for (uint32_t i = 0; i < count; ++i) {
    if (pos + 8 > command_end) return fail("command header past command area");
    const uint32_t cmd = le32(b.data(), pos);
    const uint32_t len = le32(b.data(), pos + 4);
    if (len < 8 || (len & 7) || pos + len > command_end)
      return fail("command length invalid");
    if (cmd == 0x19) {
      const bool is_text = std::memcmp(b.data() + pos + 8, "__TEXT", 6) == 0 &&
                           b[pos + 14] == 0;
      if (is_text) {
        text_seg = pos;
        have_text_seg = true;
        file_backed.push_back({pos, le64(b.data(), pos + 40)});
        const uint32_t nsects = le32(b.data(), pos + 64);
        for (uint32_t s = 0; s < nsects; ++s) {
          const size_t so = pos + 72 + s * 80;
          sections.push_back({so, le32(b.data(), so + 48),
                              le32(b.data(), so + 56)});
          if (std::memcmp(b.data() + so, "__text", 6) == 0 && b[so + 6] == 0) {
            text_data_off = le32(b.data(), so + 48);
            text_data_size = le64(b.data(), so + 40);
          }
        }
      } else if (std::memcmp(b.data() + pos + 8, "__KERN_0", 8) == 0) {
        kernel_vm = le64(b.data(), pos + 24);
        file_backed.push_back({pos, le64(b.data(), pos + 40)});
        const uint32_t nsects = le32(b.data(), pos + 64);
        for (uint32_t s = 0; s < nsects; ++s)
          sections.push_back({pos + 72 + s * 80,
                              le32(b.data(), pos + 72 + s * 80 + 48),
                              le32(b.data(), pos + 72 + s * 80 + 56)});
      } else if (std::memcmp(b.data() + pos + 8, "__FVMLIB", 8) == 0) {
        surface_vms.push_back(le64(b.data(), pos + 24));
      }
    } else if (cmd == 0x31) {
      notes.push_back(pos);
      note_lens.push_back(len);
      if (le32(b.data(), last_annotation) != 8 || last_annotation == 0)
        return fail("note is not preceded by an annotation");
    } else if (cmd == 8) {
      last_annotation = pos;
    } else if (cmd == 4 && le32(b.data(), pos + 8) == 4) {
      program = pos;
      have_program = true;
    } else if (cmd == 2) {
      symtab = pos;
      have_symtab = true;
    }
    pos += len;
  }
  if (!have_text_seg) return fail("no __TEXT segment");
  if (!have_program) return fail("no program command");
  if (!have_symtab) return fail("no symbol table command");
  if (surface_vms.size() < 2) return fail("fewer than two surfaces");
  if (le32(b.data(), program + 4) != kProgramLen)
    return fail("program command is not the 0x8a0 non-mixed layout");
  if (text_data_off == 0 || text_data_size < 16)
    return fail("no file-backed __text section");

  // ---- Phase B: in-place field fixes (no size changes). ----
  put32(b.data(), text_seg + 68, kTextSegFlags);

  put32(b.data(), text_data_off,
        subtype == kSubtypeH17 ? 0u : 1u);  // task-stream prologue word

  // Base table: segment order at +0x70, kernel slot after the surfaces.
  for (size_t slot = 0; slot < 5; ++slot) {
    const uint64_t v = slot < surface_vms.size() ? surface_vms[slot]
                       : slot == surface_vms.size() ? kernel_vm : 0;
    put64(b.data(), program + 0x70 + slot * 16, v);
    put64(b.data(), program + 0x78 + slot * 16, 0);
  }
  std::memset(b.data() + program + 0x60, 0, 0x10);
  put32(b.data(), program + 0x880, kTrailerConstant);

  // Symbol compaction: keep section symbols, drop stabs and debug entries.
  uint32_t kept_syms = 0;
  {
    const uint32_t nsyms = le32(b.data(), symtab + 12);
    const size_t symoff = le32(b.data(), symtab + 8);
    std::vector<uint8_t> kept;
    for (uint32_t i = 0; i < nsyms; ++i) {
      const size_t s = symoff + i * 16;
      const uint8_t type = b[s + 4];
      const uint8_t sect = b[s + 5];
      if ((type & ~1u) == 0xe && sect != 0)
        kept.insert(kept.end(), b.begin() + s, b.begin() + s + 16);
    }
    if (kept.empty()) return fail("no section symbols survived compaction");
    std::memcpy(b.data() + symoff, kept.data(), kept.size());
    std::memset(b.data() + symoff + kept.size(), 0,
                size_t(nsyms) * 16 - kept.size());
    kept_syms = uint32_t(kept.size() / 16);
    put32(b.data(), symtab + 12, kept_syms);
  }

  // ---- Phase C: fold every 0x31 note into the annotation command right
  // before it. The driver's annotation rule is "NUL-terminated string, all
  // zero bytes after it, len <= 4096 and a multiple of 8", so extending the
  // annotation over the note and zeroing the note bytes keeps every other
  // byte of the file in place (no offset shifts, no alignment breakage).
  
  for (size_t i = 0; i < notes.size(); ++i) {
    const size_t note = notes[i];
    const uint32_t note_len = note_lens[i];
    const uint32_t prev_len = le32(b.data(), last_annotation + 4);
    if (last_annotation + prev_len != note)
      return fail("annotation does not end at the note");
    if (prev_len + note_len > 4096)
      return fail("merged annotation would exceed 4096 bytes");
    std::memset(b.data() + note, 0, note_len);
    put32(b.data(), last_annotation + 4, prev_len + note_len);
  }
  // The command area keeps its size: the note bytes are inside the grown
  // annotation, and the symtab physically follows the merged annotation.
  // Only the command count drops.
  put32(b.data(), 16, count - uint32_t(notes.size()));

  // ---- Phase D: write back. ----
  f = std::fopen(path, "wb");
  if (!f) return fail("cannot reopen file for write");
  if (std::fwrite(b.data(), 1, b.size(), f) != b.size()) {
    std::fclose(f);
    return fail("short write");
  }
  if (std::fclose(f) != 0) return fail("close failed");
  std::printf("hwx_normalise: %zu note command(s) removed, %u symbols kept, "
              "wrote %zu bytes\n",
              notes.size(), kept_syms, b.size());
  return 0;
}
