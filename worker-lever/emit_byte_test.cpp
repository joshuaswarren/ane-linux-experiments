// emit_byte_test.cpp — standalone failing-first byte-equivalence test for
// the per-output flush lever (LEVER_BUFFERED_DRAIN analog in worker).
//
// Compares two modes of stdout emission from the worker's resident-serve
// submit loop:
//   BASE  : per-output printf+fflush + fwrite+fflush + trailing printf+fflush
//   LEVER : setvbuf(stdout, _IONBF, 0) + per-output printf+fwrite + trailing printf
//
// Both modes capture their full stdout to a pipe via stdout redirection.
// Then we byte-compare captured streams. Failing-first: any byte difference
// or order difference fails the test.

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <string>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <vector>


// Build a payload vector with a recognizable pattern
static std::vector<uint8_t> make_payload(uint8_t fill, size_t len) {
    return std::vector<uint8_t>(len, fill);
}


// === Base behavior: per-output fflush (current worker) ===
static void emit_loop_base(FILE* f, int n_rounds) {
    // Round A: 2 outputs (attention_scores_1, matmul_0)
    // Round C: 1 output (attn_output_1)
    auto pa1 = make_payload(0xAA, 16);
    auto pa2 = make_payload(0xBB, 16);
    auto pc1 = make_payload(0xCC, 16);
    for (int r = 0; r < n_rounds; r++) {
        size_t out_bytes = 0;
        if (r % 2 == 0) {
            std::fprintf(f, "out %s %zu\n", "attention_scores_1", pa1.size());
            std::fflush(f);
            std::fwrite(pa1.data(), 1, pa1.size(), f);
            std::fflush(f);
            std::fprintf(f, "out %s %zu\n", "matmul_0", pa2.size());
            std::fflush(f);
            std::fwrite(pa2.data(), 1, pa2.size(), f);
            std::fflush(f);
            out_bytes = pa1.size() + pa2.size();
        } else {
            std::fprintf(f, "out %s %zu\n", "attn_output_1", pc1.size());
            std::fflush(f);
            std::fwrite(pc1.data(), 1, pc1.size(), f);
            std::fflush(f);
            out_bytes = pc1.size();
        }
        std::fprintf(f,
                     "job status=0 bundle=%s elapsed_ms=%lld iterations=%d "
                     "input_bytes=%zu output_bytes=%zu stage_ms=%lld save_ms=%lld\n",
                     "test-bundle", 18LL, 1, size_t(0), out_bytes, 4LL, 6LL);
        std::fflush(f);
    }
}


// === Lever behavior: setvbuf _IONBF + drop per-output fflush ===
static void emit_loop_lever(FILE* f, int n_rounds) {
    // Use _IONBF: every write goes straight to the kernel via write()
    std::setvbuf(f, nullptr, _IONBF, 0);
    auto pa1 = make_payload(0xAA, 16);
    auto pa2 = make_payload(0xBB, 16);
    auto pc1 = make_payload(0xCC, 16);
    for (int r = 0; r < n_rounds; r++) {
        size_t out_bytes = 0;
        if (r % 2 == 0) {
            std::fprintf(f, "out %s %zu\n", "attention_scores_1", pa1.size());
            std::fwrite(pa1.data(), 1, pa1.size(), f);
            std::fprintf(f, "out %s %zu\n", "matmul_0", pa2.size());
            std::fwrite(pa2.data(), 1, pa2.size(), f);
            out_bytes = pa1.size() + pa2.size();
        } else {
            std::fprintf(f, "out %s %zu\n", "attn_output_1", pc1.size());
            std::fwrite(pc1.data(), 1, pc1.size(), f);
            out_bytes = pc1.size();
        }
        std::fprintf(f,
                     "job status=0 bundle=%s elapsed_ms=%lld iterations=%d "
                     "input_bytes=%zu output_bytes=%zu stage_ms=%lld save_ms=%lld\n",
                     "test-bundle", 18LL, 1, size_t(0), out_bytes, 4LL, 6LL);
        // No fflush: _IONBF makes every write a syscall.
    }
}


