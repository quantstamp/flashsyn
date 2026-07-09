import os
import sys
import config
import Actions.macros as macros
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
from Actions.SingleApprox.SingleApprox import single_round_approx, predict
from Actions.Utils import *
from Actions.AttackDAG import *
import gc
import copy

class NumericalApproximator():
    def __init__(self, points, values, indexes=None):
        self.interpolator = None
        self.polynomial = None
        self.polynomial_name = None
        self.score = None
        self.is1D = False
        self.method = config.method # matches config.method
        self.method2 = -1 

        newpoints = None
        if indexes is None:
            newpoints = copy.deepcopy( points )
        else:
            newpoints = getPointsFromIndexes(points, indexes)
        
        if self.method == 0:
            isND = any(isinstance(el, list) for el in newpoints)
            if not isND: # means it is 1D
                self.is1D = True
                self.interpolator = interp1d(newpoints, values, kind='linear', fill_value='extrapolate')
            else:
                self.interpolator = BarebonesNearestNDInterpolator(newpoints, values, rescale=False)

        elif self.method == 1:
            self.polynomial, self.polynomial_name, self.score = single_round_approx(newpoints, values, rate=0.1)
            # print("polynomial coef_: ", self.polynomial.coef_)
            # print("polynomial intercept_: ", self.polynomial.intercept_)
            # print("polynomial_name: ", self.polynomial_name)

        elif self.method == 2:
            self.polynomial, self.polynomial_name, self.score = single_round_approx(newpoints, values, rate=0.1)
            
            if self.score == 0:
                self.method2 = 1
            else:
                self.method2 = 0
                isND = any(isinstance(el, list) for el in newpoints)
                if not isND: # means it is 1D
                    self.is1D = True
                    self.interpolator = interp1d(newpoints, values, kind='linear', fill_value='extrapolate')
                else:
                    self.interpolator = BarebonesNearestNDInterpolator(newpoints, values, rescale=False)
            


    def __call__(self, inputs):
        if self.method == 0 or self.method2 == 0:
            if self.is1D:
                # return predict(self.polynomial, self.polynomial_name, [inputs])        

                return self.interpolator(inputs)[0]
            else:
                return self.interpolator([inputs])[0]
                    

        elif self.method == 1 or self.method2 == 1:
            return predict(self.polynomial, self.polynomial_name, [inputs])        



