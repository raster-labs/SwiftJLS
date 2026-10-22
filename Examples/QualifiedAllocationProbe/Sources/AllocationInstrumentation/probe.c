// SPDX-License-Identifier: Apache-2.0
// Development-only glibc executable symbol interposition. No production target
// depends on this code. Internal glibc entry points avoid recursive dlsym work.
#define _GNU_SOURCE 1
#include "AllocationInstrumentation.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#if defined(__linux__)
#include <features.h>
#endif
#if defined(__linux__) && defined(__GLIBC__)
#include <malloc.h>
#include <unistd.h>
extern void *__libc_malloc(size_t);
extern void *__libc_calloc(size_t, size_t);
extern void *__libc_realloc(void *, size_t);
extern void *__libc_memalign(size_t, size_t);
extern void __libc_free(void *);
static _Thread_local int enabled;
static _Thread_local SJLSAllocationCounts counts;

static void observe(uint64_t *counter, size_t bytes) {
    if (!enabled) return;
    if (*counter == UINT64_MAX) counts.overflow = 1; else ++*counter;
    if (bytes > UINT64_MAX - counts.requested_bytes) counts.overflow = 1;
    else counts.requested_bytes += bytes;
}
static size_t product(size_t a, size_t b) {
    if (a && b > SIZE_MAX / a) { if (enabled) counts.overflow = 1; return SIZE_MAX; }
    return a * b;
}
void *malloc(size_t n) { observe(&counts.malloc_calls, n); return __libc_malloc(n); }
void *calloc(size_t a, size_t b) { observe(&counts.calloc_calls, product(a, b)); return __libc_calloc(a, b); }
void *realloc(void *p, size_t n) { observe(&counts.realloc_calls, n); return __libc_realloc(p, n); }
void free(void *p) { if (enabled) ++counts.free_calls; __libc_free(p); }
void *memalign(size_t a, size_t n) { observe(&counts.memalign_calls, n); return __libc_memalign(a, n); }
int posix_memalign(void **p, size_t a, size_t n) {
    observe(&counts.posix_memalign_calls, n);
    if (a < sizeof(void *) || (a & (a - 1))) return EINVAL;
    int saved = errno;
    void *result = __libc_memalign(a, n);
    errno = saved;
    if (!result) return ENOMEM;
    *p = result; return 0;
}
void *aligned_alloc(size_t a, size_t n) {
    observe(&counts.aligned_alloc_calls, n);
    return __libc_memalign(a, n);
}
void *valloc(size_t n) {
    observe(&counts.valloc_calls, n);
    return __libc_memalign((size_t)getpagesize(), n);
}
void *pvalloc(size_t n) {
    observe(&counts.pvalloc_calls, n);
    size_t page = (size_t)getpagesize();
    if (n > SIZE_MAX - (page - 1)) { errno = ENOMEM; return NULL; }
    size_t rounded = n ? (n + page - 1) & ~(page - 1) : page;
    return __libc_memalign(page, rounded);
}
void *reallocarray(void *p, size_t a, size_t b) {
    size_t n = product(a, b); observe(&counts.reallocarray_calls, n);
    if (a && b > SIZE_MAX / a) { errno = ENOMEM; return NULL; }
    return __libc_realloc(p, n);
}
int sjls_allocation_supported(void) { return 1; }
int sjls_allocation_begin(void) {
    if (enabled) return 0;
    counts = (SJLSAllocationCounts){0}; enabled = 1; return 1;
}
SJLSAllocationCounts sjls_allocation_end(void) { enabled = 0; return counts; }

// Volatile indirection and observable stores keep these controls in optimised
// builds. A separate scope per symbol prevents another allocator masking a miss.
__attribute__((noinline)) uint32_t sjls_allocation_self_test(void) {
    void *(*volatile m)(size_t) = malloc;
    void *(*volatile c)(size_t, size_t) = calloc;
    void *(*volatile r)(void *, size_t) = realloc;
    void *(*volatile ma)(size_t, size_t) = memalign;
    int (*volatile pm)(void **, size_t, size_t) = posix_memalign;
    void *(*volatile aa)(size_t, size_t) = aligned_alloc;
    void *(*volatile va)(size_t) = valloc;
    void *(*volatile pv)(size_t) = pvalloc;
    void *(*volatile ra)(void *, size_t, size_t) = reallocarray;
    uint32_t mask = 0; void *p; SJLSAllocationCounts s;
#define FINISH(bit, field, amount) do { \
    if (p) *(volatile unsigned char *)p = 0x5a; \
    s = sjls_allocation_end(); \
    if (p && s.field == 1 && s.requested_bytes == (amount) && !s.overflow) mask |= (1u << (bit)); \
    free(p); \
} while (0)
    sjls_allocation_begin(); p = m(41); FINISH(0, malloc_calls, 41);
    sjls_allocation_begin(); p = c(7, 9); FINISH(1, calloc_calls, 63);
    p = m(17); sjls_allocation_begin(); p = r(p, 73); FINISH(2, realloc_calls, 73);
    sjls_allocation_begin(); p = ma(64, 71); FINISH(3, memalign_calls, 71);
    p = NULL; sjls_allocation_begin(); int status = pm(&p, 64, 91); FINISH(4, posix_memalign_calls, 91);
    if (status) mask &= ~(1u << 4);
    sjls_allocation_begin(); p = aa(64, 128); FINISH(5, aligned_alloc_calls, 128);
    sjls_allocation_begin(); p = va(83); FINISH(6, valloc_calls, 83);
    sjls_allocation_begin(); p = pv(89); FINISH(7, pvalloc_calls, 89);
    p = m(17); sjls_allocation_begin(); p = ra(p, 7, 19); FINISH(8, reallocarray_calls, 133);
#undef FINISH
    return mask;
}
#else
int sjls_allocation_supported(void) { return 0; }
int sjls_allocation_begin(void) { return 0; }
SJLSAllocationCounts sjls_allocation_end(void) { return (SJLSAllocationCounts){0}; }
uint32_t sjls_allocation_self_test(void) { return 0; }
#endif

bool sjls_probe_cancel(void *context) {
    SJLSCancellationState *state = context;
    if (!state) return false;
    ++state->calls;
    return state->cancel_after && state->calls >= state->cancel_after;
}
