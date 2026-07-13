"""Generate a per-action smoke/validate harness from the manifest (no hand-written tests).

For each action the harness runs a token-flow prefix (the actions whose outputs grant the
target's tokens_in, so the target reaches a usable prestate) then the target action, and
ends in revert("PROBE_OK"). A probe whose revert reason is PROBE_OK executed cleanly; any
other reason is a real (protocol) revert. Each action is tried at several in-range values,
so one bad value (overflow, dust) doesn't mask an action that does run.

Limitation: the prefix is pure token flow. An action needing protocol STATE the manifest
doesn't capture (e.g. euler's liquidation needs a prior donate to crash the oracle so the
position is liquidatable) will FAIL here — correctly flagging "the manifest alone can't set
this up", not a bug in the action.
"""
import json
import re

PROBE_MARKER = "PROBE_OK"
_TEST = re.compile(r"testExample(\d+)")


def _probe_values(action):
    """In-range values to try, spanning small -> large (or [None] for a 0-input action).

    Small values matter: an action consuming a produced token (burn/donate) usually holds
    far less than the search range's high end, so a large probe reverts (amount-too-large)
    while a small one runs. Trying the spread means one bad value doesn't mask a live action.
    """
    r = list(getattr(action, "range", []) or [])
    if getattr(action, "numInputs", 0) == 0 or len(r) != 2:
        return [None]
    lo, hi = r
    span = hi - lo
    cands = [lo + 1, lo + max(1, span // 1000), lo + max(1, span // 100),
             lo + max(1, span // 4), lo + span // 2]
    out = []
    for v in cands:
        if lo < v <= hi and v not in out:
            out.append(v)
    return out or [hi]


def _mid_value(action):
    vals = _probe_values(action)
    return vals[len(vals) // 2]


def _concrete(action, val):
    """The action's Solidity with each $$ replaced by a concrete in-range value."""
    s = action.actionStr()
    if val is not None:
        while "$$" in s:
            s = s.replace("$$", str(val), 1)
    return s


def _prefix(action, actions, initial):
    """Greedy token-flow prefix: runnable actions (in order) whose outputs grant the
    target's tokens_in. Best effort — stops if a needed token can't be produced."""
    have = set(initial)
    seq, needed = [], set(action.tokensIn) - have
    while needed:
        progressed = False
        for a in actions:
            if a is action or a in seq:
                continue
            if set(a.tokensIn) <= have and (set(a.tokensOut) & needed):
                seq.append(a)
                have |= set(a.tokensOut)
                needed -= set(a.tokensOut)
                progressed = True
        if not progressed:
            break
    return seq


def build_validate_harness(preamble, actions, initial_balances):
    """Return (harness_str, [action_name per testExample index])."""
    fns, idx_action = [], []
    for action in actions:
        prefix = _prefix(action, actions, set(initial_balances))
        for val in _probe_values(action):
            body = "".join("    " + _concrete(a, _mid_value(a)) for a in prefix)
            body += "    " + _concrete(action, val)
            body += '        revert("{}");\n'.format(PROBE_MARKER)
            fns.append("    function testExample{}() public {{\n{}    }}\n".format(len(idx_action), body))
            idx_action.append(action.__name__)
    return preamble + "\n" + "".join(fns) + "\n}\n", idx_action


def report(stdout, idx_action):
    """Print a per-action RUNS/FAILS table from forge --json stdout; return True if all run.

    An action RUNS if ANY of its probes reverted with PROBE_MARKER (executed to the end)."""
    text = stdout.decode(errors="replace") if isinstance(stdout, (bytes, bytearray)) else stdout
    start = text.find("{")
    data = json.loads(text[start:]) if start != -1 else {}
    result = {name: [False, None] for name in idx_action}   # action -> [ran, sample failure reason]
    for suite in data.values():
        for tname, res in suite.get("test_results", {}).items():
            m = _TEST.search(tname)
            if not m or int(m.group(1)) >= len(idx_action):
                continue
            name = idx_action[int(m.group(1))]
            reason = res.get("reason") or ""
            if PROBE_MARKER in reason:
                result[name][0] = True
            elif result[name][1] is None:
                result[name][1] = reason

    print("\n=== validate: per-action smoke (generated from the manifest) ===")
    all_ok = True
    for name in dict.fromkeys(idx_action):          # unique, in manifest order
        ran, why = result[name]
        if ran:
            print("  RUNS   {}".format(name))
        else:
            all_ok = False
            print("  FAILS  {}  (reason: {})".format(name, why or "no PROBE_OK reached"))
    print("=== {} ===".format(
        "all actions run" if all_ok else "some actions need setup the manifest can't express (see reasons)"))
    return all_ok
