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

from conventions import SEPARATOR_TEXT

PROBE_MARKER = "PROBE_OK"
_TEST = re.compile(r"testExample(\d+)")
_SEP = '        emit log("{}");\n'.format(SEPARATOR_TEXT)


# Points to probe, as FRACTIONS of the [lo, hi] range: both boundaries (0.0 -> lo, 1.0 -> hi)
# and a spread of interior values. Using fractions means every candidate is in range by
# construction — no hardcoded amount that could fall outside [lo, hi]. Ordered small-first
# and we take the first value that executes, so the small fractions do the work: an action
# consuming a produced token (burn/donate) holds far less than the range top, so only a small
# amount runs, while lo (often a no-op) and hi (often too large) just document the boundaries.
_PROBE_FRACTIONS = (0.0, 0.001, 0.01, 0.1, 0.5, 1.0)


def _probe_values(action):
    """In-range values to try (or [None] for a 0-input action like touch)."""
    r = list(getattr(action, "range", []) or [])
    if getattr(action, "numInputs", 0) == 0 or len(r) != 2:
        return [None]
    lo, hi = r
    span = hi - lo
    out = []
    for f in _PROBE_FRACTIONS:
        v = lo + int(span * f)                # in [lo, hi] since f in [0, 1]
        if v not in out:                      # de-duplicate (tiny spans collapse to a few)
            out.append(v)
    return out


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


def _deps_value(action):
    """A single small in-range value for a deps probe (the target must execute, and small
    amounts tend to)."""
    vals = _probe_values(action)
    if vals == [None]:
        return None
    nonzero = [v for v in vals if v != 0]
    return nonzero[0] if nonzero else vals[0]


def build_deps_harness(preamble, actions, initial_balances):
    """A dependency-probe harness for `deps`: one testExample per action = a token-flow
    prefix then the target action bracketed by SEPARATOR logs (dependencyCheck.py diffs the
    storage each action touches between the separators). Concrete values are best-effort
    (a small amount that tends to execute); an action needing state the manifest can't set
    up produces no useful trace, same as a mis-written hand-authored probe would."""
    fns = []
    for i, action in enumerate(actions):
        prefix = _prefix(action, actions, set(initial_balances))
        body = "".join("    " + _concrete(a, _deps_value(a)) for a in prefix)
        body += _SEP + "    " + _concrete(action, _deps_value(action)) + _SEP
        body += '        revert("");\n'
        fns.append("    function testExample{}() public {{\n{}    }}\n".format(i, body))
    return preamble + "\n" + "".join(fns) + "\n}\n"


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
