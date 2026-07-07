from scipy.interpolate.interpnd import NDInterpolatorBase
from numpy import array, array_equal, allclose
import numpy as np
import signal
from scipy.spatial.qhull import QhullError
from scipy.interpolate import LinearNDInterpolator
from scipy.interpolate import NearestNDInterpolator
from scipy.interpolate import interp1d
from scipy.optimize import shgo

import time, itertools, os, sys, inspect, gc, random

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
# print(sys.path)

from forge.forgeCollectDVD import *
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
parentdir = os.path.dirname(parentdir)
sys.path.insert(0, parentdir)
from Actions.prune import *
from src.Actions.UtiloptFrame import *
from Actions.initialPassCollectData import *
from Actions.Action import *


class Sketch():
    def __init__(self):
        pass

    def string(self):
        return "?"


class BarebonesNearestNDInterpolator(NearestNDInterpolator):
    def __init__(self, x, y, rescale=False, tree_options=None):
        NDInterpolatorBase.__init__(self, x, y, rescale=rescale,
                                    need_contiguous=False,
                                    need_values=False)
        if tree_options is None:
            tree_options = dict()
        # self.tree = cKDTree(self.points, **tree_options)
        self.tree = KDTree(self.points)
        self.values = np.asarray(y)

    def __call__(self, *args):
        xi = _ndim_coords_from_arrays(
            args, ndim=self.points.shape[1])   # 6.4373016357421875e-06
        xi = self._check_call_shape(xi)        # 2.6226043701171875e-06
        xi = self._scale_x(xi)                   # 1.52587890625e-05
        _, i = self.tree.query(xi, k=1)              # 0.00017404556274414062
        return self.values[i]


def intepolateFunction(points, values, indexes=[]):
    # print("points=", points)
    if len(indexes) != 0:
        newpoints = getPointsFromIndexes(points, indexes)
        return BarebonesNearestNDInterpolator(newpoints, values, rescale=True)
    return BarebonesNearestNDInterpolator(points, values, rescale=True)


def LinearintepolateFunction(points, values, indexes=[], verbose=False):
    if len(indexes) != 0:
        newpoints = getPointsFromIndexes(points, indexes)
        return LinearNDInterpolator(newpoints, values, rescale=True)
    return LinearNDInterpolator(points, values, rescale=True)


def getPointsFromIndexes(points, indexes):
    newPoints = []
    for point in points:
        newPoint = []
        for index in indexes:
            newPoint.append(point[index])
        newPoints.append(newPoint)
    return newPoints


def combinedIntepolate(Linear_f, f, point, indexes=[]):
    if len(indexes) != 0:
        newpoint = []
        for index in indexes:
            newpoint.append(point[index])
        value = Linear_f(newpoint)
        if np.isnan(value):
            value = f(newpoint)
        return value

    value = Linear_f(point)
    if np.isnan(value):
        value = f(point)
    return value


def intepolateFunction1d(points, values):
    return interp1d(points, values, kind='nearest', fill_value='extrapolate')


def LinearintepolateFunction1d(points, values):
    return interp1d(points, values, kind='linear', fill_value='extrapolate')








def buildCollectorContract(startStr_attack, ActionList, endStr_attack):
    collectorStr = startStr_attack
    input_strings = ["uint aa", ", uint bb", ", uint cc", ", uint dd", ", uint ee",
                     ", uint ff", ", uint gg", ", uint hh", ", uint ii", ", uint jj", ", uint kk"]
    insert_inside_strings = ["aa", "bb", "cc", "dd",
                             "ee", "ff", "gg", "hh", "ii", "jj", "kk"]
    allActionStr = ""
    input_attack = ""
    input_string_ptr = 0
    for i in range(len(ActionList) - 1):
        temp = ActionList[i].actionStr()

        for _ in range(ActionList[i].numInputs):
            temp = temp.replace(
                '$$', insert_inside_strings[input_string_ptr], 1)
            input_string_ptr += 1

        allActionStr += temp

    temp = ActionList[-1].collectorStr()

    for _ in range(ActionList[-1].numInputs):
        temp = temp.replace('$$', insert_inside_strings[input_string_ptr], 1)
        input_string_ptr += 1

    allActionStr += temp

    for i in range(input_string_ptr):
        input_attack += input_strings[i]

    collectorStr = collectorStr.replace("$$_$$", input_attack, 1)
    collectorStr += allActionStr
    collectorStr += endStr_attack

    return collectorStr