# Still one action has one approximator
class NumericalApproximatorsPro():
    def __init__(self, map = {}):
        self.dataMap = {}
        self.dataMapHasNewDataPoints = {}
        # status code: 
        # has new data points: 1
        # doesn't have new data points: 0
        self.ApproximationMap = {}
        
        self.InferredApproximationMap = {}
        self.inferredCache = {}

        self.cachedActionList = None
        self.cachedIndex = None
        self.cachedDAG = None
        
        for key in map:
            actionList = map[key][0]
            points, values = map[key][1]
            dag, index = AttackDAGGenerator.generateDAG(actionList)
            if index == len(AttackDAGGenerator.generated) - 1:
                # it means it's a new DAG
                self.dataMap[index] = (points, values)
            else:
                # if index == 16:
                #     print("now is the time")
                # it means it's equivalent to an old DAG
                dag.setSimplifierExpander( AttackDAGGenerator.generated[index] )
                new_points = []
                for point in points:
                    new_point = dag.extendInputs(point)
                    new_points += new_point
                self.dataMap[index] = (new_points, values)
                
            self.ApproximationMap[index] = []
            for ii in range(len(values)):
                value = copy.deepcopy(values[ii]) 
                polynomial, polynomial_name, score = single_round_approx(self.dataMap[index][0], value, rate=0.1)
                self.ApproximationMap[index].append( (polynomial, polynomial_name, score)  )
                self.dataMapHasNewDataPoints[index] = 0


    def points(self, actionList):
        dag, index = AttackDAGGenerator.generateDAG(actionList)
        return self.dataMap[index][0]
    
    def values(self, actionList):
        dag, index = AttackDAGGenerator.generateDAG(actionList)
        return self.dataMap[index][1]

    def numOfDataPoints(self):
        sum = 0
        for key in self.dataMap:
            sum += len(self.dataMap[key][0])
        return sum

    def addDataPoint(self, point, values, actionList):
        # new_point = Adapter().extend(point, actionList)
        dag = None
        index = None
        if actionList == self.cachedActionList:
            dag = self.cachedDAG
            index = self.cachedIndex
        else:
            dag, index = AttackDAGGenerator.generateDAG(actionList)
            self.cachedActionList = actionList
            self.cachedDAG = dag
            self.cachedIndex = index
            dag.setSimplifierExpander( AttackDAGGenerator.generated[index] )

        if index in self.dataMap:
            # it means that has old data points                
            new_points = dag.extendInputs(point)

            if len(new_points) > 1:
                sys.exit("Error: new_points > 1")
            else:
                new_point = new_points[0]
                if new_point in self.dataMap[index][0]:
                    return macros.ILLEGALPOINT
                self.dataMap[index][0].append( new_point )
                for ii in range(len(values)):
                    self.dataMap[index][1][ii].append(values[ii])
        else:
            # it means that doesn't have old data points
            new_point = dag.convertSelfInputs(point)
            new_values = []
            for ii in range(len(values)):
                new_values.append([values[ii]])
            self.dataMap[index] = ([new_point], new_values)
        self.dataMapHasNewDataPoints[index] = 1
        return macros.LEGALPOINT

    def refreshTransitFormulaOneDAG(self, index, newpoints, newvalues):
        if index not in self.ApproximationMap:
            sys.exit("Error: name not in ApproximationMap")
        self.ApproximationMap[index] = []
        for ii in range(len(newvalues)):
            value = newvalues[ii]
            polynomial, polynomial_name, score = single_round_approx(newpoints, value, rate=0.1)
            self.ApproximationMap[index].append( (polynomial, polynomial_name, score)  )
        return 

    def callOneActionList(self, index, new_inputs):
        rets = []
        for ii in range(len(self.ApproximationMap[index])):
            polynomial, polynomial_name, score = self.ApproximationMap[index][ii]
            rets.append( predict(polynomial, polynomial_name, [new_inputs]) )
        return rets

    def refreshTransitFormula(self):
        for index in self.ApproximationMap:
            # all approximators need to consider data points of sub-DAGs
            anything_changed = False
            if index in self.dataMapHasNewDataPoints and self.dataMapHasNewDataPoints[index] == 1:
                anything_changed = True
            else:
                if index not in self.inferredCache:
                    self.inferredCache[index] = []
                    for key in AttackDAGGenerator.subTree[index]:
                        if key in self.dataMap:
                            self.inferredCache[index].append(key)
                for related_indexes in self.inferredCache[index]:
                    if self.dataMapHasNewDataPoints[related_indexes] == 1:
                        anything_changed = True
            if not anything_changed:
                continue

            newpoints = []
            newvalues = None

            if index in self.dataMap:
                points, values = self.dataMap[index]
                newpoints = copy.deepcopy(points)
                newvalues = copy.deepcopy(values)
            
            else:
                related_index0 = self.inferredCache[index][0]
                points, values = self.dataMap[related_index0]
                newvalues = []
                for ii in range(len(values)):
                    newvalues.append( [] )

            # means the approx will be inferred
            for related_indexes in self.inferredCache[index]:
                if related_indexes in self.dataMap:
                    points, values = self.dataMap[related_indexes]
                    dag = AttackDAGGenerator.generated[related_indexes]
                    dag.setSimplifierExpander( AttackDAGGenerator.generated[index] )
                    for ii in range(len(points)):
                        point = points[ii]
                        new_points = dag.extendInputs(point)
                        if len(new_points) == 0:
                            sys.exit("Error: isSubDAG, but cannot extend Inputs")
                        for new_point in new_points:
                            if new_point not in newpoints:
                                newpoints.append(new_point)
                                for jj in range(len(values)):
                                    newvalues[jj].append( values[jj][ii] )

            self.refreshTransitFormulaOneDAG(index, newpoints, newvalues)

        gc.collect()


    def __call__(self, inputs, actionList):
        
        # if len(actionList) == 3 and actionList[0].__name__ == "SwapUniswapWETH2DAI" and \
        #     actionList[1].__name__ == "MintLPUniswapV2" and actionList[2].__name__ == "SwapUniswapWETH2DAI":
        #     print("now is the time")

        dag, index = AttackDAGGenerator.generateDAG(actionList)

        new_inputs = None
        if index == len(AttackDAGGenerator.generated)-1:
            new_inputs = [inputs]
        else:
            their_dag = AttackDAGGenerator.generated[index]
            their_dag.setSimplifierExpander( dag )
            new_inputs = their_dag.extendInputs(inputs) 

        if index in self.ApproximationMap:
            # new_inputs = inputs
            if len(new_inputs) > 1:
                print(new_inputs)
                sys.exit("Error: new_inputs > 1")

            rets = []
            for ii in range(len(self.ApproximationMap[index])):
                polynomial, polynomial_name, score = self.ApproximationMap[index][ii]
                rets.append( predict(polynomial, polynomial_name, new_inputs ) )
            return rets

        else:
            # we need to infer the approx
            self.inferredCache[index] = []
            self.ApproximationMap[index] = []

            newpoints = []
            newvalues = []

            if len(AttackDAGGenerator.subTree[index]) == 0:
                sys.exit("Error: len(AttackDAGGenerator.subTree[index]) == 0")

            for key in AttackDAGGenerator.subTree[index]:
                # print(key)
                if key in self.dataMap:
                    self.inferredCache[index].append(key)

                    their_dag = AttackDAGGenerator.generated[key]
                    points, values = self.dataMap[key]
                    their_dag.setSimplifierExpander( dag )

                    for ii in range(len(points)):
                        point = points[ii]
                        new_point = their_dag.extendInputs(point) # new points could have multiple
            
                        newpoints += new_point
                        for jj in range( len(values) ):
                            if len(newvalues) == jj:
                                newvalues.append( [] )
                        
                        for jj in range( len(values) ):
                            for _ in range(len(new_point)):
                                newvalues[jj].append( values[jj][ii] )




            rets = []
            if newpoints is None:
                print("Error: no data points to infer")
                sys.exit(1)
            for ii in range(len(newvalues)):
                value = copy.deepcopy( newvalues[ii] )
                polynomial, polynomial_name, score = single_round_approx(newpoints, value, rate=0.1)
                self.ApproximationMap[index].append( (polynomial, polynomial_name, score)  )
                rets.append( predict(polynomial, polynomial_name, new_inputs) )
            return rets

            





        




