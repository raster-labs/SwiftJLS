# SPDX-License-Identifier: Apache-2.0
"""Negative controls for the release evidence admission checks."""
import copy
import unittest

from prepare import check_pin, swift_example


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.url = "file:///temporary/SwiftJLS.git"
        self.sha = "a" * 40
        self.pin = {"identity": "swiftjls", "location": self.url,
                    "state": {"revision": self.sha, "version": "1.1.0-dev.2"}}

    def test_accepts_exact_version_and_revision(self):
        self.assertEqual(check_pin({"pins": [self.pin]}, self.sha, "1.1.0-dev.2", self.url), self.pin)

    def test_rejects_stale_version_revision_location_and_branch(self):
        for key, value in (("version", "1.1.0-dev.1"), ("revision", "b" * 40), ("branch", "main")):
            with self.subTest(key=key):
                pin = copy.deepcopy(self.pin)
                pin["state"][key] = value
                with self.assertRaises(ValueError):
                    check_pin({"pins": [pin]}, self.sha, "1.1.0-dev.2", self.url)
        with self.assertRaises(ValueError):
            check_pin({"pins": [self.pin]}, self.sha, "1.1.0-dev.2", "https://example.invalid/SwiftJLS.git")

    def test_rejects_missing_or_extra_dependencies(self):
        for pins in ([], [self.pin, self.pin]):
            with self.assertRaises(ValueError):
                check_pin({"pins": pins}, self.sha, "1.1.0-dev.2", self.url)

    def test_revision_consumption_cannot_hide_version_pin(self):
        with self.assertRaises(ValueError):
            check_pin({"pins": [self.pin]}, self.sha, None, self.url)
        pin = copy.deepcopy(self.pin)
        del pin["state"]["version"]
        check_pin({"pins": [pin]}, self.sha, None, self.url)

    def test_documentation_extraction_is_exact_and_rejects_drift(self):
        text = 'Text\n```swift\nimport SwiftJLS\n```\n'
        self.assertEqual(swift_example(text), 'import SwiftJLS\n')
        for invalid in ("No example", text + text):
            with self.assertRaises(ValueError):
                swift_example(invalid)


if __name__ == "__main__":
    unittest.main()