def buildAttackContract(startStr_attack, ActionList, endStr_attack):
    attackStr = startStr_attack
    input_strings = ["uint aa", ", uint bb", ", uint cc", ", uint dd", ", uint ee",
                     ", uint ff", ", uint gg", ", uint hh", ", uint ii", ", uint jj", ", uint kk"]
    insert_inside_strings = ["aa", "bb", "cc", "dd",
                             "ee", "ff", "gg", "hh", "ii", "jj", "kk"]
    allActionStr = ""
    input_attack = ""
    input_string_ptr = 0
    for i in range(len(ActionList)):
        temp = ActionList[i].actionStr()

        for _ in range(ActionList[i].numInputs):
            temp = temp.replace(
                '$$', insert_inside_strings[input_string_ptr], 1)
            input_string_ptr += 1

        allActionStr += temp

    for i in range(input_string_ptr):
        input_attack += input_strings[i]

    attackStr = attackStr.replace("$$_$$", input_attack, 1)
    attackStr += allActionStr
    attackStr += endStr_attack
    return attackStr





def ShowDataPointsForEachAction(actionList):
    for action in actionList:
        print("For action ", action.__name__)
        if hasattr(action, 'points'):
            print("Points length: ", len(action.points), end="   ")
            print("Value length:", len(action.values[0]))
            print(action.__name__ + ".points=", action.points)
            print(action.__name__ + ".values=", action.values)
        else:
            print("skip")

def singleEnumerate(Actions, actionWrapper, para_append):
    para_product = list(itertools.product(*para_append))
    return singleCollect(Actions, actionWrapper, para_product)

def singleCollect(Actions, actionWrapper, para_product):
    attackContract = actionWrapper.buildAttackContract(Actions)
    forge = forgedataCollectContractDVD(actionWrapper)
    forge.addAttackContract(attackContract)
    forge.cleanDataCollector()

    used = []
    for pp in para_product:
        if pp not in used:
            used.append(pp)
            forge.addDataCollector(pp)

    forge.updateDataCollectorContract()
    datapoints = forge.executeCollectData()
    return datapoints

def testOneContract(actionWrapper, paras, Action_list):
    para_append = []
    for i in range(len(paras)):
        new_para = [int(paras[i] * 98 / 100), int(paras[i]),
                    int(paras[i] * 102 / 100)]
        if min(new_para) <= 0:
            continue
        para_append.append(new_para)

    return singleEnumerate(Action_list, actionWrapper, para_append)

def testOneContract_Multiple_Points(actionWrapper, parasArr, Action_list):
    numOfSolutions = len(parasArr)
    numOfParaPerSol = len(parasArr[0])
    mode = 0

    if numOfSolutions * 3 ** numOfParaPerSol <= 2000:
        mode = 0
    elif numOfSolutions * 2 ** numOfParaPerSol <= 2000:
        mode = 1
    else:
        mode = 2

    passedParaArrs = []
    for paras in parasArr:  # iterate through solutions
        para_append = []
        for i in range(len(paras)):  # iterate through paras
            if mode == 0:
                new_para = None
                if int(paras[i] * 99 / 100) <= 0:
                    new_para = [int(paras[i]), int(
                        paras[i] * 101 / 100), int(paras[i] * 102 / 100)]
                else:
                    new_para = [int(paras[i] * 99 / 100),
                                int(paras[i]), int(paras[i] * 101 / 100)]

                para_append.append(new_para)
            elif mode == 1:
                new_para = None
                if int(paras[i] * 99 / 100) <= 0:
                    new_para = [int(paras[i]), int(paras[i] * 101 / 100)]
                else:
                    new_para = [int(paras[i] * 99 / 100), int(paras[i])]
                para_append.append(new_para)
            else:
                para_append.append([int(paras[i])])

        para_product = list(itertools.product(*para_append))
        for one_para_product in para_product:
            if one_para_product not in passedParaArrs:
                passedParaArrs.append(one_para_product)
            # if len(one_para_product) == 0:
            #     print("Now it's the time")

            #     sys.exit("Error message")

    if len(passedParaArrs) > 2000:
        print("Error happened in testOneContract_Multiple_Points")
        exit

    datapoints = singleCollect(Action_list, actionWrapper, passedParaArrs)

    # datapoints = singleCollect(Action_list, actionWrapper, parasArr)

    return datapoints



