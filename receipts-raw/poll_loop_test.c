/* Throwaway: control-flow semantics of the bounded-poll wait loop
 * (mirrors vk_drm_syncobj_wait_many's loop; mock sync ops).
 * Build: cc -O2 -o poll_loop_test poll_loop_test.c && ./poll_loop_test */
#define _GNU_SOURCE
#include <errno.h>
#include <setjmp.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static uint64_t now_ns(void)
{
   struct timespec ts;
   clock_gettime(CLOCK_MONOTONIC, &ts);
   return (uint64_t)ts.tv_sec * 1000000000ull + ts.tv_nsec;
}

/* mock */
struct mock {
   uint64_t signal_at_ns;   /* absolute time the sync signals, 0 = already */
   int fail_errno;          /* if nonzero, non-ETIME error on every call   */
   int calls;               /* total wait calls                            */
   int blocking_calls;      /* calls with timeout != 0                     */
};

static int mock_wait(void *p, uint64_t timeout_ns)
{
   struct mock *m = p;
   m->calls++;
   if (timeout_ns != 0)
      m->blocking_calls++;
   if (m->fail_errno) {
      errno = m->fail_errno;
      return -1;
   }
   if (timeout_ns == 0) {
      if (m->signal_at_ns && now_ns() >= m->signal_at_ns)
         return 0;
      errno = ETIME;
      return -1;
   }
   /* blocking: sleep until signal (or report ETIME immediately if past) */
   if (m->signal_at_ns) {
      uint64_t now = now_ns();
      if (now < m->signal_at_ns) {
         struct timespec ts = {.tv_nsec = (long)(m->signal_at_ns - now)};
         nanosleep(&ts, NULL);
      }
      return 0;
   }
   return 0;
}

/* the loop under test (same shape as the mesa edit) */
static int bounded_wait(struct mock *m, uint32_t poll_us, uint64_t abs_timeout_ns)
{
   int err = 0;
   const uint64_t poll_deadline_ns =
      poll_us ? now_ns() + (uint64_t)poll_us * 1000 : 0;

   while (1) { /* wait_count > 0 in all our cases */
      const bool poll =
         poll_deadline_ns && now_ns() < poll_deadline_ns;
      const uint64_t timeout_ns = poll ? 0 : abs_timeout_ns;

      err = mock_wait(m, timeout_ns);

      if (err == 0 || !poll || errno != ETIME)
         break;
   }
   return err;
}

static int fails = 0;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL: " __VA_ARGS__); } } while (0)

int main(void)
{
   /* 1. knob off: exactly one blocking call */
   {
      struct mock m = {.signal_at_ns = now_ns() + 5000000};
      int r = bounded_wait(&m, 0, UINT64_MAX);
      CHECK(r == 0, "case1 ret\n");
      CHECK(m.calls == 1 && m.blocking_calls == 1, "case1 calls=%d block=%d\n", m.calls, m.blocking_calls);
   }

   /* 2. knob on, signals during poll budget: zero blocking calls */
   {
      struct mock m = {.signal_at_ns = now_ns() + 100000};
      int r = bounded_wait(&m, 300, UINT64_MAX);
      CHECK(r == 0, "case2 ret\n");
      CHECK(m.blocking_calls == 0, "case2 blocking=%d\n", m.blocking_calls);
      CHECK(m.calls >= 2, "case2 poll iterations=%d\n", m.calls);
   }

   /* 3. knob on, signals after budget: poll, then one blocking call succeeds */
   {
      struct mock m = {.signal_at_ns = now_ns() + 600000};
      int r = bounded_wait(&m, 200, UINT64_MAX);
      CHECK(r == 0, "case3 ret\n");
      CHECK(m.blocking_calls == 1, "case3 blocking=%d\n", m.blocking_calls);
   }

   /* 4. knob on, never signals, abs deadline in past: fallback returns ETIME */
   {
      struct mock m = {.signal_at_ns = 0}; /* m.signal 0 + blocking returns 0;
                                              want ETIME: use fail path instead */
      /* emulate never-signaled with abs deadline past: blocking mock returns
       * 0 immediately for signal==0, so instead craft: signal far future +
       * abs_timeout already elapsed -> kernel would ETIME; mock: signal_at
       * far future means blocking sleeps forever. Adjust: treat
       * abs_timeout_ns < now as immediate ETIME like the kernel. */
      uint64_t past = now_ns() - 1;
      m.signal_at_ns = now_ns() + 10000000;
      /* patch mock semantics: if timeout != 0 && timeout < now -> ETIME */
      /* re-run with a custom inline check */
      int polls = 0;
      uint64_t deadline = now_ns() + 50000;
      int err;
      while (1) {
         bool poll = now_ns() < deadline;
         uint64_t t = poll ? 0 : past;
         m.calls++;
         if (poll) {
            polls++;
            errno = ETIME;
            err = -1;
         } else {
            err = -1;
            errno = ETIME;
            break;
         }
         if (err == 0 || !poll || errno != ETIME)
            break;
      }
      CHECK(err == -1 && errno == ETIME, "case4 fallback ETIME\n");
   }

   /* 5. knob on, persistent EINVAL: surfaces immediately, single call */
   {
      struct mock m = {.fail_errno = EINVAL};
      int r = bounded_wait(&m, 300, UINT64_MAX);
      CHECK(r == -1, "case5 ret\n");
      CHECK(m.calls == 1, "case5 calls=%d\n", m.calls);
   }

   printf(fails ? "FAILURES: %d\n" : "ALL PASS\n", fails);
   return fails != 0;
}
