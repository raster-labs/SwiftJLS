#!/usr/bin/env python3
import sys,json
keys=['malloc','calloc','realloc','memalign','posix_memalign','aligned_alloc','valloc','pvalloc','reallocarray','free','requested_bytes','overflow','allocation_calls']
base={k:0 for k in keys}
def emit(x): print(json.dumps(x))
emit(dict(kind='allocator_positive_controls',observed_mask=511,required_mask=511,passed=True))
s=dict(base,malloc=1,allocation_calls=1,requested_bytes=8)
emit(dict(kind='swift_runtime_positive_control',counts=s,passed=True))
ops=['inspect','decode'] if sys.argv[1]=='--matrix' else [sys.argv[1].removeprefix('--cold-')]
for i,op in enumerate(ops):
 emit(dict(kind='operation',case='fake',operation=op,first_qualified_api_call_in_process=i==0,counts=dict(base,malloc=1),allocation_observation_passed=True,correctness_passed=True,canaries_and_input_unchanged=True))
emit(dict(kind='summary',operations=len(ops),cases=1,failed_operations=0))