# This function is used to search for the best profit based on data points collected from initial pass.
def Optimize(action_list, ActionWrapper):
    
    bnds = getBnds(action_list)
    bnds = np.array(bnds)

    # print("ads", bnds.min())  # 1
    csts = None
    F = None
    bnds_normalised = bnds
    if config.benchmarkName == 'CheeseBank' or config.benchmarkName == 'AutoShark' \
        or config.benchmarkName == 'InverseFi':
        Scale = 1
                # 2 ===> -1576.03
                # 100 ===> 898.17
                # 10 ===> -6.92
                # 5 ===> 821.68
                # 50 ===> 2nd round: -223.63
                # 10000 ===> 2nd round:  -760.43
                # 1000 ===> 2nd round:  -7.22
                # bnds.min() = 1  ===>  2nd round: 1078.1150965363718
        bnds_normalised = [(0, Scale),]* len(bnds)  # Normalise boundaries back to a simplex
        csts = getCsts(action_list, ActionWrapper, bnds, Scale)
        F = getF(ActionWrapper, action_list, bnds, Scale)
    else:
        csts = getCsts(action_list, ActionWrapper)
        F = getF(ActionWrapper, action_list)


    # the idea of global constraint works badly
    # For Warp:  global constraint ==> takes 20 seconds to find profit of 64 0000
    # For Warp:        constraints ==> takes 25 seconds to find profit of 111 0000
    # global_csts = []
    # global_cst = {"type": "ineq", "fun": c_global, "args":  (ActionWrapper, action_list )}
    # global_csts.append( global_cst )

    globalBestProfit = 0
    globalBestSolution = []

    result3 = None
    for strength in [0, 1, 2]:
        try:
            # tolerance = 0
            # if config.method == 0:
            #     tolerance = 40
            # with timeout(60 + int(2 * len(bnds)) + tolerance):
            start = time.time()
            
            if strength == 0:
                #   # simplicial, sobol
                result3 = shgo(func=F, bounds=bnds_normalised, constraints=csts, n=128, iters=3, sampling_method='sobol',
                                        minimizer_kwargs={"options": {"ftol": 1}}, \
                                        # minimizer_kwargs = {"method": "COBYLA",  "options": {"tol": 10.0, "maxiter": 1000}}, \
                                        options={"maxfev": 10 * len(bnds), "f_tol": 1000, "maxtime": 6}  \
                                        )
            elif strength == 1:
                #   # simplicial, sobol
                result3 = shgo(func=F, bounds=bnds_normalised, constraints=csts, n=128, iters=1, sampling_method='sobol',
                                        minimizer_kwargs={"options": {"ftol": 1}}, \
                                        # minimizer_kwargs = {"method": "COBYLA",  "options": {"tol": 10.0, "maxiter": 1000}}, \
                                        options={"maxfev": 100 * len(bnds), "f_tol": 1000, "maxtime": 60}  \
                                        )
            elif strength == 2:
                #   # simplicial, sobol
                result3 = shgo(func=F, bounds=bnds_normalised, constraints=csts, n=128, iters=1, sampling_method='sobol',
                                        minimizer_kwargs={"options": {"ftol": 1}}, \
                                        # minimizer_kwargs = {"method": "COBYLA",  "options": {"tol": 10.0, "maxiter": 1000}}, \
                                        options={"maxfev": 500 * len(bnds), "f_tol": 1000, "maxtime": 300}  \
                                        )

            print("The optimizer takes " + str(time.time() - start)+ " seconds")

        except QhullError:
            print("QhullError!")
            return [], [], 0

        try:
            fitted_params = result3.xl
            if config.benchmarkName == 'CheeseBank' or config.benchmarkName == 'AutoShark' \
                or config.benchmarkName == 'InverseFi':
                fitted_params = []
                for x in result3.xl:
                    x = (bnds[:, 0] + x * (bnds[:, 1] - bnds[:, 0])) / Scale
                    fitted_params.append(x)
            

            # convert float to int
            fitted_params = np.asarray(fitted_params, dtype=int)
            # filter out duplicate solutions
            fitted_params, indexes = np.unique(fitted_params, axis=0, return_index=True)

            fitted_params_rts = result3.funl
            fitted_params_rts = fitted_params_rts[indexes]


            if config.benchmarkName == 'CheeseBank' or config.benchmarkName == 'AutoShark' \
                or config.benchmarkName == 'InverseFi':
                result3.x = (bnds[:, 0] + result3.x  * (bnds[:, 1] - bnds[:, 0])) / Scale

            if len(result3.funl) == 1:
                ifAllLessThanOnes = True
                for ii in range(len(result3.x)):
                    if int(result3.x[ii]) > 1:
                        ifAllLessThanOnes = False
                        break
                if ifAllLessThanOnes:
                    print("result.x[i] <= 1 for all i !")
                    continue



            result3x = (bnds[:, 0] + result3.x  * (bnds[:, 1] - bnds[:, 0])) / Scale
            print("best para: " + str(result3x) + " best profit: " + str((-1) * result3.fun))

        except AttributeError:
            print("No result!")
            continue





        ActualProfitsForFittedParams = [0] * len(fitted_params)

        datapoints = testOneContract_Multiple_Points(ActionWrapper, fitted_params, action_list)

        # print("datapoints:  ", datapoints)

        bestPara = []
        bestProfit = float('-inf')
        for datapoint in datapoints:
            
            profit = 0
            if datapoint[1] == None:
                profit = 0
            else:
                profit = ActionWrapper.calcProfit(datapoint[1])
            if profit > bestProfit and profit != 0 and profit != 1:  # 0 and 1 are possiby revert
                bestProfit = profit
                bestPara = datapoint[0]

            for ii in range(len(fitted_params)):
                fitted_param = fitted_params[ii]
                isEqual = True
                for i in range(len(fitted_param)):
                    if int(fitted_param[i]) != datapoint[0][i]:
                        isEqual = False
                        break
                    # else:
                    #     print("same")
                if isEqual:
                    ActualProfitsForFittedParams[ii] = profit
                    break

        if globalBestProfit < bestProfit:
            globalBestProfit = bestProfit
            globalBestSolution = bestPara

        print(result3.message, "    Next only show the first ",min(5, len(fitted_params)), " profitable solutions")
        counter = 0
        for ii in range(len(fitted_params)):
            solu = fitted_params[ii]
            counter += 1
            if counter >= 5:
                break
            print(solu, end=" \t  ")
            estimated_profit = (-1) * f(solu, ActionWrapper, action_list)
            print("estimated profit is, ", estimated_profit, end="   \t   ")
            if ActualProfitsForFittedParams[ii] != 0:
                print("Actual profit is, ",
                      ActualProfitsForFittedParams[ii], end="")
            print("")

        print("Actual best profit is ", bestProfit)
        print("Actual parameter is ", bestPara)

    print("After all rounds, Global best profit is ", globalBestProfit)
    print("Global best parameter is ", globalBestSolution)


