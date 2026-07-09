import random
import config
import os, sys
import itertools, pickle
import copy
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
from forge.forgeCollectDVD import *
from forge.forgeCollect import *

from Actions.Action import *
from Actions.prune import *


# Given a list of lower bounds and upper bounds
# Return <target> randomly sampled points. 
# randomlyPickUpPoints([[0, 343], [0, 234]], 5)
# 
def sampleFromdataPoints(Actionist):
    dataPointUpperLimit = config.dataPointUpperLimit
    for Action in Actionist:
        if hasattr(Action, 'values') and len(Action.points) > dataPointUpperLimit:
            random.seed(123)
            index = range(len(Action.points))
            index_values = random.sample(index, dataPointUpperLimit)
            # print(Action.string())
            # print("len(Action.points): ", len(Action.points))
            # print("dataPointUpperLimit: ", dataPointUpperLimit)
            for i in range(len(Action.values)):
                temp = []
                for index in index_values:
                    temp.append(Action.values[i][index])
                Action.values[i] = temp.copy()
            temp2 = []
            for index in index_values:
                temp2.append(Action.points[index])
            Action.points = temp2


def randomlyPickUpPoints(bounds, target = 5):
    bb = []
    for _ in range(target):
        oneTry = []
        for bound in bounds:
            oneTry.append(random.randint(bound[0], bound[1]))
        bb.append(oneTry)
    return bb

# Removing duplicates from a list of lists
# array: list of lists
#        e.g. [[1,2,3], [1,2,3], [1,2,3]]
def removeDuplicates(array):
    array.sort()
    newArray = list(array for array, _ in itertools.groupby(array))
    return newArray


def AddDataPoints(datapoints, action_list):
    count = 0
    revert_count = 0
    exists_count = 0
    datapoints = removeDuplicates(datapoints)
    for datapoint in datapoints:
        if datapoint[1] != None and len(datapoint[1]) > 1:
            ret = action_list[-1].addDataPoint(datapoint[0], datapoint[1])
            if ret == 1:
                count += 1
            elif ret == -1:
                revert_count += 1
            elif ret == -2:
                exists_count += 1
        elif datapoint[1] != None and len(datapoint[1]) == 1 and datapoint[1][0] != 0:
            ret = action_list[-1].addDataPoint(
                datapoint[0], datapoint[1])
            if ret == 1:
                count += 1
            elif ret == -1:
                revert_count += 1
            elif ret == -2:
                exists_count += 1
    return count, revert_count, exists_count


# Given a list of Actions cA,
# Return a list of lower bounds and upper bounds
# eg. [[0, 13], [0, 123432], [0, 45435], [0, 3244543]]
def collectBounds(cA):
    bounds = []
    for action in cA:
        if action.numInputs == 1:
            max = action.range[1]
            min = action.range[0]
            bounds.append([min, max])
        elif action.numInputs == 2:
            max = action.range[1]
            min = action.range[0]
            max2 = action.range2[1]
            min2 = action.range2[0]
            bounds.append([min, max])
            bounds.append([min2, max2])
    return bounds

def permutation(aList):
    a = list(itertools.permutations(aList))
    return a


def combinationActions(ActionWrapper, ActionList, ActionToCollect, maxLen = 4):
    actionlistPermutations = permutation(ActionList)
    # print( len(actionlistPermutations) )
    # print(actionlistPermutations)
    out = []
    # check if single action is feasible
    if isFeasible(ActionWrapper, [ActionToCollect], False):
        out.append((ActionToCollect, ))
    for actionlistPermutation in actionlistPermutations:
        for i in range(1, len(actionlistPermutation) + 1):
            temp = actionlistPermutation[0:i]
            seq = temp + (ActionToCollect, )
            if len(seq) > maxLen:
                continue
            # print(seq)
            if seq not in out:
                out.append(seq)
    return out