// Capture stdout via pipe redirect. Returns full bytes written to stdout.
static std::vector<uint8_t> capture_emit(const std::string& mode, int n_rounds) {
    int pipefd[2];
    assert(pipe(pipefd) == 0);
    fflush(stdout);
    int saved_stdout = dup(STDOUT_FILENO);
    assert(dup2(pipefd[1], STDOUT_FILENO) != -1);
    close(pipefd[1]);

    FILE* f = fdopen(STDOUT_FILENO, "w");
    assert(f != nullptr);

    if (mode == "base") emit_loop_base(f, n_rounds);
    else if (mode == "lever") emit_loop_lever(f, n_rounds);
    else { assert(false); }

    fflush(f);
    dup2(saved_stdout, STDOUT_FILENO);
    close(saved_stdout);

    std::vector<uint8_t> captured;
    uint8_t buf[8192];
    while (true) {
        ssize_t n = read(pipefd[0], buf, sizeof(buf));
        if (n <= 0) break;
        captured.insert(captured.end(), buf, buf + n);
    }
    close(pipefd[0]);
    return captured;
}


int main() {
    int n_rounds = 48;
    auto base_bytes = capture_emit("base", n_rounds);
    auto lever_bytes = capture_emit("lever", n_rounds);

    printf("=== Captured %zu bytes (base), %zu bytes (lever) ===\n",
           base_bytes.size(), lever_bytes.size());
    if (base_bytes.size() != lever_bytes.size()) {
        fprintf(stderr, "FAIL: byte count differs: base=%zu, lever=%zu\n",
                base_bytes.size(), lever_bytes.size());
        // Dump first 200 bytes of each for diff
        fprintf(stderr, "FIRST 200 BYTES OF BASE:\n");
        for (size_t i = 0; i < std::min<size_t>(200, base_bytes.size()); i++) {
            fprintf(stderr, "%02x ", base_bytes[i]);
            if ((i+1) % 16 == 0) fprintf(stderr, "\n");
        }
        fprintf(stderr, "\nFIRST 200 BYTES OF LEVER:\n");
        for (size_t i = 0; i < std::min<size_t>(200, lever_bytes.size()); i++) {
            fprintf(stderr, "%02x ", lever_bytes[i]);
            if ((i+1) % 16 == 0) fprintf(stderr, "\n");
        }
        return 1;
    }
    if (base_bytes != lever_bytes) {
        fprintf(stderr, "FAIL: byte content differs\n");
        for (size_t i = 0; i < base_bytes.size(); i++) {
            if (base_bytes[i] != lever_bytes[i]) {
                fprintf(stderr, "  first diff at byte %zu: base=0x%02x lever=0x%02x\n",
                        i, base_bytes[i], lever_bytes[i]);
                break;
            }
        }
        return 1;
    }

    // Spot-check counts
    auto count_substr = [](const std::vector<uint8_t>& v, const std::string& s) {
        size_t count = 0;
        for (size_t i = 0; i + s.size() <= v.size(); i++) {
            if (memcmp(v.data() + i, s.data(), s.size()) == 0) count++;
        }
        return count;
    };
    size_t base_out = count_substr(base_bytes, "out ");
    size_t base_status = count_substr(base_bytes, "job status=");
    size_t lever_out = count_substr(lever_bytes, "out ");
    size_t lever_status = count_substr(lever_bytes, "job status=");

    printf("base:   %zu 'out ' headers, %zu 'job status=' lines\n", base_out, base_status);
    printf("lever: %zu 'out ' headers, %zu 'job status=' lines\n", lever_out, lever_status);

    // Expected: 24 A-rounds * 2 + 24 C-rounds * 1 = 72 out headers; 48 job status
    if (base_out != 72 || lever_out != 72) {
        fprintf(stderr, "FAIL: out count: expected 72, got base=%zu lever=%zu\n",
                base_out, lever_out);
        return 1;
    }
    if (base_status != 48 || lever_status != 48) {
        fprintf(stderr, "FAIL: job status count: expected 48, got base=%zu lever=%zu\n",
                base_status, lever_status);
        return 1;
    }

    printf("=== ALL BYTE-EQUIVALENCE INVARIANTS PASS ===\n");
    printf("base_bytes.size() == lever_bytes.size() == %zu\n", base_bytes.size());
    printf("base_bytes == lever_bytes (every byte, in order)\n");
    return 0;
}
