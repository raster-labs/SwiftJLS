#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Controls for the allocator mutation detector; no codec build is performed."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'StorageEvidence/mutate-copy.py'
SPEC = importlib.util.spec_from_file_location('copy_mutation', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CopyMutationClassifierTests(unittest.TestCase):
    marker = 'SwiftJLS.ScalarCodec.telemetryInjectedFrameCopy'
    array = 'generic specialization <Swift.UInt8> of Swift.Array.init(repeating: A, count: Swift.Int)'
    owner = 'SwiftJLS.OwnedImageStorage.init(byteCount: Swift.Int)'
    private_owner = 'SwiftJLS.OwnedImageStorage.(in _E3A3FF9B1E0185F10C196E0592093825).init(reservedByteCount: Swift.Int)'

    def classify(self, frames, count=10, analysis=None):
        if analysis is None:
            analysis = self.marker + '\nPEAK MEMORY CONSUMERS\n'
        return MODULE.classify_injected_copy(analysis, ';'.join(frames) + f'; {count}\n')

    def test_public_and_private_initialisers_are_detected(self):
        for owner in (self.owner, self.private_owner):
            with self.subTest(owner=owner):
                self.assertEqual(self.classify([self.marker, self.array, owner]), (True, 10))

    def test_helper_only_cannot_establish_a_pixel_array(self):
        self.assertEqual(self.classify([self.marker]), (False, 0))
        self.assertEqual(self.classify([self.marker, self.owner]), (False, 0))

    def test_array_without_exact_owner_is_rejected(self):
        for owner in ('SwiftJLS.OtherOwnedImageStorage.init(byteCount: Swift.Int)',
                      'SwiftJLS.OwnedImageStorageAdapter.init(byteCount: Swift.Int)',
                      'OtherSwiftJLS.OwnedImageStorage.init(byteCount: Swift.Int)',
                      'Other.SwiftJLS.OwnedImageStorage.init(byteCount: Swift.Int)',
                      'SwiftJLS.OwnedImageStorage.allocateReserved(byteCount: Swift.Int)',
                      'SwiftJLS.OwnedImageStorage.(in arbitrary_text).init(byteCount: Swift.Int)'):
            with self.subTest(owner=owner):
                self.assertEqual(self.classify([self.marker, self.array, owner]), (False, 0))

    def test_exact_ten_allocations_remain_required(self):
        for count in (0, 1, 9, 11):
            with self.subTest(count=count):
                self.assertEqual(self.classify([self.marker, self.array, self.private_owner], count), (False, count))

    def test_baseline_and_peak_section_symbol_are_not_detection(self):
        self.assertEqual(self.classify([self.array, self.owner], analysis='ordinary baseline\n'), (False, 0))
        self.assertEqual(self.classify([self.marker, self.array, self.private_owner],
                                      analysis='PEAK MEMORY CONSUMERS\n' + self.marker), (False, 10))

    def test_frames_must_belong_to_the_same_allocation_stack(self):
        stacks = self.marker + ';' + self.owner + '; 10\n' + self.array + '; 10\n'
        self.assertEqual(MODULE.classify_injected_copy(self.marker, stacks), (False, 0))


if __name__ == '__main__':
    unittest.main()
