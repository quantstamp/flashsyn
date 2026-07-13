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

Collectors are always DERIVED and emitted through the harness's Collect helper
(src/foundryModule/lib/mylib/Collect.sol, deployed as `collect` in setUp): the action records
a token's change with collect.gained("<tok>", raw) / collect.spent("<tok>", raw) and the engine
appends collect.flush(), which reverts "FlashSyn: <tok>=<raw> ..."; the parser maps values to
positions by name and scales each by token_info decimals (as a float — no rounding in Solidity).
There is no `collector` field. Two things shape an action:

    effects = [                         # optional; REPLACES the default transit (consume
      {token="DVT", op="add", src="input"},     # tokens_in params, produce the collected
      {token="ETH", op="sub", src="collected"}, # tokens_out). Needed when the parameter is
    ]                                           # a received amount and a paid amount is the
                                                # collected one (borrow/mint), when an action
                                                # zeroes a balance, or has no measured output.
        # op    : add | sub | set
        # src   : input (the sole $$; inputN for a multi-$$ action)
        #         | collected (this token's own value the collector reported)
        #         | a number literal (whole-token constant, e.g. 0, 5, -100; handy with set)

`effects` also DRIVES the derived collector (Mode A): each `collected` token is measured as a
balance delta and recorded with collect.gained (op=add, after-before) or collect.spent (op=sub,
before-after), scaled by token_info decimals. With no effects, the default measures each
tokens_out as a gain. token_info's optional 3rd element "native" -> address(attacker).balance.

Mode B — when the collected value is an INTERNAL quantity (not a start-to-end balance delta,
e.g. borrow's collateral _dep), the action records it inline in `solidity` with a
collect.spent/gained("<tok>", value) call; the engine then only appends collect.flush().

tokens_in / tokens_out always describe token FLOW for the search graph, independent of the
above; annotate them by direction even when effects invert the magnitude bookkeeping.
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


def _make_transit(num_inputs, effects):
    """Declarative balance transition from an `effects` list.

    Each effect is {token, op, src}. src resolves to: input -> this action's search
    parameter (the sole $$; inputN for the Nth of a multi-$$ action); collected -> this
    token's own value that the collector reported (via simulate()); or a number literal
    (a whole-token constant, e.g. 0, 5, -100), useful with op=set to reset a balance.
    """
    collected_tokens = [e["token"] for e in effects if e["src"] == "collected"]

    def transit(cls, inputs, actionList, _effects=effects, _n=num_inputs, _coll=collected_tokens):
        params = inputs[-_n:] if _n else []
        outputs = None
        for e in _effects:
            src = e["src"]
            if src == "collected":
                if outputs is None:
                    outputs = cls.simulate(inputs, actionList)
                val = outputs[_coll.index(e["token"])]         # this token's collected value
            elif isinstance(src, str) and src.startswith("input"):
                idx = src[len("input"):]
                val = params[int(idx) if idx else 0]           # input == input0 (the sole $$)
            elif isinstance(src, (int, float)):
                val = src                                       # literal constant (TOML number)
            elif isinstance(src, str):
                try:
                    val = float(src) if "." in src else int(src)   # numeric string, incl. "0"
                except ValueError:
                    raise ValueError("bad effect src {!r} (want input | collected | a number)".format(src))
            else:
                raise ValueError("bad effect src {!r} (want input | collected | a number)".format(src))
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
    """The (token, direction) to measure for an action, in effect order.

    direction is 'gain' (op=add -> collect.gained, after-before) or 'spend' (op=sub ->
    collect.spent, before-after). Derived from the effects whose src is 'collected'; if there
    are none, fall back to the default (measure each tokens_out as a gain), so a plain action
    needs no effects.
    """
    collected = [(e["token"], "gain" if e["op"] == "add" else "spend")
                 for e in action.get("effects", []) if e["src"] == "collected"]
    if collected:
        return collected
    return [(t, "gain") for t in action["tokens_out"]]


def _make_inline_collector():
    """Collector for an action that records its own measurement inline in `solidity`
    (a collect.spent/gained(...) call — e.g. an internal value like borrow's _dep that
    isn't a start-to-end balance delta). The engine only appends collect.flush()."""
    def collectorStr(cls):
        return "        // Collect: {}\n".format(cls.__name__) + cls.actionStr() + "        collect.flush();\n"
    return collectorStr


def _make_collect_collector(measures, token_info):
    """A collectorStr that measures each (token, direction) as a balance delta and records
    it RAW with collect.gained/spent(name, rawDelta); the harness's Collect helper reverts
    them for the parser, which scales each raw value by token_info decimals as a float (one
    source of decimals, kept out of Solidity). No measure -> just flush (the Collect helper
    reverts "FlashSyn: 0").
    """
    def collectorStr(cls, _m=measures, _ti=token_info):
        reads, changes = "", ""
        for i, (tok, direction) in enumerate(_m):
            info = _ti[tok]
            native = len(info) > 2 and info[2] == "native"
            acc = "address(attacker).balance" if native else "{}.balanceOf(address(attacker))".format(info[0])
            reads += "        uint _fsC{} = {};\n".format(i, acc)
            # subtract in whichever order keeps the raw magnitude positive; the direction is
            # the method name. The parser scales the raw value by token_info decimals (float).
            if direction == "gain":
                changes += '        collect.gained("{}", {} - _fsC{});\n'.format(tok, acc, i)
            else:
                changes += '        collect.spent("{}", _fsC{} - {});\n'.format(tok, i, acc)
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
        # profitSummary()'s (token, decimals) order: the parser maps its named revert to
        # positions and scales each raw balance by decimals, like the collectors.
        "profitTokens": [(t, token_info[t][1]) for t in m["profit_tokens"]],
        "calcProfit": staticmethod(_make_calc_profit(m["profit_tokens"], initial, prices)),
    })

    actions = []
    for a in m["actions"]:
        solidity = a["solidity"]
        num_inputs = solidity.count("$$")
        if "collector" in a:
            raise ValueError("action {}: the 'collector' field was removed. Rely on the "
                             "derived collector (from effects/tokens_out), or record an "
                             "internal value inline with collect.spent/gained(...) in "
                             "solidity.".format(a["name"]))
        attrs = {
            "approximators": NumericalApproximatorsPro(),
            "numInputs": num_inputs,
            "tokensIn": list(a["tokens_in"]),
            "tokensOut": list(a["tokens_out"]),
            "range": list(a["range"]),
            "actionStr": classmethod(_make_action_str(a["name"], solidity)),
        }
        measures = _measures_for(a)
        # (token, decimals) in effect (collected) order; the parser maps a named collector revert to
        # positions with the names (emit order need not match) and scales each raw value by
        # the decimals. token_info[tok] = (var, decimals[, "native"]).
        attrs["_measured_tokens"] = [(tok, token_info[tok][1]) for tok, _ in measures]
        if "collect.spent" in solidity or "collect.gained" in solidity:
            attrs["collectorStr"] = classmethod(_make_inline_collector())              # Mode B: author records inline
        else:
            attrs["collectorStr"] = classmethod(_make_collect_collector(measures, token_info))  # Mode A: derived
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
