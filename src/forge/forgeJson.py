"""Structured parsing of `forge test --json` output.

FlashSyn's data collectors used to scrape colored `-vvv` text
(`FAIL. Reason: <r> (gas: N)`). Modern forge (>=1.x) changed that format to
`[FAIL: <r>] name() (gas: N)` and drops ANSI codes when piped, which broke the
scrapers. Instead of chasing the text format, we consume `forge test --json`,
whose shape is stable:

    {"<path>:<Contract>": {"test_results": {
        "testExampleN_()": {"status": "Failure", "reason": "FlashSyn: 1 2", ...}
    }}}

Two conventions link the generated Solidity to this parser (see conventions.py):
  - Each data-collector test is named testExampleN_ and maps to dataPoints[N];
    the index N lives ONLY in the function name (addDataCollector names them in
    order and appends to dataPoints in lockstep). We recover it from the name so
    the mapping is independent of the order forge reports tests in.
  - The test reverts on purpose with a reason beginning FLASHSYN_MARKER; the
    integers AFTER the marker are the collected stats. There is no index in the
    reason. A revert without the marker (an unexpected protocol revert) means no
    data for that point.
"""
import json
import re
import sys

from conventions import FLASHSYN_MARKER

_TEST_INDEX = re.compile(r"testExample(\d+)_")


def _extract_json(stdout) -> str:
    """Return the JSON object substring from forge's stdout.

    With `--json`, forge writes the machine JSON to stdout and diagnostics to
    stderr, but slice from the first brace defensively in case anything leaks.
    """
    text = stdout.decode(errors="replace") if isinstance(stdout, (bytes, bytearray)) else stdout
    start = text.find("{")
    return text[start:] if start != -1 else ""


_NAMED = re.compile(r"([A-Za-z_]\w*)=(\d+)")


def _stats_from_reason(reason, order=None):
    """Return the collected stats (a positional list) from a revert reason, or None.

    Two revert shapes share the marker:
      - Named (the Collect helper's flush):  "FlashSyn: eUSDC=<raw> dUSDC=<raw>"
      - Positional (a bare "FlashSyn: 0" for a no-measure action):  "FlashSyn: 0"

    Values are emitted RAW (unscaled). `order` is a list of (token, decimals) in the
    expected position order, so we (a) map each named value to its position regardless of
    emit order, and (b) scale it to whole tokens as a float (raw / 10**decimals) — the
    scaling lives here (one source: token_info), not in Solidity. A name in `order` the
    revert didn't report is a real producer/consumer mismatch, so raise. Without `order`
    we fall back to emit order, unscaled. Only text AFTER the marker is parsed.
    """
    if not reason:
        return None
    pos = reason.find(FLASHSYN_MARKER)
    if pos == -1:
        return None
    tail = reason[pos + len(FLASHSYN_MARKER):]
    named = _NAMED.findall(tail)
    if named:
        by_name = {name: int(v) for name, v in named}
        if order is not None:
            missing = [tok for tok, _ in order if tok not in by_name]
            if missing:
                raise KeyError("collector reported {} but the action measures {}; missing {}".format(
                    sorted(by_name), [tok for tok, _ in order], missing))
            return [by_name[tok] / (10 ** dec) for tok, dec in order]
        return [int(v) for _, v in named]        # no order: emit order, unscaled (fallback)
    stats = [int(s) for s in re.findall(r"\d+", tail)]
    return stats if stats else None


def parse_datapoints(stdout, dataPoints):
    """Fill dataPoints[index][1] from `forge test --json` stdout.

    dataPoints is FlashSyn's list of [paraList, stats]; index i corresponds to
    the test function testExamplei_. A test whose revert reason carries the marker
    yields the list of integers after it; anything else (an unexpected revert, an
    empty reason) yields None.

    Degrades gracefully: the synthesizer calls this in a loop and legitimately
    runs batches with no data collectors (a round with no concrete candidates ->
    0 tests -> empty forge output). In that case there is nothing to fill, so we
    return dataPoints as-is. If collectors *were* expected but forge produced no
    parseable JSON, we warn (rather than abort the search) and leave them None.
    Mapping anomalies (a test index out of range, or two tests hitting the same
    index) are warned about too, so a broken producer/consumer contract surfaces
    instead of silently scrambling the data.
    """
    if not dataPoints:
        return dataPoints

    raw = _extract_json(stdout)
    data = None
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
    if data is None:
        sys.stderr.write("forgeJson: warning - no forge JSON for {} data collectors; "
                         "recording them as None\n".format(len(dataPoints)))
        return dataPoints

    seen = {}
    for suite in data.values():
        for name, res in suite.get("test_results", {}).items():
            m = _TEST_INDEX.search(name)
            if m is None:
                continue
            idx = int(m.group(1))
            if idx >= len(dataPoints):
                sys.stderr.write("forgeJson: warning - test {} maps to index {} but only "
                                 "{} data points exist; skipping\n".format(name, idx, len(dataPoints)))
                continue
            if idx in seen:
                sys.stderr.write("forgeJson: warning - tests {} and {} both map to data point "
                                 "{}; using the latter\n".format(seen[idx], name, idx))
            seen[idx] = name
            entry = dataPoints[idx]
            order = entry[2] if len(entry) > 2 else None   # measured-token names, if the producer set them
            entry[1] = _stats_from_reason(res.get("reason"), order)
    return dataPoints