def AddDatapoints(cA, datapoints):
    maxStatsLength = 0
    # assume when revert unexpectedly, we get fewer stats than when revert with stats
    for datapoint in datapoints:
        if datapoint[1] != None and len(datapoint[1]) > maxStatsLength:
            maxStatsLength = len(datapoint[1])

    count = 0
    for datapoint in datapoints:
        if datapoint[1] == None or len(datapoint[1]) != maxStatsLength:
            continue
        if cA[-1].add1PointValue(datapoint[0], datapoint[1]) == 1:
            count += 1
    return count


# For a sequence of actions, check if the datapoints matches the simulation result, return the total points added
# if no points are added
# datapoints contains the paras
# datapoints[0] is the paras
# datapoints[1] is the stats
def checkAndAddDatapoints(cA, ActionWrapper, datapoints, show=False):
    maxStatsLength = 0
    # assume when revert unexpectedly, we get fewer stats than when revert with stats
    for datapoint in datapoints:
        if datapoint[1] != None and len(datapoint[1]) > maxStatsLength:
            maxStatsLength = len(datapoint[1])

    count = 0
    for datapoint in datapoints:
        if datapoint[1] == None or len(datapoint[1]) != maxStatsLength:
            continue
        ActionWrapper.resetBalances()
        para_index = 0

        new_cA = cA[:-1]
        for ii in range(len(new_cA)):
            Action = new_cA[ii]
            if Action.numInputs == 0:
                Action.transit(datapoint[0][:para_index], new_cA[0:ii+1])
            elif Action.numInputs == 1:
                Action.transit(datapoint[0][:para_index+1], new_cA[0:ii+1])
                para_index += 1
            elif Action.numInputs == 2:
                Action.transit(datapoint[0][:para_index+2], new_cA[0:ii+1])
                para_index += 2

        # print(datapoint)
        # print(para_index)
        # print(cA)
        # a result smaller than 20 might be the error code
        if datapoint[1] != None and not (len(datapoint[1]) == 1 and datapoint[1][0] == 20):
            simulate_ret = None
            if cA[-1].numInputs == 0:
                simulate_ret = cA[-1].simulate(datapoint[0], cA)
            elif cA[-1].numInputs == 1:
                simulate_ret = cA[-1].simulate(datapoint[0], cA)
            elif cA[-1].numInputs == 2:
                simulate_ret = cA[-1].simulate(datapoint[0], cA)
            else:
                print("error")
                exit(0)
            if simulate_ret == None:
                continue

            execute_ret = None
            execute_ret = cA[-1].aliquotValues(datapoint[1])
            if execute_ret == None:
                continue
            allSame = True
            if type(simulate_ret) is np.float64 or type(simulate_ret) is int or type(simulate_ret) is np.int64:
                simulate_ret = [simulate_ret]
            if type(execute_ret) is np.float64 or type(execute_ret) is int or type(execute_ret) is np.int64:
                execute_ret = [execute_ret]

            for i in range(len(simulate_ret)):
                # 0.001 * max(simulate_ret[i], execute_ret[i]):
                if abs(simulate_ret[i] - execute_ret[i]) > 0:
                    allSame = False
                    break
            if allSame:
                continue
            else:
                if cA[-1].add1PointValue(datapoint[0], datapoint[1], cA) == 1:
                    if show:
                        print("For action ", cA[-1], " add data point: ", datapoint)
                    count += 1
    return count




