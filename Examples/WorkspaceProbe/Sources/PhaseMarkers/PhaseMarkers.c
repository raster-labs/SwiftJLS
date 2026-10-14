// SPDX-License-Identifier: Apache-2.0
#include <stdlib.h>
#include "PhaseMarkers.h"
#if __has_include(<valgrind/valgrind.h>)
#include <valgrind/valgrind.h>
#endif
// Prevent tail-call elimination so an external allocator sees the named frame.
__attribute__((noinline,optnone)) void *swiftjls_workspace_begin(void) {
#if __has_include(<valgrind/valgrind.h>)
    if (RUNNING_ON_VALGRIND) VALGRIND_MONITOR_COMMAND("detailed_snapshot massif-begin.out");
#endif
    volatile void *p = malloc(1); return (void *)p;
}
__attribute__((noinline,optnone)) void *swiftjls_workspace_end(void) {
#if __has_include(<valgrind/valgrind.h>)
    if (RUNNING_ON_VALGRIND) VALGRIND_MONITOR_COMMAND("detailed_snapshot massif-end.out");
#endif
    volatile void *p = malloc(2); return (void *)p;
}
void swiftjls_workspace_release(void *p) { free(p); }
