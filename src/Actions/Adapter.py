## This is a file designed to simplify data points
## If we know the dependency of Actions. 
import sys
import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
sys.path.append(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
import copy

class Adapter(): 

    def __init__(self, dependencyMap = None):
        self.dependencyMap = copy.deepcopy(dependencyMap)
        # action.__name__ -> num 

    def simplify(self, actionList):
        ## Filter out unnecessary actions
        ## And return the simplified data point

        lastAction = actionList[-1]

        newActionList = [actionList[-1]]
        relatedActions = self.dependencyMap[lastAction]
        for ii in range(len(actionList) - 2, -1, -1):
            if actionList[ii].__name__ in relatedActions:
                newActionList.insert(0, actionList[ii])
                relatedActions += self.dependencyMap[actionList[ii]]
        return newActionList
    

    def simplify(self, point, actionList):
        lastAction = actionList[-1]
        new_point = []

        newActionList = [actionList[-1]]
        relatedActions = self.dependencyMap[lastAction]
        for ii in range(len(actionList) - 2, -1, -1):
            if actionList[ii].__name__ in relatedActions:
                newActionList.insert(0, actionList[ii])
                relatedActions += self.dependencyMap[actionList[ii]]
        
        return newActionList
    
    def extend(self, point, actionList):
        # add a 1 for actions that don't have input 
        hasZero = False
        for action in actionList:
            if action.numInputs == 0:
                hasZero = True
                break
        if not hasZero:
            return point

        new_point = []
        counter = 0
        for action in actionList:
            if action.numInputs == 0:
                new_point.append(1)
            elif action.numInputs == 1:
                new_point.append(point[counter])
                counter += 1
            elif action.numInputs == 2:
                new_point.append(point[counter])
                new_point.append(point[counter + 1])
                counter += 2
            elif action.numInputs == 3:
                new_point.append(point[counter])
                new_point.append(point[counter + 1])
                new_point.append(point[counter + 2])
                counter += 3
        return new_point
            
        