# For one sequence of actions,and corresponding parameters
def executeAndAddDataPointsWithoutChecking(action_list, ActionWrapper, paras):
    # paras is a list of a list of numbers
    cAs = []
    for ii in range(len(action_list)):
        cAs.append(action_list[0: len(action_list) - ii])

    forge = forgedataCollectContractDVD(ActionWrapper)

    data_map = {}
    # data_map: maps str(a sequence of actions) to the corresponding data points
    dataCollector_map = {}
    # dataCollector_map: maps str(a sequence of actions) to [start of data_collector_index, end of data_collector_index]
    for ii in range(len(cAs)):
        cA = cAs[ii]

        numOfParas = 0
        for action in cA:
            numOfParas += action.numInputs

        sample = ActionWrapper.buildCollectorContract(cA)
        attackContract = sample

        if config.ExecutionMode == 2:
            forge.addAttackContract(attackContract)
        else:
            forge.addAttackContract(attackContract)
        # paras
        para_product = paras

        for jj in range(len(para_product)):
            pp = para_product[jj]
            data_collector_index = forge.addDataCollector(pp[0: numOfParas])
            if jj == 0:
                dataCollector_map[str(cA)] = [
                    data_collector_index, data_collector_index]
            else:
                dataCollector_map[str(cA)][1] = data_collector_index

    forge.updateDataCollectorContract()

    start = time.time()
    datapoints = forge.executeCollectData()
    end = time.time()
    print("Running foundry costs time: ", end - start, " seconds")

    for ii in range(len(cAs)):
        cA = cAs[ii]
        start_index = dataCollector_map[str(cA)][0]
        end_index = dataCollector_map[str(cA)][1]

        data_map[str(cA)] = datapoints[start_index: end_index + 1]
        print(str(cA))
        print("start_index: ", start_index, " end_index: ", end_index)

    totalCount = 0
    for ii in range(len(cAs)):
        cA = cAs[ii]
        datapoints = data_map[str(cA)]
        count = AddDatapoints(cA, datapoints)

        # For the sequence of actions, <1> <2> <3>
        # When we cannot collect any data points for <1> <2> <3>, which indicates the approximation is pretty good.
        # We don't proceed to <1> <2>
        # The above might not be universally true, let's comment it out for now.
        # if count == 0:
        #     break
        totalCount += count

    return totalCount


def executeAndGetStats(action_lists, paras, ActionWrapper):

    forge = None
    if config.ExecutionMode == 2:
        forge = forgedataCollectContractDVD(ActionWrapper)
    else:
        forge = forgedataCollectContract(
            config.contract_name, config.initialEther, config.blockNum)
        forge.initializeAttackContract(ActionWrapper)
        
    data_map = {}
    # data_map: maps str(a sequence of actions) to the corresponding data points
    dataCollector_map = {}
    # dataCollector_map: maps str(a sequence of actions) to [start of data_collector_index, end of data_collector_index]

    for ii in range(len(action_lists)):
        action_list = action_lists[ii]
        para_product = paras[ii]
        if len(para_product) == 0:
            continue

        cAs = []
        for jj in range(len(action_list)):
            cAs.append(action_list[0: len(action_list) - jj])

        for jj in range(len(cAs)):
            cA = cAs[jj]

            op = getattr(cA[-1], "collectorStr", None)
            if op is None:
                continue

            
            numOfParas = 0
            for action in cA:
                numOfParas += action.numInputs
            attackContract = ActionWrapper.buildCollectorContract(cA)
            forge.addAttackContract(attackContract)

            data_map[ToString(cA)] = None

            for kk in range(len(para_product)):
                pp = para_product[kk]
                data_collector_index = forge.addDataCollector(
                    pp[0: numOfParas])
                if kk == 0:
                    dataCollector_map[ToString(cA)] = [
                        data_collector_index, data_collector_index]
                else:
                    dataCollector_map[ToString(cA)][1] = data_collector_index

    forge.updateDataCollectorContract()
    start = time.time()
    datapoints = forge.executeCollectData()
    end = time.time()
    print("Running foundry costs time: ", end - start, " seconds")


    for Str_cA in data_map.keys():
        start_index = dataCollector_map[Str_cA][0]
        end_index = dataCollector_map[Str_cA][1]
        data_map[Str_cA] = datapoints[start_index: end_index + 1]


    # for ii in range(len(action_lists)):
    #     action_list = action_lists[ii]
    #     para_product = paras[ii]
    #     if len(para_product) == 0:
    #         continue
    #     cAs = []
    #     for jj in range(len(action_list)):
    #         cAs.append(action_list[0: len(action_list) - jj])
    #     for ii in range(len(cAs)):
    #         cA = cAs[ii]
    #         start_index = dataCollector_map[ToString(cA)][0]
    #         end_index = dataCollector_map[ToString(cA)][1]
    #         data_map[ToString(cA)] = datapoints[start_index: end_index + 1]


    # print(datapoints)
    # print(data_map)
    return data_map


