#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Classify observed allocator stacks for the strict scalar shared-storage route.

This is allocation evidence plus an explicit source review, not a memcpy tracer.
The separately executed injected-copy experiment proves sample-array sensitivity.
"""
import argparse,collections,hashlib,json,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--heap',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
raw=(a.heap/'allocation-stacks.txt').read_bytes()
stacks=subprocess.run(['swift','demangle'],input=raw,capture_output=True,check=True).stdout.decode()
groups=collections.Counter();details=[];forbidden=[]
for line in stacks.splitlines():
 frames,count=line.rsplit(';',1);count=int(count)
 if 'SwiftJLS.' not in frames:continue
 in_codec='SwiftJLS.ScalarCodec.encode' in frames or 'SwiftJLS.ScalarCodec.decode' in frames
 pixel='SwiftJLS.OwnedImageStorage.init' in frames and 'Swift.Array.init(repeating:' in frames
 if in_codec and pixel:forbidden.append(dict(stack=frames,count=count))
 if pixel:group='caller-created pixel owners (outside codec boundaries)'
 elif 'SwiftJLS.JPEGLSContextModel' in frames:group='bounded entropy contexts'
 elif 'SwiftJLS.JPEGLSRegularMode' in frames:group='bounded gradient tables'
 elif 'SwiftJLS.JPEGLSBitstreamWriter' in frames:group='compressed output writer and final Data'
 elif 'SwiftJLS.JPEGLSHeader' in frames or 'SwiftJLS.ImageDescriptor' in frames:group='validated header and descriptor containers'
 elif 'SwiftJLS.JPEGMetadataEncoding' in frames:group='metadata validation containers'
 elif 'SwiftJLS.OwnedImageStorage' in frames or 'SwiftJLS.ImageDestination' in frames:group='owner and lease control/error allocations'
 elif 'SwiftJLS.ResourceLimits' in frames:group='resource configuration containers'
 elif 'SwiftJLS.ScalarCodec' in frames:group='codec boundary values, closures and errors (not byte-count classified)'
 else:group='caller/runtime stacks referencing SwiftJLS types'
 groups[group]+=count;details.append(dict(category=group,count=count,stack=frames))
report=dict(profile_sha256=hashlib.sha256((a.heap/'allocations.gz').read_bytes()).hexdigest(),
 allocation_stack_count=len(details),allocation_calls=sum(groups.values()),groups=dict(groups),
 full_sample_arrays_under_encode_or_caller_decode=sum(x['count'] for x in forbidden),
 scope='37x23 12/16-bit scalar lossless real cross-codec routes, ordinary release, including cancellation and concurrent reads; no source changes since 2d027cf.',
 limitations=['Whole-process counts include setup/runtime. Stack classification does not measure arbitrary memcpy bytes.',
 'No broad component/metadata allocator or controlled peak-workspace qualification is inferred.'],
 source_review=['IntoJLS and IntoJ2K adapters forward scoped borrows directly without allocating or repacking samples.',
 'ScalarSampleReader/Writer retain only borrowed pointer and layout values.',
 'Scalar lossless kernels read the source owner and reconstruct in the final caller destination; no full sample array is created.',
 'Parser/header, gradient/context and compressed-data allocations are not decoded-image hand-off storage.'])
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
a.output.with_suffix('.stacks.json').write_text(json.dumps(details,indent=2)+'\n')
if forbidden:raise SystemExit('Unexpected pixel allocation inside strict shared-storage codec boundary')
print(json.dumps(report,indent=2))