def getActualProfit(initial_guess, ActionWrapper, action_list):
    datapoints = singleCollect(action_list, ActionWrapper, [initial_guess])
    profit = ActionWrapper.calcProfit(datapoints[0][1])
    return profit


def getEstimatedProfit(initial_guess, ActionWrapper, action_list):
    for action in action_list:
        action.hasNewDataPoints = True
    return (-1) * f(initial_guess, ActionWrapper, action_list)

def getEstimatedProfit_precise_display(initial_guess, ActionWrapper, action_list, isdisplay = False):
    return (-1) * f_display(initial_guess, ActionWrapper, action_list, isdisplay)


def printIntePolyEstimatedProfit(initial_guess, ActionWrapper, action_list):
    config.method = 0
    for action in action_list:
        if hasattr(action, 'refreshTransitFormula'):
            action.refreshTransitFormula()
    estimate1 =  (-1) * f_display(initial_guess, ActionWrapper, action_list, True)
    print("estimated profit for interpolation: ", estimate1)
    
    config.method = 1
    for action in action_list:
        if hasattr(action, 'refreshTransitFormula'):
            action.refreshTransitFormula()
    estimate2 =  (-1) * f_display(initial_guess, ActionWrapper, action_list, True)
    print("estimated profit for polynomial: ", estimate2)
    return estimate1, estimate2

    
def testCounterExampleDrivenApprox(initial_guess, ActionWrapper, action_list):
    estimate1, estimate2 =  printIntePolyEstimatedProfit(initial_guess, ActionWrapper, action_list)
    print("add datapoints based on groundtruth concrete attack vector")
    executeAndAddDataPoints(action_list, ActionWrapper, [initial_guess], True)
    estimate3, estimate4 = printIntePolyEstimatedProfit(initial_guess, ActionWrapper, action_list)
    return estimate1, estimate2, estimate3, estimate4


def testSpeed(initial_guess, ActionWrapper, action_list):
    start = time.time()
    for _ in range(10000):
        ret = f(initial_guess, ActionWrapper, action_list)
    end = time.time() - start
    print("estimated profit: ", (-1) * ret)
    print("run 10000 loops takes ", end, " (s)")


def testOptimize(action_list, ActionWrapper):
    Optimize(action_list, ActionWrapper)