# For one sequence of actions,and corresponding parameters
# return the number of data points added
def executeAndAddDataPoints(action_list, ActionWrapper, paras, show=False):
    # paras is a list of a list of numbers
    cAs = []
    for ii in range(len(action_list)):
        cAs.append(action_list[0: len(action_list) - ii])

    forge = forgedataCollectContractDVD(ActionWrapper)

    data_map = {}
    # data_map: maps str(a sequence of actions) to the corresponding data points
    dataCollector_map = {}
    # dataCollector_map: maps str(a sequence of actions) to [start of data_collector_index, end of data_collector_index]
    for ii in range(len(cAs)):
        cA = cAs[ii]

        numOfParas = 0
        for action in cA:
            numOfParas += action.numInputs

        op = getattr(cA[-1], "collectorStr", None)
        if op is None:
            continue

        attackContract = ActionWrapper.buildCollectorContract(cA)

        forge.addAttackContract(attackContract)
        # paras
        para_product = paras

        for jj in range(len(para_product)):
            pp = para_product[jj]
            data_collector_index = forge.addDataCollector(pp[0: numOfParas])
            if jj == 0:
                dataCollector_map[str(cA)] = [
                    data_collector_index, data_collector_index]
            else:
                dataCollector_map[str(cA)][1] = data_collector_index

    forge.updateDataCollectorContract()

    start = time.time()
    datapoints = forge.executeCollectData()
    end = time.time()
    print("Running foundry costs time: ", end - start, " seconds")

    for ii in range(len(cAs)):
        cA = cAs[ii]

        op = getattr(cA[-1], "collectorStr", None)
        if op is None:
            continue

        start_index = dataCollector_map[str(cA)][0]
        end_index = dataCollector_map[str(cA)][1]

        data_map[str(cA)] = datapoints[start_index: end_index + 1]
        # print(str(cA))
        # print("start_index: ", start_index, " end_index: ", end_index)

    totalCount = 0
    for ii in range(len(cAs)):
        cA = cAs[ii]

        op = getattr(cA[-1], "collectorStr", None)
        if op is None:
            continue


        datapoints = data_map[str(cA)]
        count = checkAndAddDatapoints(cA, ActionWrapper, datapoints, show)

        # For the sequence of actions, <1> <2> <3>
        # When we cannot collect any data points for <1> <2> <3>, which indicates the approximation is pretty good.
        # We don't proceed to <1> <2>
        # The above might not be universally true, let's comment it out for now.
        # if count == 0:
        #     break
        totalCount += count

    return totalCount


# datapoints[0]: parameters for each action
# datapoints[1]: balances used for calculating profit
def findcounterExampleInputs(action_list, ActionWrapper, datapoints):
    counterExampleInputs = []
    counterExampleActualProfits = []
    # Under 2 circumstances we should execute and add data points
    # For a sequence of paras
    # 1. The estimated Profit is high, but the actual profit is low   # iterate through fitted_params and ActualProfitsForFittedParams
    # 2. The actual Profit is high, but the estimated profit is low   # iterate through datapoints
    # print("DataPoints:  ")
    # print(datapoints)

    # This is where we find and add the counter-example data points
    for datapoint in datapoints:
        if not (datapoint[1] != None and len(datapoint[1]) >= 1):
            estimated_profit = (-1) * \
                f(datapoint[0], ActionWrapper, action_list)
            actual_profit = None
            counterExampleInputs.append(datapoint[0])
            counterExampleActualProfits.append(actual_profit)
            continue

        estimated_profit = (-1) * f(datapoint[0], ActionWrapper, action_list)
        actual_profit = ActionWrapper.calcProfit(datapoint[1])

        # the error rate is smaller than 10%(previous 5%)
        if abs(actual_profit - estimated_profit) > max(0.05 * (abs(actual_profit) + abs(estimated_profit)), 10):
            counterExampleInputs.append(datapoint[0])
            counterExampleActualProfits.append(actual_profit)

    return counterExampleInputs, counterExampleActualProfits


class timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)



# action_lists: a list of lists of actions
# para_lists: a list of lists of lists of parameters
# prestate: len(action_lists) = len(para_lists)
# example:
# input:   action_lists = [[a1, a2], [a3, a4]]
#          para_lists = [
#                           [[p1, p2], [p3, p4]],
#                           [[q1, q2], [q3, q4]]
#
#                        ]
# return:  profits = [ [p0, p1, p2, p3],
#                      [p4, p5, p6]
#                    ]
#
def testRealProfit_Batch(action_lists, para_lists, ActionWrapper):

    stop_indexes = []

    forgeBatch = None

    if config.ExecutionMode == 2:
        forgeBatch = forgedataCollectContractDVD(ActionWrapper)
    else:
        forgeBatch = forgedataCollectContract(
            config.contract_name, config.initialEther, config.blockNum)
        forgeBatch.initializeAttackContract(ActionWrapper)


    total = 0
    for ii in range(len(action_lists)):
        action_list = action_lists[ii]
        attackContract = ActionWrapper.buildAttackContract(action_list)
        if len(para_lists[ii]) > 0:
            forgeBatch.addAttackContract(attackContract)
        stop_indexes.append(-1)
        for jj in range(len(para_lists[ii])):
            total += 1
            para_list = para_lists[ii][jj]
            index = forgeBatch.addDataCollector(para_list)
            stop_indexes[-1] = index
    forgeBatch.updateDataCollectorContract()

    start = time.time()
    datapoints = forgeBatch.executeCollectData()
    end = time.time()
    print("Running attacks on foundry costs time: ", end - start, " seconds")

    index_pointer = 0
    profits = [[]]
    ii = 0
    while ii < len(datapoints):
        if ii <= stop_indexes[index_pointer]:
            profit = ActionWrapper.calcProfit(datapoints[ii][1])
            profits[-1].append(profit)
            ii = ii + 1
        else:
            profits.append([])
            index_pointer += 1
    return profits