def myrange(Min, Max, points_per_action):
    new_points_per_action = builtins.max(1, points_per_action // 3)
    range1 = range(Min, Min + (Max - Min) // 100, builtins.max(1,(Max - Min) // (100 * new_points_per_action)))
    range2 = range(Min + (Max - Min) // 100, Min + (Max - Min) // 10, builtins.max(1, ((Max - Min) // 10 - (Max - Min) // 100) // new_points_per_action))
    range3 = range(Min + (Max - Min) // 10, Min + (Max - Min), builtins.max(1,((Max - Min) - (Max - Min) // 10) // new_points_per_action))
    out = list(range1) + list(range2) + list(range3)
    return out


# action_lists = [[action1, action2, action3, action4],
#                 [action2, action3, action4, action4]]
def initialPassCollectData(action_lists, ActionWrapper, TargetDataPoints = 1000):
    # For each action, sample some dependency for it. 
    random.seed(123)

    for ii in range(len(action_lists)):
        action_list = action_lists[ii]
        cAs = combinationActions(ActionWrapper, action_list[:-1], action_list[-1])

        # filter out infeasible ones
        new_cAs = []
        for cA in cAs:
            if isFeasible(ActionWrapper, cA, False):
                new_cAs.append(cA)
        print(action_list[-1].__name__, "to collect")
        print("num of traces: ", len(new_cAs))
        
        # For each action inside target_action's dependency, want to make sure it is executed at least once
        N = len(action_list) - 1
        EachActionDependency = [ [] for _ in range(N)]
        for jj in range(len(action_list) - 1):
            for cA in new_cAs:
                if action_list[jj] in cA:
                    EachActionDependency[jj].append(cA)
            print("new_cA contains ", len(EachActionDependency[jj]), "traces that contains ", action_list[jj].__name__ )
        # Last add target action itself
        EachActionDependency.append([ [action_list[-1]] ])

        NonValidEachActionDependency = []
        totalCount = 0
        for totalPoints in [TargetDataPoints, 2000]:
            # just target action
            for ActionDependency in EachActionDependency:
                for cA in ActionDependency:
                    if cA in NonValidEachActionDependency:
                        continue
                    sample = ActionWrapper.buildCollectorContract(cA)
                    attackContract = sample
                    print(ToString(cA))
                    
                    forge = ForgeDataCollectorDVD(ActionWrapper)
                    forge.initializeAttackContract(attackContract)

                    bounds = collectBounds(cA)

                    para_product = randomlyPickUpPoints(bounds, totalPoints)
                    forge.cleanDataCollector()
                    for pp in para_product:
                        forge.addDataCollector(pp)
                    forge.updateDataCollectorContract()
                    datapoints = forge.executeCollectData()
                    print("data points tried: ", len(datapoints))

                    count = 0
                    revert_count = 0
                    exists_count = 0
                    datapoints = removeDuplicates(datapoints)
                    for datapoint in datapoints:
                        if datapoint[1] != None and len(datapoint[1]) > 1:
                            ret = action_list[-1].addDataPoint(
                                datapoint[0], datapoint[1])
                            if ret == 1:
                                count += 1
                            elif ret == -1:
                                revert_count += 1
                            elif ret == -2:
                                exists_count += 1
                        elif datapoint[1] != None and len(datapoint[1]) == 1 and datapoint[1][0] != 0:
                            ret = action_list[-1].addDataPoint(
                                datapoint[0], datapoint[1])
                            if ret == 1:
                                count += 1
                            elif ret == -1:
                                revert_count += 1
                            elif ret == -2:
                                exists_count += 1

                    print("current goal totalPoints = ", totalPoints)
                    totalCount += count
                    print("data points collected in this seq: ", count, "  total data points collected: ",
                        totalCount, "and ", len(action_list[-1].values[0]))
                    # print("     data points reverted: ", revert_count) #  always equal to 0
                    print("data points that already exist: ", exists_count)

                    if count == 0 and exists_count == 0:
                        NonValidEachActionDependency.append(cA)

                    if count > 0:
                        break

            if totalCount >= TargetDataPoints:
                break
        if totalCount == 0:
            exit()

def initialPassCollectData2(action_lists, ActionWrapper, TargetDataPoints = 1000):
    # Count # of tries
    for ii in range(len(action_lists)):
        action_list = action_lists[ii]
        cAs = combinationActions(ActionWrapper, action_list[:-1], action_list[-1])
        totalCount = len(cAs)
        for cA in cAs:
            if not isFeasible(ActionWrapper, cA, False):
                totalCount -= 1
        print(action_list[-1].__name__, "to collect")
        print("num of traces: ", totalCount)

    for ii in range(len(action_lists)):
        action_list = action_lists[ii]
        cAs = combinationActions(ActionWrapper, action_list[:-1], action_list[-1])

        totalCount = 0
        for totalPoints in [TargetDataPoints / 5 * 2]:
            for cA in cAs:
                if not isFeasible(ActionWrapper, cA, False):
                    continue
                print(cA)
                if len(cA) == 6 and cA[0].string() == "SwapPancakeWBNB2LP" \
                    and cA[1].string() == "TransferLPStrategy" \
                    and cA[2].string() == "DepositStrategy" \
                    and cA[3].string() == "SwapPancakeWBNB2SHARK" \
                    and cA[4].string() == "TransferSHARKStrategy" \
                    and cA[5].string() == "GetRewardStrategy":
                    break
                sample = ActionWrapper.buildCollectorContract(cA)
                attackContract = sample

                forge = ForgeDataCollectorDVD(ActionWrapper)
                forge.updateAttackContract(attackContract)


                para_append = []
                numParas = 0
                for i in range(len(cA)):
                    numParas += cA[i].numInputs

                para_product = None
                if numParas == 0:
                    para_product = [[]]
                else:
                    points_per_action = int(totalPoints ** (1 / numParas))

                    for action in cA:
                        if action.numInputs == 1:
                            max = action.range[1]
                            min = action.range[0]
                            # paras_this_action = range(min, max, (max - min) // points_per_action)
                            paras_this_action = myrange(min, max, points_per_action)
                            para_append.append(paras_this_action)
                        elif action.numInputs == 2:
                            max = action.range[1]
                            min = action.range[0]
                            max2 = action.range2[1]
                            min2 = action.range2[0]
                            paras_this_action = myrange(min, max, points_per_action)
                            paras_this_action2 = myrange(min2, max2, points_per_action)
                            para_append.append(paras_this_action)
                            para_append.append(paras_this_action2)

                    para_product = list(itertools.product(*para_append))

                forge.cleanDataCollector()
                for pp in para_product:
                    forge.addDataCollector(pp)

                forge.updateDataCollectorContract()
                datapoints = forge.executeCollectData()
                print("data points tried: ", len(datapoints))
                count = 0
                revert_count = 0
                exists_count = 0

                datapoints = removeDuplicates(datapoints)

                for datapoint in datapoints:
                    if datapoint[1] != None and len(datapoint[1]) > 1:
                        ret = action_list[-1].addDataPoint(
                            datapoint[0], datapoint[1])
                        if ret == 1:
                            count += 1
                        elif ret == -1:
                            revert_count += 1
                        elif ret == -2:
                            exists_count += 1
                    elif datapoint[1] != None and len(datapoint[1]) == 1 and datapoint[1][0] != 0:
                        ret = action_list[-1].addDataPoint(
                            datapoint[0], datapoint[1])
                        if ret == 1:
                            count += 1
                        elif ret == -1:
                            revert_count += 1
                        elif ret == -2:
                            exists_count += 1

                print("current goal totalPoints = ", totalPoints)
                totalCount += count
                print("data points collected in this seq: ", count, "  total data points collected: ",
                      totalCount, "and ", len(action_list[-1].values[0]))
                # print("     data points reverted: ", revert_count) #  always equal to 0
                print("data points that already exist: ", exists_count)

                if len(action_list[-1].values) == 1 and totalCount > 200 and \
                        (type(action_list[-1]).__name__ != "RefreshCheeseBank"):
                    break

            if totalCount > 10:
                break

        if totalCount == 0:
            exit()


def createCacheFolder():
    path = os.path.dirname(os.path.dirname(SCRIPT_DIR)) + "/initialDataPoints/" + config.benchmarkName + "/"
    if not os.path.exists( path ):
        os.makedirs(path)

def storeDataPoints(ActionList, points: list, values: list, append: bool = False):
    """Given an action list, store the data into corresponding cache files.

    The payload is [points, values, names]; `names` (the action __name__s) is the
    authoritative sequence, so loaders no longer parse it back out of the filename.
    The filename is still the "_"-joined names, but only for human browsing now.
    """
    names = [action.__name__ for action in ActionList]
    name = "_".join(names)
    path = os.path.dirname(os.path.dirname(SCRIPT_DIR)) + "/initialDataPoints/" + \
        config.benchmarkName + "/" + name + ".pkl"

    new_points = []
    new_values = []

    if os.path.exists(path) and append:
        with open(path, 'rb') as f:
            payload = pickle.load(f)
            old_points, old_values = payload[0], payload[1]
            new_points = old_points + points
            new_values = old_values
            for i in range(len(old_values)):
                new_values[i] = old_values[i] + values[i]
    else:
        new_points = points
        new_values = values

    with open(path, 'wb') as f:
        pickle.dump([new_points, new_values, names], f)
    
def loadDataPoints():
    path = os.path.dirname(os.path.dirname(SCRIPT_DIR)) + "/initialDataPoints/" + \
        config.benchmarkName + "/"
    files = os.listdir(path)
    pickle_files = [file for file in files if file.endswith('.pkl')]
    map = {}
    for file in pickle_files:
        file_path = os.path.join(path, file)
        with open(file_path, 'rb') as f:
            map[file[:-4]] = pickle.load(f)
    return map

    
    # """Given an action list, load the data from corresponding cache files"""
    # name = ""
    # for action in ActionList:
    #     name += action.string() + "_"
    # name = name[:-1]
    # path = os.path.dirname(os.path.dirname(SCRIPT_DIR)) + "/initialDataPoints/" + \
    #     config.benchmarkName + "/" + name + ".pkl"
    # with open(path, 'rb') as f:
    #     data = pickle.load(f)
    # return data[0], data[1] # points, values

def initialPassCollectData3(action_lists, ActionWrapper, TargetDataPoints = 1000):
    # For each action, sample some dependency for it. 
    random.seed(123)

    # clean the cached data points. 
    directory = os.path.dirname(os.path.dirname(SCRIPT_DIR)) + "/initialDataPoints/" + config.benchmarkName
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
                print(f"Deleted {filename}")
        except Exception as e:
            print(f"Error deleting {filename}: {e}")


    # permutations of preceding actions
    for ii in range(len(action_lists)):
        action_list = action_lists[ii]
        cAs = combinationActions(ActionWrapper, action_list[:-1], action_list[-1])
        # filter out infeasible ones
        new_cAs = []
        for cA in cAs:
            if isFeasible(ActionWrapper, cA, False):
                new_cAs.append(cA)
        print(action_list[-1].__name__, "to collect")
        print("num of traces: ", len(new_cAs))
        # For each action inside target_action's dependency, want to make sure it is executed at least once
        N = len(action_list) - 1
        EachActionDependency = [ [] for _ in range(N)]
        for jj in range(len(action_list) - 1):
            for cA in new_cAs:
                if action_list[jj] in cA and cA not in EachActionDependency[jj]:
                    EachActionDependency[jj].append(cA)
            print("new_cA contains ", len(EachActionDependency[jj]), "traces that contains ", action_list[jj].__name__ )
        # Last add target action itself
        EachActionDependency.append([ [action_list[-1]] ])

        NonValidEachActionDependency = []
        totalCount = 0
        for totalPoints in [TargetDataPoints, 2000]:
            # just target action
            for ActionDependency in EachActionDependency:
                for cA in ActionDependency:
                    if cA in NonValidEachActionDependency:
                        continue
                    sample = ActionWrapper.buildCollectorContract(cA)
                    attackContract = sample
                    print(ToString(cA))

                    forge = ForgeDataCollectorDVD(ActionWrapper)
                    forge.initializeAttackContract(attackContract)

                    bounds = collectBounds(cA)

                    para_product = randomlyPickUpPoints(bounds, totalPoints)
                    forge.cleanDataCollector()
                    for pp in para_product:
                        forge.addDataCollector(pp)
                    forge.updateDataCollectorContract()
                    datapoints = forge.executeCollectData()
                    print("data points tried: ", len(datapoints))

                    count = 0
                    revert_count = 0
                    exists_count = 0
                    datapoints = removeDuplicates(datapoints)

                    maxLen = 0
                    for datapoint in datapoints:
                        if datapoint[1] != None and len(datapoint[1]) > 1:
                            maxLen = max(maxLen, len(datapoint[1]))

                    points = []
                    values = []
                    for ii in range(maxLen):
                        values.append([])
                    if action_list[-1].__name__ != cA[-1].__name__:
                        sys.exit("action_list[-1].__name__ != cA[-1].__name__")
                    for datapoint in datapoints:
                        if datapoint[1] != None and len(datapoint[1]) > 1:
                            ret = action_list[-1].addDataPoint(datapoint[0], datapoint[1], cA)
                            if ret == 1:
                                count += 1
                            elif ret == -1:
                                revert_count += 1
                            elif ret == -2:
                                exists_count += 1
                        elif datapoint[1] != None and len(datapoint[1]) == 1 and datapoint[1][0] != 0:
                            ret = action_list[-1].addDataPoint(datapoint[0], datapoint[1], cA)
                            if ret == 1:
                                count += 1
                            elif ret == -1:
                                revert_count += 1
                            elif ret == -2:
                                exists_count += 1
                    print("current goal totalPoints = ", totalPoints)
                    totalCount += count
                    print("data points collected in this seq: ", count, "  total data points collected: ",
                        totalCount )
                    # print("     data points reverted: ", revert_count) #  always equal to 0
                    print("data points that already exist: ", exists_count)
                    if count > 0:
                        storeDataPoints(cA, action_list[-1].approximators.points(cA), action_list[-1].approximators.values(cA), append=True)

                    if count == 0 and exists_count == 0:
                        NonValidEachActionDependency.append(cA)
                    # if count > 0:
                    #     break
            if totalCount >= TargetDataPoints:
                break
        if totalCount == 0:
            exit()




def extraTokens( tokens, existingActions, ActionWrapper):
    new_tokens = []
    for token in tokens:
        hasIt = False
        for action in existingActions:
            if token in action.tokensOut:
                hasIt = True
                break
        if hasIt:
            continue
        if token not in ActionWrapper.initialBalances.keys():
            new_tokens.append(token)
    return new_tokens


def initialPassCollectData4(actionSpecs, ActionWrapper, TargetDataPoints = 1000, maxLenGlobal = 4):
    ### TODO: infer necessary prefix actions

    # step 0: delete all cached data points.
    random.seed(123)
    directory = os.path.dirname(os.path.dirname(SCRIPT_DIR)) + "/initialDataPoints/" + config.benchmarkName
    if not os.path.exists(directory):
        os.makedirs(directory)
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
                print(f"Deleted {filename}")
        except Exception as e:
            print(f"Error deleting {filename}: {e}")

    # step 1: add extra actions which grants tokensIn of every action 
    actionList = []
    for actionSpec in actionSpecs:
        actionList.append( copy.deepcopy( actionSpec[-1] ) )

    for jj in range(len(actionSpecs)):

        actionSpec = copy.deepcopy(actionSpecs[jj])
        extraActions = []
        # actionSpec is actionADependencies + actionA itself 

        ii = -1
        while ii < len(actionSpec) - 1:
            ii += 1
            tokensIn = actionSpec[ii].tokensIn
            tokensNeeded = [x for x in tokensIn if x not in ActionWrapper.initialBalances.keys()]
            for action in actionSpec:
                tokensNeeded = [x for x in tokensNeeded if x not in action.tokensOut]
            if len(tokensNeeded) == 0:
                continue
            # otherwise, do a BFS to find the shortest path to get tokensIn
            # BFS
            queue = [ ([action], tokensNeeded) ]
            # (actionList, tokenNeeded)
            # initialize
            findAPath = False
            shortestPath = None
            while True:
                paths, tokensNeeded = queue.pop(0)
                for action2 in [x for x in actionList if x not in paths]:
                    if set(action2.tokensOut) & set(tokensNeeded):  # if action2.tokensOut contains any token in tokensNeeded
                        paths.append(action2)
                        new_tokensNeeded = copy.deepcopy([x for x in tokensNeeded if x not in action2.tokensOut])
                        new_tokensNeeded += action2.tokensIn
                        new_tokensNeeded = [x for x in new_tokensNeeded if x not in ActionWrapper.initialBalances.keys()]
                        if len(new_tokensNeeded) == 0:
                            findAPath = True
                            shortestPath = paths
                            break
                        queue.append((paths, new_tokensNeeded))
                if findAPath:
                    break
            extraActions = [x for x in shortestPath if x not in actionSpec]
            # add extra actions
            actionSpec.insert(0, extraActions)
            actionSpecs[jj] = copy.deepcopy(actionSpec)
            ii = -1



    # permutations of preceding actions
    for ii in range(len(actionSpecs)):

        if not hasattr(actionList[ii], 'collectorStr'):
            print(actionList[ii].__name__, "to collect")
            print("skip")

            continue
        
        # ii = 3
        action_list = copy.deepcopy(actionSpecs[ii])

        ### Should have a better way of enumerating all possible combination... 04/28/2023
        cAs = combinationActions(ActionWrapper, action_list[:-1], action_list[-1], maxLen=maxLenGlobal)
        # filter out infeasible ones
        new_cAs = []
        for cA in cAs:
            if isFeasible(ActionWrapper, cA, False):
                new_cAs.append(cA)
        
        
        print(action_list[-1].__name__, "to collect")
        print("num of traces: ", len(new_cAs))
        # For each action inside target_action's dependency, want to make sure it is executed at least once
        N = len(action_list) - 1
        EachActionDependency = [ [] for _ in range(N)]
        for jj in range(len(action_list) - 1):
            for cA in new_cAs:
                if action_list[jj] in cA and cA not in EachActionDependency[jj]:
                    EachActionDependency[jj].append(cA)
            print("new_cA contains ", len(EachActionDependency[jj]), "traces that contains ", action_list[jj].__name__ )
        # Last add target action itself
        EachActionDependency.append([ [action_list[-1]] ])

        NonValidEachActionDependency = []
        totalCount = 0


        for totalPoints in [TargetDataPoints, int(TargetDataPoints/2), int(TargetDataPoints*2)]:
            # just target action
            for old_cA in new_cAs:
                cA = copy.deepcopy(old_cA)
                if cA in NonValidEachActionDependency:
                    continue
                sample = ActionWrapper.buildCollectorContract(cA)
                attackContract = sample
                print(ToString(cA))

                forge = None
                if config.ExecutionMode == 2:
                    forge = ForgeDataCollectorDVD(ActionWrapper)
                    forge.addAttackContract(attackContract)
                else:
                    forge = ForgeDataCollector(
                        config.contract_name, config.initialEther, config.blockNum)  # need to be modified
                    forge.initializeAttackContract(ActionWrapper)
                    forge.addAttackContract(attackContract)

                
                
                bounds = collectBounds(cA)
                para_product = randomlyPickUpPoints(bounds, totalPoints)
                forge.cleanDataCollector()
                for pp in para_product:
                    forge.addDataCollector(pp)
                forge.updateDataCollectorContract()
                datapoints = forge.executeCollectData()
                print("data points tried: ", len(datapoints))

                count = 0
                revert_count = 0
                exists_count = 0
                datapoints = removeDuplicates(datapoints)

                maxLen = 0
                for datapoint in datapoints:
                    if datapoint[1] != None:
                        maxLen = max(maxLen, len(datapoint[1]))

                points = []
                values = []
                for ii in range(maxLen):
                    values.append([])
                if action_list[-1].__name__ != cA[-1].__name__:
                    sys.exit("action_list[-1].__name__ != cA[-1].__name__")
                for datapoint in datapoints:
                    if datapoint[1] != None and len(datapoint[1]) > 1:
                        ret = action_list[-1].addDataPoint(datapoint[0], datapoint[1], cA)
                        if ret == 1:
                            count += 1
                        elif ret == -1:
                            revert_count += 1
                        elif ret == -2:
                            exists_count += 1
                    elif datapoint[1] != None and len(datapoint[1]) == 1 and datapoint[1][0] != 0:
                        ret = action_list[-1].addDataPoint(datapoint[0], datapoint[1], cA)
                        if ret == 1:
                            count += 1
                        elif ret == -1:
                            revert_count += 1
                        elif ret == -2:
                            exists_count += 1
                print("current goal totalPoints = ", totalPoints)
                totalCount += count
                print("data points collected in this seq: ", count, "  total data points collected: ",
                    totalCount )
                # print("     data points reverted: ", revert_count) #  always equal to 0
                print("data points that already exist: ", exists_count)
                if count > 0:
                    storeDataPoints(cA, action_list[-1].approximators.points(cA), action_list[-1].approximators.values(cA), append=True)

                if count == 0 and exists_count == 0:
                    NonValidEachActionDependency.append(cA)
                # if count > 0:
                #     break
            if totalCount >= TargetDataPoints:
                break

        if totalCount == 0:
            exit()
