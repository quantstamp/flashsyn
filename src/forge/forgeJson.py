"""Structured parsing of `forge test --json` output.

FlashSyn's data collectors used to scrape colored `-vvv` text
(`FAIL. Reason: <r> (gas: N)`). Modern forge (>=1.x) changed that format to
`[FAIL: <r>] name() (gas: N)` and drops ANSI codes when piped, which broke the
scrapers. Instead of chasing the text format, we consume `forge test --json`,
whose shape is stable:

    {"<path>:<Contract>": {"test_results": {
        "testExampleN_()": {"status": "Failure", "reason": "FlashSyn 1, 2, N", ...}
    }}}

Each FlashSyn data-collector test testExampleN_ maps to dataPoints[N] (the data
point index is the N in the function name, assigned in order by addDataCollector).
The test reverts on purpose with a reason string like "FlashSyn: <stat1> <stat2>";
every integer in it is a collected stat. A revert without "FlashSyn" (an
unexpected failure) means no data for that point.
"""
import json
import re
import sys


def _extract_json(stdout) -> str:
    """Return the JSON object substring from forge's stdout.

    With `--json`, forge writes the machine JSON to stdout and diagnostics to
    stderr, but slice from the first brace defensively in case anything leaks.
    """
    text = stdout.decode(errors="replace") if isinstance(stdout, (bytes, bytearray)) else stdout
    start = text.find("{")
    return text[start:] if start != -1 else ""


def parse_datapoints(stdout, dataPoints):
    """Fill dataPoints[index][1] from `forge test --json` stdout.

    dataPoints is FlashSyn's list of [paraList, stats]; index i corresponds to
    the test function testExamplei_. A test whose revert reason carries FlashSyn
    stats yields the list of integers in that reason; anything else (an
    unexpected revert, an empty reason) yields None.

    Degrades gracefully: the synthesizer calls this in a loop and legitimately
    runs batches with no data collectors (a round with no concrete candidates ->
    0 tests -> empty forge output). In that case there is nothing to fill, so we
    return dataPoints as-is. If collectors *were* expected but forge produced no
    parseable JSON, we warn (rather than abort the search) and leave them None.
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

    for suite in data.values():
        for name, res in suite.get("test_results", {}).items():
            m = re.search(r"testExample(\d+)_", name)
            if m is None:
                continue
            idx = int(m.group(1))
            if idx >= len(dataPoints):
                continue
            reason = res.get("reason")
            if reason and "FlashSyn" in reason:
                stats = [int(s) for s in re.findall(r"\d+", reason)]
                dataPoints[idx][1] = stats if stats else None
            else:
                dataPoints[idx][1] = None
    return dataPoints
