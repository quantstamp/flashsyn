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
    @classmethod
    def string(cls):
        return cls.__name__

    @classmethod
    def __str__(cls):
        return cls.__name__
    
    def __str__(self):
        return  self.__name__
    

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
        initialPassCollectData4( actionSpecs , ActionWrapper, TargetDataPoints = 2000, maxLenGlobal = maxLen)
        ShowDataPointsForEachAction( action_list_1 )
        end = time.time()
        print("in total it takes %f seconds" % (end - start))





    @classmethod
    def aliquotValues(cls, values):
        return values
    

    @classmethod
    def add1PointValue(cls, inputs, values, actionList):
        if values == None: 
            return
        values = cls.aliquotValues(values)
        return cls.approximators.add1PointValue( inputs, values, actionList )

    @classmethod
    def refreshTransitFormula(cls):
        cls.approximators.refreshTransitFormula()


    @classmethod
    def simulate(cls, inputs, actionList):
        return cls.approximators(inputs, actionList)