"""Unit tests for forge/forgeJson.parse_datapoints — the producer/consumer
contract between the generated Solidity harness and the Python engine.

Pure Python: no forge, no fork, runs anywhere. From the repo root:
    python3 -m unittest src/forge/test_forgeJson.py
or:
    python3 src/forge/test_forgeJson.py
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # src/

from forge.forgeJson import parse_datapoints  # noqa: E402
from conventions import FLASHSYN_MARKER  # noqa: E402


def _forge_json(reasons):
    """Build a `forge test --json` stdout (bytes) from {test_name: reason}."""
    results = {name: {"status": "Failure", "reason": reason}
               for name, reason in reasons.items()}
    return json.dumps({"src/test/attack.t.sol:euler": {"test_results": results}}).encode()


def _dp(n):
    """n empty data points: [[paras], stats]."""
    return [[[i], None] for i in range(n)]


class ParseDatapointsTest(unittest.TestCase):
    def test_multi_and_single_value_and_index_from_name(self):
        out = _forge_json({
            "testExample0_()": FLASHSYN_MARKER + ": 123 456",
            "testExample1_()": FLASHSYN_MARKER + ": 789",
        })
        dp = parse_datapoints(out, _dp(2))
        self.assertEqual(dp[0][1], [123, 456])
        self.assertEqual(dp[1][1], [789])

    def test_no_marker_is_none(self):
        out = _forge_json({"testExample0_()": "e/collateral-violation"})
        self.assertIsNone(parse_datapoints(out, _dp(1))[0][1])

    def test_marker_but_no_digits_is_none(self):
        out = _forge_json({"testExample0_()": FLASHSYN_MARKER + ": "})
        self.assertIsNone(parse_datapoints(out, _dp(1))[0][1])

    def test_no_index_is_dropped_from_reason(self):
        # regression: the old code treated the last int as an index and dropped
        # it. The canonical template has no index in the reason -> keep all ints.
        out = _forge_json({"testExample0_()": FLASHSYN_MARKER + ": 90958"})
        self.assertEqual(parse_datapoints(out, _dp(1))[0][1], [90958])

    def test_digits_before_marker_are_ignored(self):
        # only integers AFTER the marker are stats
        out = _forge_json({"testExample0_()": "gas 999 " + FLASHSYN_MARKER + ": 42"})
        self.assertEqual(parse_datapoints(out, _dp(1))[0][1], [42])

    def test_mapping_is_order_independent(self):
        out = _forge_json({
            "testExample1_()": FLASHSYN_MARKER + ": 11",
            "testExample0_()": FLASHSYN_MARKER + ": 22",
        })
        dp = parse_datapoints(out, _dp(2))
        self.assertEqual(dp[0][1], [22])
        self.assertEqual(dp[1][1], [11])

    def test_empty_datapoints_returns_unchanged(self):
        # synthesizer runs 0-test batches; must not raise
        self.assertEqual(parse_datapoints(b"", []), [])

    def test_empty_stdout_with_expected_collectors_stays_none(self):
        dp = parse_datapoints(b"", _dp(3))
        self.assertEqual([d[1] for d in dp], [None, None, None])

    def test_out_of_range_index_is_skipped_not_fatal(self):
        out = _forge_json({
            "testExample0_()": FLASHSYN_MARKER + ": 5",
            "testExample9_()": FLASHSYN_MARKER + ": 7",  # only 1 data point exists
        })
        dp = parse_datapoints(out, _dp(1))
        self.assertEqual(dp[0][1], [5])
        self.assertEqual(len(dp), 1)


if __name__ == "__main__":
    unittest.main()
