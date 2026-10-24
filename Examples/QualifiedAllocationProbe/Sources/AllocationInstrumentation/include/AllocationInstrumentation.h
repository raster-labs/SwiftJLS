// SPDX-License-Identifier: Apache-2.0
#ifndef SWIFTJLS_ALLOCATION_INSTRUMENTATION_H
#define SWIFTJLS_ALLOCATION_INSTRUMENTATION_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint64_t malloc_calls, calloc_calls, realloc_calls, memalign_calls;
    uint64_t posix_memalign_calls, aligned_alloc_calls, valloc_calls, pvalloc_calls, reallocarray_calls;
    uint64_t free_calls, requested_bytes, overflow;
} SJLSAllocationCounts;
int sjls_allocation_supported(void);
int sjls_allocation_begin(void);
SJLSAllocationCounts sjls_allocation_end(void);
// Returns a nine-bit mask. Every allocation entry point has its own positive
// control, performed through a volatile function pointer to prevent elision.
uint32_t sjls_allocation_self_test(void);

typedef struct {
    uint64_t calls, cancel_after;
} SJLSCancellationState;
bool sjls_probe_cancel(void *context);
#endif
