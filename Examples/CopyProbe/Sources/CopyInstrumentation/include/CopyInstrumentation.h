// SPDX-License-Identifier: Apache-2.0
#include <stddef.h>
#include <stdint.h>
int sjls_copy_probe_self_test(void);
void sjls_copy_probe_begin(const void *base, size_t size);
void sjls_copy_probe_end(void);
void sjls_copy_probe_reset(void);
uint64_t sjls_copy_probe_bytes(void);
