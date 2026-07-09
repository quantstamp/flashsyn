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
"""
import tomllib

import config
from Actions.macros import DVD
from Actions.UtilsPrecision import NumericalApproximatorsPro
from Actions.AttackDAG import attackDAGGenerator, generateActionDependency
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

    actions = []
    for a in m["actions"]:
        solidity = a["solidity"]
        cls = type(a["name"], (wrapper,), {
            "approximators": NumericalApproximatorsPro(),
            "numInputs": solidity.count("$$"),
            "tokensIn": list(a["tokens_in"]),
            "tokensOut": list(a["tokens_out"]),
            "range": list(a["range"]),
            "actionStr": classmethod(_make_action_str(a["name"], solidity)),
        })
        actions.append(cls)

    config.ExecutionMode = DVD
    config.command = "./run.sh {} {} {}".format(m["contract"], m["chain"], m["block"])
    config.benchmarkName = m["name"]

    # Safe default: every action's prestate may be reached by running all the others.
    dependencies = [[b for b in actions if b is not a] + [a] for a in actions]
    attackDAGGenerator.setActionDependency(generateActionDependency(actions, dependencies))

    return {"wrapper": wrapper, "actions": actions, "dependencies": dependencies,
            "max_len": m.get("max_synthesis_len", len(actions))}
