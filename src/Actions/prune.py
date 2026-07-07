import inspect
from Actions.AttackDAG import *




# this function is only for initial data collection 
def checkifFeasible(ActionWrapper, ActionList, isPartial=True):
    # Pruning 0: each action can only be used at most maxTime
    ActionMap = {}

    maxTime = 2
    if len(ActionList) >= 6:
        maxTime = 1

    for Action in ActionList:
        # print(Action.__class__.__name__)
        if not inspect.isclass(Action): # Sketch
            continue
        # print(Action.__name__)
        if Action.__name__ not in ActionMap:
            ActionMap[Action.__name__] = 1
        else:
            ActionMap[Action.__name__] += 1
            if ActionMap[Action.__name__] > maxTime:
                return False
            # # only allow one duplicate at the end of the attack vector
            # if not isPartial and ActionMap[Action.__name__] == maxTime and\
            #     ActionList[-1].__name__ != Action.__name__:
            #     return False

    # Pruning 1: token flow pruning
    tokensHave = ActionWrapper.initialBalances.copy()
    if isPartial:
        for Action in ActionList[0: -1]:
            for token in Action.tokensIn:
                if token not in tokensHave:
                    return False
            for token in Action.tokensOut:
                if token not in tokensHave:
                    tokensHave[token] = 0
    else:
        for Action in ActionList:
            for token in Action.tokensIn:
                if token not in tokensHave:
                    return False
            for token in Action.tokensOut:
                if token not in tokensHave:
                    tokensHave[token] = 0

                    
    # Pruning 2: no duplicate adjacent actions
    if not isPartial:
        if not inspect.isclass(ActionList[0]):
            for i in range(len(ActionList) - 1):
                if ActionList[i].__class__.__name__ == ActionList[i + 1].__class__.__name__:
                    return False
        else:
            for i in range(len(ActionList) - 1):
                if ActionList[i].__name__ == ActionList[i + 1].__name__:
                    return False


    return True


# token flow pruning(must have tokens when an action needs)
# + no duplicate adjacent actions
# + each action can only be used twice
# + no useless tokens(if a token is not in TragetTokens, there must be a path to one of target token)
# + need at least one parameter in total for non-Partial
def checkifFeasible2(ActionWrapper, ActionList, isPartial):
    # Pruning 0: each action can only be used at most maxTime
    ActionMap = {}

    maxTime = 2
    if len(ActionList) >= 6:
        maxTime = 1

    for Action in ActionList:
        # print(Action.__class__.__name__)
        if not inspect.isclass(Action): # Sketch
            continue
        # print(Action.__name__)
        if Action.__name__ not in ActionMap:
            ActionMap[Action.__name__] = 1
        else:
            ActionMap[Action.__name__] += 1
            if ActionMap[Action.__name__] > maxTime:
                return False
            # # only allow one duplicate at the end of the attack vector
            # if not isPartial and ActionMap[Action.__name__] == maxTime and\
            #     ActionList[-1].__name__ != Action.__name__:
            #     return False


    # print("Survive from Pruning 0")

    # # Pruning 1: no useless tokens
    # # Every time get some useless tokens, it must be converted into Target Tokens later
    # if not isPartial:
    #     tokensHave = ActionWrapper.initialBalances.copy()
    #     TargetTokens = ActionWrapper.TargetTokens
    #     for Action in ActionList:
    #         for token in Action.tokensIn:
    #             if token not in tokensHave:
    #                 return False
    #             else:
    #                 tokensHave[token] = -1
    #         for token in Action.tokensOut:
    #             tokensHave[token] = 0

    #     for token in tokensHave:
    #         if tokensHave[token] == 0 and token not in TargetTokens:
    #             return False
    # # print("Survive from Pruning 1")


    # Pruning 2: no duplicate adjacent actions
    if not isPartial:
        if not inspect.isclass(ActionList[0]):
            for i in range(len(ActionList) - 1):
                if ActionList[i].__class__.__name__ == ActionList[i + 1].__class__.__name__:
                    return False
        else:
            for i in range(len(ActionList) - 1):
                if ActionList[i].__name__ == ActionList[i + 1].__name__:
                    return False

    # print("Survive from Pruning 2")

    # Pruning 3: token flow pruning
    tokensHave = ActionWrapper.initialBalances.copy()
    TargetTokens = ActionWrapper.TargetTokens
    if isPartial:
        for Action in ActionList[0: -1]:
            for token in Action.tokensIn:
                if token not in tokensHave:
                    return False
            for token in Action.tokensOut:
                if token not in tokensHave:
                    tokensHave[token] = 0
    else:
        for Action in ActionList:
            for token in Action.tokensIn:
                if token not in tokensHave:
                    return False
            for token in Action.tokensOut:
                if token not in tokensHave:
                    tokensHave[token] = 0

        # print("Survive from Pruning 3.1")

    # Pruning 3: Last Action must have at least one target token!!! 
    # This heuristic is purely from a perspective of an attacker
        hasOne = False
        for token in TargetTokens:
            if token in ActionList[-1].tokensOut:
                hasOne = True
                break
        if not hasOne:
            return False
    # print("Survive from Pruning 3.2")


    # Pruning 4: at least one parameter in total for non-partial
    if not isPartial:
        total = 0
        for Action in ActionList:
            total += Action.numInputs
        if total == 0:
            return False
        
    # print("Survive from Pruning 4")


    # # Pruning 5: Actions cannot be all Curve Finance or Uniswap
    # if not isPartial:
    #     AllCurveFi = True
    #     for Action in ActionList:
    #         if not ("Curve" in Action.__name__ \
    #             or "AddLiquidityDAIUSDC" in Action.__name__ \
    #             or "AddLiquidityUSDT" in Action.__name__ \
    #             or "RemoveImbalance"  in Action.__name__\
    #             or "RemoveImbalanceDAIUSDC"  in Action.__name__\
    #             or "AddLiquidityUSDTWBTCWETHPool" in Action.__name__\
    #             or "ExchangeWBTC2USDT" in Action.__name__\
    #             or "ExchangeUSDT2WBTC" in Action.__name__ ) :
    #             AllCurveFi = False
    #             break
    #     if AllCurveFi:
    #         return False

    # print("Survive from Pruning 5")

    # Pruning 6: infeasible: reasoning from DAGs, there must be some subDAG
    if not isPartial:
        for ii in range(0, len(ActionList)):
            lastAction = ActionList[ii]
            dag, index = attackDAGGenerator.generateDAG(ActionList[0:ii+1] )

            if not hasattr(ActionList[ii], "approximators"):
                continue
            hasData = False
            indexes2Try = deque()
            indexes2Try.append(index)
            while len(indexes2Try) > 0:
                index = indexes2Try.popleft()
                if index in lastAction.approximators.dataMap and \
                    len(lastAction.approximators.dataMap[index]) > 0 and \
                    len(lastAction.approximators.dataMap[index][0]) > 0:
                    hasData = True
                    break
                else:
                    for subTreeIndex in attackDAGGenerator.subTree[index]:
                        indexes2Try.append(subTreeIndex)
            
            if not hasData:
                return False

    return True

