// SPDX-License-Identifier: Apache-2.0
// Development-only Linux executable symbol interposition. No production target
// depends on this code. Ranges are registered only during synchronous borrows.
#include "CopyInstrumentation.h"
#include <dlfcn.h>
#include <pthread.h>
#include <string.h>
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static uintptr_t first, last;
static uint64_t copied;
static void observe(const void *source, size_t size) {
    uintptr_t begin = (uintptr_t)source;
    if (size > UINTPTR_MAX - begin) return;
    uintptr_t end = begin + size;
    pthread_mutex_lock(&lock);
    uintptr_t lo = begin > first ? begin : first, hi = end < last ? end : last;
    if (lo < hi) copied += hi - lo;
    pthread_mutex_unlock(&lock);
}
void sjls_copy_probe_begin(const void *base, size_t size) {
    pthread_mutex_lock(&lock); first = (uintptr_t)base; last = first + size; pthread_mutex_unlock(&lock);
}
void sjls_copy_probe_end(void) {
    pthread_mutex_lock(&lock); first = last = 0; pthread_mutex_unlock(&lock);
}
void sjls_copy_probe_reset(void) {
    pthread_mutex_lock(&lock); copied = 0; pthread_mutex_unlock(&lock);
}
uint64_t sjls_copy_probe_bytes(void) {
    pthread_mutex_lock(&lock); uint64_t value = copied; pthread_mutex_unlock(&lock); return value;
}
#ifdef __linux__
// The fallback is also safe while dlsym is resolving itself. Volatile scalar
// accesses prevent the compiler turning this fallback into a recursive memcpy.
static void *fallback(void *destination, const void *source, size_t size) {
    volatile unsigned char *d = destination;
    const volatile unsigned char *s = source;
    if ((uintptr_t)d < (uintptr_t)s) { for (size_t i = 0; i < size; ++i) d[i] = s[i]; }
    else { for (size_t i = size; i > 0; --i) d[i - 1] = s[i - 1]; }
    return destination;
}
typedef void *(*copy_fn)(void *, const void *, size_t);
static copy_fn actual_memcpy, actual_memmove;
__attribute__((constructor)) static void initialise(void) {
    actual_memcpy = (copy_fn)dlsym(RTLD_NEXT, "memcpy");
    actual_memmove = (copy_fn)dlsym(RTLD_NEXT, "memmove");
}
void *memcpy(void *destination, const void *source, size_t size) {
    observe(source, size);
    return actual_memcpy ? actual_memcpy(destination, source, size) : fallback(destination, source, size);
}
void *memmove(void *destination, const void *source, size_t size) {
    observe(source, size);
    return actual_memmove ? actual_memmove(destination, source, size) : fallback(destination, source, size);
}
#endif
int sjls_copy_probe_self_test(void) {
#ifdef __linux__
    unsigned char source[64], destination[64];
    for (size_t i = 0; i < 64; ++i) source[i] = (unsigned char)i;
    sjls_copy_probe_reset(); sjls_copy_probe_begin(source, 64);
    memmove(destination, source, 64); sjls_copy_probe_end();
    int passed = sjls_copy_probe_bytes() >= 64 && memcmp(source, destination, 64) == 0;
    sjls_copy_probe_reset(); return passed;
#else
    return 0;
#endif
}
