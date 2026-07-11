"""Build a FlashSyn benchmark from a declarative manifest.toml.

An example that ships a manifest.toml needs no Python action model: the fields
that a hand-written model spelled out — initial balances, token prices, token
metadata, and one entry per protocol action — are data here, and load() turns
them into the same (wrapper, actions, dependencies) the engine drives. The
Solidity harness (attack.t.sol) still lives next to the manifest, since setUp /
interfaces / profitSummary are protocol-specific code, not config.

Schema (see examples/harvest_usdt/manifest.toml):

    name = "harvest_usdt"        # benchmark id
    contract = "Harvest_USDT"    # --match-contract name in attack.t.sol
    chain = "ETH"                # ETH | BSC | Fantom | Polygon
    block = 11129474             # fork block
    max_synthesis_len = 4
    profit_tokens = ["USDT","USDC"]   # profitSummary() output order

    [initial_balances]   USDT = 18308555.417594 ...
    [token_prices]       USDT = 1.0 ...
    [token_info]         USDT = ["USDT", 6] ...   # token -> [solidity var, decimals]

    [[actions]]
    name = "Curve_USDT2USDC"
    tokens_in = ["USDT"]
    tokens_out = ["USDC"]
    range = [0, 20000000]
    solidity = "CURVE.exchange_underlying(2, 1, $$ * 1e6, 0);"   # numInputs = count of $$

Two optional per-action fields cover the actions a fixed swap/deposit model can't
express — the cases that used to force a Python action model (see examples/puppet):

    collector = '''...revert(...);'''   # raw Solidity, verbatim, REPLACES the derived
                                        # balanceOf collector. Needed when the measured
                                        # output isn't an attacker balanceOf delta:
                                        # native ETH, an input-side amount, /1e18 quirks.

    effects = [                         # REPLACES the default transit (consume tokens_in
      {token="DVT", op="add", src="param0"},   # params, produce approximated tokens_out).
      {token="ETH", op="sub", src="approx0"},  # Needed when the search parameter is a
    ]                                          # received amount and a paid amount is the
                                               # approximation (borrow/mint), when an action
                                               # zeroes a balance, or has no measured output.
        # op    : add | sub | set
        # src   : paramN (the Nth $$, 0-based) | approxN (the Nth collector output) | 0

tokens_in / tokens_out always describe token FLOW for the search graph, independent of
these; annotate them by direction even when effects invert the magnitude bookkeeping.
Omit both fields and the common case keeps zero boilerplate.

Prototype (opt-in, top-level `use_collect_helper = true`; see examples/euler): instead of
a `collector` field, DERIVE every collector from `effects` and emit it through a `Collect`
helper contract in the harness (collect.balanceChange(name, wholeTokenDelta) + flush). Each
approxN effect is measured as a balance delta (op=add -> after-before, op=sub -> before-after)
in approxN order, scaled by token_info decimals. Off by default -> other examples unchanged.
"""
import tomllib

import config
from Actions.macros import DVD
from Actions.UtilsPrecision import NumericalApproximatorsPro
from Actions.AttackDAG import AttackDAGGenerator, generateActionDependency
from FlashSynProActions.ActionPro import ActionPro


def _make_calc_profit(profit_tokens, initial, prices):
    def calcProfit(stats):
        if stats is None or len(stats) != len(profit_tokens):
            return 0
        return sum((stats[i] - initial.get(tok, 0)) * prices.get(tok, 1.0)
                   for i, tok in enumerate(profit_tokens))
    return calcProfit


def _make_action_str(name, solidity):
    body = "        // Action: {}\n        {}\n".format(name, solidity)
    def actionStr(cls, _body=body):
        return _body
    return actionStr


def _make_collector(raw):
    """Raw Solidity used verbatim as the collector — overrides the derived one."""
    def collectorStr(cls, _raw=raw):
        return _raw
    return collectorStr


def _make_transit(num_inputs, effects):
    """Declarative balance transition from an `effects` list.

    Each effect is {token, op, src}. src resolves to: paramN -> the Nth of this
    action's inputs (the last num_inputs of the input vector, matching numInputs);
    approxN -> the Nth collector output from simulate(); 0 -> the literal 0.
    """
    def transit(cls, inputs, actionList, _effects=effects, _n=num_inputs):
        params = inputs[-_n:] if _n else []
        outputs = None
        for e in _effects:
            src = e["src"]
            if src == "0":
                val = 0
            elif src.startswith("param"):
                val = params[int(src[len("param"):])]
            elif src.startswith("approx"):
                if outputs is None:
                    outputs = cls.simulate(inputs, actionList)
                val = outputs[int(src[len("approx"):])]
            else:
                raise ValueError("bad effect src {!r} (want paramN | approxN | 0)".format(src))
            tok, op = e["token"], e["op"]
            cur = cls.currentBalances.get(tok, 0)
            if op == "add":
                cls.currentBalances[tok] = cur + val
            elif op == "sub":
                cls.currentBalances[tok] = cur - val
            elif op == "set":
                cls.currentBalances[tok] = val
            else:
                raise ValueError("bad effect op {!r} (want add | sub | set)".format(op))
    return transit


