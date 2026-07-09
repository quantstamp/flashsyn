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


class HarvestUSDCAction(ActionPro):
    # Capital the historical exploit flash-loaned; profit is measured against these.
    initialBalances = {"USDT": 50000000, "USDC": 20000000}  # keep consistent with the foundry script

    currentBalances = initialBalances.copy()  # Don't change

    # Both legs are USD stablecoins, so profit is just the summed balance change.
    TokenPrices = {"USDT": 1.0, "USDC": 1.0}

    TargetTokens = TokenPrices.keys()    # Don't change: tokens of interest

    tokenInfo = {"USDT": ("USDT", 6), "USDC": ("USDC", 6), "fUSDT": ("fUSDT", 6)}

    # No start_str literal: the engine reads the harness preamble straight from
    # examples/harvest_usdc/attack.t.sol (copied into src/foundryModule/src/test/).
    # See ActionPro.start_str and forge/forgeCollectDVD.py.

    # stats = [USDT balance, USDC balance] (whole tokens), parsed from profitSummary().
    def calcProfit(stats):
        if stats == None or len(stats) != 2:
            return 0
        return (stats[0] - HarvestUSDCAction.initialBalances['USDT']) \
             + (stats[1] - HarvestUSDCAction.initialBalances['USDC'])

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


class Curve_USDC2USDT(HarvestUSDCAction):
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




class Curve_USDT2USDC(HarvestUSDCAction):
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




class fUSDT_deposit(HarvestUSDCAction):
    approximators = NumericalApproximatorsPro()

    numInputs = 1
    tokensIn = ['USDT']
    tokensOut = ['fUSDT']
    range = [0, 50000000]

    @classmethod
    def actionStr(cls):
        action = '''        // Action: fUSDT_deposit
        fUSDT.deposit($$ * 1e6);
        '''
        return action




class fUSDT_withdraw(HarvestUSDCAction):
    approximators = NumericalApproximatorsPro()

    numInputs = 1
    tokensIn = ['fUSDT']
    tokensOut = ['USDT']
    range = [0, 60000000]

    @classmethod
    def actionStr(cls):
        action = '''        // Action: fUSDT_withdraw
        fUSDT.withdraw($$ * 1e6);
        '''
        return action




# Longest attack sequence the synthesizer searches (the known exploit is length 4).
MAX_SYNTHESIS_LEN = 4


def flashsyn_setup():
    """Wire up config + the action DAG. Returns the pieces the flashsyn CLI drives.

    The CLI (flashsyn.py) calls this once, then runs either data collection or
    synthesis — no more editing main() to toggle between the two.
    """
    config.ExecutionMode = DVD
    config.command = "./run.sh Harvest_USDC ETH 11129500"
    config.benchmarkName = "harvest_usdc"

    action1 = Curve_USDC2USDT
    action2 = Curve_USDT2USDC
    action3 = fUSDT_deposit
    action4 = fUSDT_withdraw
    action_list = [action1, action2, action3, action4]

    # If unsure about prestates, list all other actions (safe default).
    action1_prestate_dependency = [action2, action3, action4] + [action1]
    action2_prestate_dependency = [action1, action3, action4] + [action2]
    action3_prestate_dependency = [action1, action2, action4] + [action3]
    action4_prestate_dependency = [action1, action2, action3] + [action4]
    actionDependencies = [action1_prestate_dependency, action2_prestate_dependency,
                          action3_prestate_dependency, action4_prestate_dependency]

    attackDAGGenerator.setActionDependency(generateActionDependency(action_list, actionDependencies))

    return {"wrapper": HarvestUSDCAction, "actions": action_list,
            "dependencies": actionDependencies, "max_len": MAX_SYNTHESIS_LEN}


def main():
    # Preferred entrypoint: `python3 flashsyn.py collect harvest_usdc`.
    # Running this file directly still does one data-collection pass.
    setup = flashsyn_setup()
    setup["wrapper"].initialPass(setup["actions"], setup["dependencies"], setup["wrapper"])


if __name__ == "__main__":
    main()
