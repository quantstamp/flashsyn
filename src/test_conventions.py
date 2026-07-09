"""Unit tests for conventions.check_placeholder_count — the $$ / numInputs
contract between an action's Solidity and its declared parameter count.

Pure Python, no forge. From the repo root:
    python3 -m unittest src/test_conventions.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # src/

from conventions import check_placeholder_count, extract_preamble  # noqa: E402


# A harness preamble followed by the two kinds of trailing function the engine
# needs sliced off: an authored testExample and a generated helper.
_PREAMBLE = (
    "// SPDX\ncontract X {\n"
    "    function setUp() public { vm.startPrank(attacker); }\n"
    "    function profitSummary() public view returns (string memory) { return \"FlashSyn\"; }\n"
)


class ExtractPreambleTest(unittest.TestCase):
    def _assert_is_the_preamble(self, harness, result):
        # Intent: the preamble is a prefix of the harness that keeps setUp/
        # profitSummary but excludes every generated/test function the engine
        # appends its collectors in place of. Whitespace before the boundary is
        # kept (it mirrors what an authored start_str literal ended with).
        self.assertTrue(harness.startswith(result))
        self.assertIn("function setUp", result)
        self.assertIn("function profitSummary", result)
        self.assertNotIn("function testExample", result)
        self.assertNotIn("function helper", result)

    def test_slices_authored_harness_at_testExample(self):
        harness = _PREAMBLE + "    function testExample0() public { revert(\"\"); }\n}"
        self._assert_is_the_preamble(harness, extract_preamble(harness))

    def test_slices_generated_file_at_earlier_helper(self):
        # A generated collector is preamble + helpers + testExampleN_; the helper
        # comes first, so the same preamble is recovered from it too.
        generated = _PREAMBLE + "    function helper0_(uint a) internal { }\n" \
                                "    function testExample0_() public { helper0_(1); }\n}"
        self._assert_is_the_preamble(generated, extract_preamble(generated))

    def test_no_boundary_raises(self):
        with self.assertRaises(ValueError):
            extract_preamble(_PREAMBLE + "}")


class CheckPlaceholderCountTest(unittest.TestCase):
    def test_match_is_ok(self):
        check_placeholder_count("a", "eUSDC.deposit(0, $$ * 1e6);", 1)   # no raise
        check_placeholder_count("a", "eUSDC.touch();", 0)
        check_placeholder_count("a", "f($$, $$);", 2)

    def test_too_few_placeholders_raises(self):
        with self.assertRaises(ValueError):
            check_placeholder_count("a", "f(0, $$);", 2)

    def test_too_many_placeholders_raises(self):
        with self.assertRaises(ValueError):
            check_placeholder_count("a", "f($$, $$);", 1)

    def test_error_names_the_action(self):
        with self.assertRaises(ValueError) as cm:
            check_placeholder_count("eulerMint", "no placeholders", 1)
        self.assertIn("eulerMint", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
