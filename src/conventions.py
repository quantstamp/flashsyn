"""Contracts shared between the Python engine and the generated Solidity harness.

These strings are the seams where Python parses Solidity output, so both sides
must agree. Kept here (one source of truth) instead of duplicated as literals so
they can't silently drift.

If you change a value here you MUST update the Solidity that emits it:
  - SEPARATOR_TEXT  -> the `emit log("...")` calls in
        foundryModule/src/test/template.t.sol (and any filled-in attack.t.sol)
  - FLASHSYN_MARKER -> the `revert("FlashSyn: ...")` collector strings in
        FlashSynProActions/template.py (and filled-in action models)
"""

# A data-collector test reverts with a reason that begins with this marker; the
# integers following it are the collected stats. forge/forgeJson.py keys off it,
# and a reason WITHOUT it means the action reverted unexpectedly (no data point).
FLASHSYN_MARKER = "FlashSyn"

# dependencyCheck brackets each action between two `emit log(SEPARATOR_TEXT)`
# calls so it can slice the trace into per-action sections.
SEPARATOR_TEXT = "=================== Separator =================="