def _measures_for(action):
    """The (token, direction) to measure for an action, in approxN order.

    direction is 'gain' (op=add -> after-before) or 'spend' (op=sub -> before-after).
    Derived from the effects whose src is approxN; if there are none, fall back to the
    default (measure each tokens_out as a gain), so a plain action needs no effects.
    """
    approx = []
    for e in action.get("effects", []):
        src = e["src"]
        if src.startswith("approx"):
            approx.append((int(src[len("approx"):]),
                           e["token"],
                           "gain" if e["op"] == "add" else "spend"))
    if approx:
        approx.sort()
        return [(tok, d) for _, tok, d in approx]
    return [(t, "gain") for t in action["tokens_out"]]


def _make_collect_collector(measures, token_info):
    """A collectorStr that measures each (token, direction) as a balance delta and
    records it with collect.balanceChange(name, wholeTokenDelta); the harness's
    Collect helper reverts them for the parser. Deltas are pre-scaled by token_info
    decimals (single source of decimals) — the emitted values stay whole-token ints,
    so the positional parser is unchanged. No approx to measure -> just flush (the
    Collect helper reverts "FlashSyn: 0").
    """
    def collectorStr(cls, _m=measures, _ti=token_info):
        reads, changes = "", ""
        for i, (tok, direction) in enumerate(_m):
            info = _ti[tok]
            var, dec = info[0], info[1]
            native = len(info) > 2 and info[2] == "native"
            acc = "address(attacker).balance" if native else "{}.balanceOf(address(attacker))".format(var)
            reads += "        uint _fsC{} = {};\n".format(i, acc)
            delta = "({} - _fsC{})".format(acc, i) if direction == "gain" else "(_fsC{} - {})".format(i, acc)
            changes += '        collect.balanceChange("{}", {} / 1e{});\n'.format(tok, delta, dec)
        return "        // Collect: {}\n".format(cls.__name__) + reads + cls.actionStr() + changes + "        collect.flush();\n"
    return collectorStr


def load(manifest_path):
    """Read a manifest.toml and return {wrapper, actions, dependencies, max_len}."""
    with open(manifest_path, "rb") as f:
        m = tomllib.load(f)

    initial = dict(m["initial_balances"])
    prices = dict(m["token_prices"])
    token_info = {k: tuple(v) for k, v in m["token_info"].items()}

    wrapper = type(m["name"] + "_wrapper", (ActionPro,), {
        "initialBalances": initial,
        "currentBalances": dict(initial),
        "TokenPrices": prices,
        "TargetTokens": list(prices.keys()),
        "tokenInfo": token_info,
        "calcProfit": staticmethod(_make_calc_profit(m["profit_tokens"], initial, prices)),
    })

    # Opt-in prototype: derive every collector from the action's effects and emit it
    # through the harness's Collect helper (collect.balanceChange), instead of a raw
    # `collector` field. See examples/euler. Off by default -> harvest/puppet unchanged.
    use_collect = m.get("use_collect_helper", False)

    actions = []
    for a in m["actions"]:
        solidity = a["solidity"]
        num_inputs = solidity.count("$$")
        attrs = {
            "approximators": NumericalApproximatorsPro(),
            "numInputs": num_inputs,
            "tokensIn": list(a["tokens_in"]),
            "tokensOut": list(a["tokens_out"]),
            "range": list(a["range"]),
            "actionStr": classmethod(_make_action_str(a["name"], solidity)),
        }
        if use_collect:
            if "collector" in a:
                raise ValueError("action {}: 'collector' is not used with use_collect_helper "
                                 "(the collector is derived from effects)".format(a["name"]))
            attrs["collectorStr"] = classmethod(_make_collect_collector(_measures_for(a), token_info))
        elif "collector" in a:
            attrs["collectorStr"] = classmethod(_make_collector(a["collector"]))
        if "effects" in a:
            attrs["transit"] = classmethod(_make_transit(num_inputs, a["effects"]))
        actions.append(type(a["name"], (wrapper,), attrs))

    config.ExecutionMode = DVD
    config.command = "./run.sh {} {} {}".format(m["contract"], m["chain"], m["block"])
    config.benchmarkName = m["name"]

    # Safe default: every action's prestate may be reached by running all the others.
    dependencies = [[b for b in actions if b is not a] + [a] for a in actions]
    AttackDAGGenerator.setActionDependency(generateActionDependency(actions, dependencies))

    return {"wrapper": wrapper, "actions": actions, "dependencies": dependencies,
            "max_len": m.get("max_synthesis_len", len(actions))}
