"""Contracts shared between the Python engine and the generated Solidity harness.

These strings are the seams where Python parses Solidity output, so both sides
must agree. Kept here (one source of truth) instead of duplicated as literals so
they can't silently drift.

If you change a value here you MUST update the Solidity that emits it:
  - SEPARATOR_TEXT  -> the `emit log("...")` calls in
        foundryModule/src/test/template.t.sol (and any filled-in attack.t.sol)
  - FLASHSYN_MARKER -> the `revert("FlashSyn: ...")` collector strings in
        FlashSynProActions/ActionPro.py's default collectorStr (and any `collector`
        field a manifest.toml writes verbatim)
  - PLACEHOLDER     -> the `$$` markers in an action's actionStr()/collectorStr()
"""

# A data-collector test reverts with a reason that begins with this marker; the
# integers following it are the collected stats. forge/forgeJson.py keys off it,
# and a reason WITHOUT it means the action reverted unexpectedly (no data point).
FLASHSYN_MARKER = "FlashSyn"

# dependencyCheck brackets each action between two `emit log(SEPARATOR_TEXT)`
# calls so it can slice the trace into per-action sections.
SEPARATOR_TEXT = "=================== Separator =================="

# The marker an action writes in its Solidity wherever a numeric parameter goes.
# The contract builders substitute each occurrence with a generated variable, so
# an action's declared numInputs must equal its placeholder count.
PLACEHOLDER = "$$"


# The generated collector/attack Solidity is appended directly after the harness
# preamble (interfaces + contract decl + state vars + setUp + profitSummary). These
# tokens are the first thing that comes AFTER the preamble in both an authored
# harness (`function testExampleN()`) and a generated collector file (`function
# helperN_(...)` emitted by forgeCollectDVD). Slicing a harness at the earliest of
# them recovers the preamble, so an action model no longer has to duplicate it as a
# `start_str` literal — see extract_preamble() and FlashSynProActions/ActionPro.py.
# A harness preamble must therefore NOT contain these tokens (e.g. don't name a
# helper function "helper" or mention "testExample" in setUp/profitSummary).
PREAMBLE_BOUNDARIES = ("function testExample", "function helper")


def extract_preamble(harness_text):
    """Return the harness preamble: everything before the first generated/test function.

    Works on both an authored `attack.t.sol` (cut at `function testExample`) and an
    engine-generated collector file (cut at the earlier `function helper`), so the
    same slice recovers the preamble whichever the engine reads. Raises if no
    boundary is present, since silently returning the whole file would append the
    generated collectors to a full contract and fail to compile cryptically.
    """
    cuts = [i for i in (harness_text.find(m) for m in PREAMBLE_BOUNDARIES) if i != -1]
    if not cuts:
        raise ValueError(
            "harness has no {} function; cannot locate the preamble boundary".format(
                " / ".join(PREAMBLE_BOUNDARIES)))
    return harness_text[:min(cuts)]


def check_placeholder_count(action_name, snippet, num_inputs):
    """Fail loud if an action's Solidity has the wrong number of '$$' markers.

    A mismatch is otherwise silent or cryptic: too few placeholders desync the
    shared variable pool (a later action gets the wrong variable), and too many
    leave literal '$$' in the source so forge reports an opaque solc error. This
    surfaces it at build time, naming the offending action.
    """
    found = snippet.count(PLACEHOLDER)
    if found != num_inputs:
        raise ValueError(
            "action {} declares numInputs={} but its Solidity has {} '{}' "
            "placeholder(s)".format(action_name, num_inputs, found, PLACEHOLDER))