# test for exact equality
def arreq_in_list(myarr, list_arrays):
    return next((True for elem in list_arrays if array_equal(elem, myarr)), False)


def tweakParas(xls, funls):
    new_xls = []
    # for ii in range(len(xls)):
    #     new_xls.append(xls[ii])
    for ii in range(len(xls)):
        if funls[ii] >= 1:
            paras = xls[ii].copy()
            for j in range(len(paras)):
                if paras[j] == 1:
                    continue
                paras[j] = int(paras[j] * 998 / 1000)
                if paras[j] >= 1 and not arreq_in_list(paras, new_xls) and not arreq_in_list(paras, xls):
                    new_xls.append(paras)
    return new_xls


def runningOptimizer(F, bnds_normalised, csts, bnds, strength):
    if strength == 0:
        #   # simplicial, sobol
        result3 = shgo(func=F, bounds=bnds_normalised, constraints=csts, n=128, iters=3, sampling_method='sobol',
                                minimizer_kwargs={"options": {"ftol": 1}}, \
                                # minimizer_kwargs = {"method": "COBYLA",  "options": {"tol": 10.0, "maxiter": 1000}}, \
                                options={"maxfev": 10 * len(bnds), "f_tol": 100, "maxtime": 6}  \
                                )
    elif strength == 1:
        #   # simplicial, sobol
        result3 = shgo(func=F, bounds=bnds_normalised, constraints=csts, n=128, iters=1, sampling_method='sobol',
                                minimizer_kwargs={"options": {"ftol": 1}}, \
                                # minimizer_kwargs = {"method": "COBYLA",  "options": {"tol": 10.0, "maxiter": 1000}}, \
                                options={"maxfev": 100 * len(bnds), "f_tol": 100, "maxtime": 60}  \
                                )
    elif strength == 2:
        #   # simplicial, sobol
        result3 = shgo(func=F, bounds=bnds_normalised, constraints=csts, n=128, iters=1, sampling_method='sobol',
                                minimizer_kwargs={"options": {"ftol": 1}}, \
                                # minimizer_kwargs = {"method": "COBYLA",  "options": {"tol": 10.0, "maxiter": 1000}}, \
                                options={"maxfev": 500 * len(bnds), "f_tol": 100, "maxtime": 300}  \
                                )
    return result3


