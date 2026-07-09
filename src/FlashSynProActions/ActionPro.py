import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
sys.path.append(os.path.dirname(os.path.dirname(SCRIPT_DIR)))

from Actions.UtilsDVD import * 

from Actions.Utils import *
from Actions.UtilsPrecision import *
from Actions.Action import *
from Actions.AttackDAG import *


def ToString(action_list):
    temp = ""
    for ii in range(len(action_list)):
        if ii != len(action_list) - 1:
            temp += action_list[ii].__name__ + ", "
        else:
            temp += action_list[ii].__name__
    return temp



class ActionPro():
    # The Solidity preamble (interfaces + contract + setUp + profitSummary) the
    # generated collectors are appended to. Leave it as this default '' and the
    # engine reads the preamble straight from the authored attack.t.sol instead
    # (see forge/forgeCollectDVD.py) — one source of truth, no duplication. Only
    # set it to a literal to override that (the Euler example still does).
    start_str = ''

    # Per-token Solidity metadata for the auto-generated collector:
    #   {"USDC": ("USDC", 6)} = (the token's contract variable in the harness, its decimals).
    # Set this on the action wrapper so a plain swap/deposit/withdraw action only has
    # to write actionStr() — collectorStr() and transit() are derived from it below.
    tokenInfo = {}

    # How many data points initialPass() aims to collect per action.
    TARGET_DATA_POINTS = 500

    @classmethod
    def string(cls):
        return cls.__name__

    def __str__(self):
        return self.__name__
    

    @classmethod
    def action_by_name(cls, name):
        """Resolve an action class by its __name__ from the ActionPro subclass tree.

        Replaces `globals()[name]` lookups: those only saw the caller module's
        namespace, coupling saved data files to source symbol locations. This
        walks every ActionPro subclass instead, so any defined action is found
        regardless of which module it or the caller lives in.
        """
        stack = list(ActionPro.__subclasses__())
        seen = set()
        while stack:
            sub = stack.pop()
            if sub in seen:
                continue
            seen.add(sub)
            if sub.__name__ == name:
                return sub
            stack.extend(sub.__subclasses__())
        raise KeyError("no ActionPro subclass named {!r}".format(name))

    @classmethod
    def resetBalances(cls):
        cls.currentBalances = cls.initialBalances.copy()

    @classmethod
    def calcProfit2(cls):
        profit = 0
        for token in cls.currentBalances.keys():
            currentBalance = cls.currentBalances[token]
            earned = currentBalance
            if token in cls.initialBalances.keys():
                initialBalance = cls.initialBalances[token]
                earned -= initialBalance
            if token in cls.TokenPrices.keys():
                profit += earned * cls.TokenPrices[token]
        return profit

    
    # Don't change
    # Used to construct the foundry script
    @classmethod
    def buildAttackContract(cls, ActionList):
        cls.attack_str = buildDVDattackContract(ActionList) + "       revert(profitSummary());\n"
        return cls.attack_str   
    

    # Don't change
    # Used to construct the foundry script 
    @classmethod
    def buildCollectorContract(cls, ActionList):
        cls.collector_str = buildDVDCollectorContract(ActionList)
        return cls.collector_str

    def ToString(ActionList):
        return ToString(ActionList)


    @classmethod
    def initialPass(cls, actionList, actionDependencies, ActionWrapper, maxLen = None):
        if maxLen == None:
            largestLen = 0
            for actionDependency in actionDependencies:
                if len(actionDependency) > largestLen:
                    largestLen = len(actionDependency)
            maxLen = largestLen

        action_list_1 = actionList
        # seq of actions
        actionSpecs = []
        for ii in range(len(actionDependencies)):
            temp = actionDependencies[ii] + [actionList[ii]] 
            actionSpecs.append( temp )
        start = time.time()
        initialPassCollectData4( actionSpecs , ActionWrapper, TargetDataPoints = cls.TARGET_DATA_POINTS, maxLenGlobal = maxLen)
        ShowDataPointsForEachAction( action_list_1 )
        end = time.time()
        print("in total it takes %f seconds" % (end - start))

    @classmethod
    def runinitialPass(cls):
        # Build one approximator per terminal action from the collected data.
        # Action sequences come from each pkl's saved names; classes are resolved
        # via the registry (action_by_name), not by splitting the filename.
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





    @classmethod
    def aliquotValues(cls, values):
        return values
    

    @classmethod
    def addDataPoint(cls, inputs, values, actionList):
        if values == None: 
            return
        values = cls.aliquotValues(values)
        return cls.approximators.addDataPoint( inputs, values, actionList )

    @classmethod
    def refreshTransitFormula(cls):
        cls.approximators.refreshTransitFormula()


    @classmethod
    def simulate(cls, inputs, actionList):
        return cls.approximators(inputs, actionList)

    @classmethod
    def collectorStr(cls):
        """Default data collector: measure each output token's balance delta.

        Wraps actionStr() between balance reads and reverts with the deltas after
        the FlashSyn marker — so a plain swap/deposit/withdraw action only writes
        actionStr(). Derived from tokensOut + tokenInfo. Override for an action
        whose measurable output isn't a simple attacker-balance delta.
        """
        if not cls.tokensOut:
            raise NotImplementedError(
                "{}: default collectorStr needs tokensOut; give the action its own "
                "collectorStr()".format(cls.__name__))
        reads = ""
        revert = None
        for i, tok in enumerate(cls.tokensOut):
            var, dec = cls.tokenInfo[tok]
            reads += "        uint _fsOut{} = {}.balanceOf(address(attacker));\n".format(i, var)
            delta = "({}.balanceOf(address(attacker)) - _fsOut{}) / 1e{}".format(var, i, dec)
            if revert is None:
                revert = 'Strings.append("FlashSyn: ", {})'.format(delta)
            else:
                revert = "Strings.appendWithSpace({}, {})".format(revert, delta)
        return "{}{}        revert({});\n".format(reads, cls.actionStr(), revert)

    @classmethod
    def transit(cls, inputs, actionList):
        """Default balance transition: consume tokensIn, produce tokensOut.

        The last len(tokensIn) inputs are the consumed amounts (one per input token);
        simulate() yields the produced amounts for tokensOut, in order. Override for
        an action that moves funds in a way this 1:1 mapping doesn't capture.
        """
        consumed = inputs[-len(cls.tokensIn):] if cls.tokensIn else []
        for tok, amt in zip(cls.tokensIn, consumed):
            cls.currentBalances[tok] = cls.currentBalances.get(tok, 0) - amt
        outputs = cls.simulate(inputs, actionList)
        for i, tok in enumerate(cls.tokensOut):
            cls.currentBalances[tok] = cls.currentBalances.get(tok, 0) + outputs[i]