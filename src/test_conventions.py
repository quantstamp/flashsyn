"""Unit tests for conventions.check_placeholder_count — the $$ / numInputs
contract between an action's Solidity and its declared parameter count.

Pure Python, no forge. From the repo root:
    python3 -m unittest src/test_conventions.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # src/

from conventions import check_placeholder_count  # noqa: E402


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