# This function is used to search for the best profit based on data points collected from initial pass.
# Plus the counter-example data argumentation.
# strength represents the power of search
def optimizeMiniMumOnce(action_list, ActionWrapper, strength=0, start=0, currProfit=-1):
    sys.stdout.flush()

    
    
    start_str = ("Check Contract: \t" + ToString(action_list))
    if currProfit != -1:
        start_str += ("    Profit of Previous Interation: \t" + str(currProfit))
    start_str += ("  time: " + str(time.time() - start) + "\n")
    print_str = ""


    # Step 1: run optimizer
    bnds = getBnds(action_list)
    bnds = np.array(bnds)
    
    bnds_normalised = bnds

    csts = None
    F = None
    if config.benchmarkName == 'CheeseBank' or config.benchmarkName == 'AutoShark' \
        or config.benchmarkName == 'InverseFi':
        Scale = 1
        bnds_normalised = [(0, Scale),]*len(bnds)  # Normalise boundaries back to a simplex
        csts = getCsts(action_list, ActionWrapper, bnds, Scale)
        F = getF(ActionWrapper, action_list, bnds, Scale)
    else:
        csts = getCsts(action_list, ActionWrapper)
        F = getF(ActionWrapper, action_list)

    result3 = None
    gc.collect()

    try:
        # tolerance = 0
        # with timeout(60 + int(2 * len(bnds)) + tolerance):
        start = time.time()
        gc.collect()
        if strength == 0:
        #   # simplicial, sobol
            result3 = shgo(func=F, bounds=bnds_normalised, constraints=csts, n=128, iters=3, sampling_method='sobol',
                                minimizer_kwargs={"options": {"ftol": 1}}, \
                                # minimizer_kwargs = {"method": "COBYLA",  "options": {"tol": 10.0, "maxiter": 1000}}, \
                                options={"maxfev": 10 * len(bnds), "f_tol": 100, "maxtime": 6}  \
                                )
        elif strength == 1:
            #   # simplicial, sobol
            result3 = shgo(func=F, bounds=bnds_normalised, constraints=csts, n=128, iters=1, sampling_method='sobol',
                                    minimizer_kwargs={"options": {"ftol": 1}}, \
                                    # minimizer_kwargs = {"method": "COBYLA",  "options": {"tol": 10.0, "maxiter": 1000}}, \
                                    options={"maxfev": 100 * len(bnds), "f_tol": 100, "maxtime": 60}  \
                                    )
        elif strength == 2:
            #   # simplicial, sobol
            result3 = shgo(func=F, bounds=bnds_normalised, constraints=csts, n=128, iters=1, sampling_method='sobol',
                                    minimizer_kwargs={"options": {"ftol": 1}}, \
                                    # minimizer_kwargs = {"method": "COBYLA",  "options": {"tol": 10.0, "maxiter": 1000}}, \
                                    options={"maxfev": 500 * len(bnds), "f_tol": 100, "maxtime": 300}  \
                                    )

        print_str += ("The optimizer takes " + str(time.time() - start)+ " seconds\n")
        # except TimeoutError:
        #     print(start_str + "Timeout!")
        #     return [], [], 0

    except QhullError:
        print(start_str + "QhullError!")
        return [], [], 0





    try:
        fitted_params = result3.xl
        if config.benchmarkName == 'CheeseBank' or config.benchmarkName == 'AutoShark' \
            or config.benchmarkName == 'InverseFi':
            fitted_params = []
            for x in result3.xl:
                x = (bnds[:, 0] + x * (bnds[:, 1] - bnds[:, 0])) / Scale
                fitted_params.append(x)

        # convert float to int
        fitted_params = np.asarray(fitted_params, dtype=int)
        # filter out duplicate solutions
        fitted_params, indexes = np.unique(fitted_params, axis=0, return_index=True)

        fitted_params_rts = result3.funl
        fitted_params_rts = fitted_params_rts[indexes]

        if config.benchmarkName == 'CheeseBank' or config.benchmarkName == 'AutoShark' \
            or config.benchmarkName == 'InverseFi':
            result3.x = (bnds[:, 0] + result3.x  * (bnds[:, 1] - bnds[:, 0])) / Scale

        if len(result3.funl) == 1:
            ifAllLessThanOnes = True
            for ii in range(len(result3.x)):
                if int(result3.x[ii]) > 1:
                    ifAllLessThanOnes = False
                    break
            if ifAllLessThanOnes:
                print(start_str + "result.x[i] <= 1 for all i !")
                return [], [], 0


        print_str += ("best para: " + str(result3.x) + " best profit: " + str((-1) * result3.fun) + "\n")
        
        # print_str += ("double check best profit: " + str( (-1) * F(result3.x) ) + "\n")

    except AttributeError:
        print(start_str + "No result!")
        return [], [], 0

    # Now we have
    # fitted_params: list of sequences of parameters
    # fitted_params_rts: list of profits of fitted_params

    # Step 3: print Paras and estimated profits
    numofxl = len(fitted_params)
    print_str += (str(result3.message) + "    Next only show the first " + str( min( \
        5, numofxl)) + "/" + str(numofxl) + " profitable solutions\n")
    fitted_params_rts = [(-1) * item for item in fitted_params_rts]

    # print(fitted_params)
    # print(new_fitted_params)
    fitted_params = fitted_params.tolist()

    # Tweak the parameters ==== start ====.
    new_fitted_params = tweakParas(fitted_params, fitted_params_rts)
    fitted_params += new_fitted_params
    # Tweak the parameters ==== end ====.

    counter = 0
    for kk in range(len(fitted_params)):
        solu = fitted_params[kk]
        counter += 1

        if counter <= 5:
            print_str += (str(solu) + " \t  ")
        # estimated_profit = (-1) * f(solu, ActionWrapper, action_list)
        if kk < numofxl:
            if counter <= 5:
                print_str += ("estimated profit is, " + \
                      str(fitted_params_rts[kk]) + "   \t   \n")
        else:
            estimated_profit = (-1) * \
                f(fitted_params[kk], ActionWrapper, action_list)
            fitted_params_rts.append(estimated_profit)
            if counter <= 5:
                print_str += ("estimated profit is, " + \
                      str(estimated_profit) + "   \t   \n")

    NumPositives = sum(x > 1 for x in fitted_params_rts)
# (-1) * f(initial_guess, ActionWrapper, action_list)
    if len(fitted_params) != len(fitted_params_rts):
        print(start_str + "Error: fitted_params and fitted_params_rts are not the same length!")
        sys.exit(1)

    print(start_str + print_str)

    return fitted_params, fitted_params_rts, NumPositives

