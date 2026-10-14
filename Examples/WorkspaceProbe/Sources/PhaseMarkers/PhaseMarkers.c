// SPDX-License-Identifier: Apache-2.0
#include <stdlib.h>
#include "PhaseMarkers.h"
// Prevent tail-call elimination so an external allocator sees the named frame.
__attribute__((noinline,optnone)) void *swiftjls_workspace_begin(void) {
    volatile void *p = malloc(1); return (void *)p;
}
__attribute__((noinline,optnone)) void *swiftjls_workspace_end(void) {
    volatile void *p = malloc(2); return (void *)p;
}
void swiftjls_workspace_release(void *p) { free(p); }
