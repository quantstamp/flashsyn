
import random
import config
import os, sys, copy
import itertools, pickle
from itertools import permutations
from collections import deque

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
from forge.forgeCollectDVD import *
from Actions.Action import *
from Actions.prune import *
# from FlashSynPro2Actions.WarpNewPro import *



class AttackDAG():
    def __init__(self):
        self.roots = []
        self.DAGNodeArray = []
        self.selfConverterInputIndexes = None
        self.targetAttackDAG = None
        self.numOfInputs = 0
    # convert a parameter list into 

    def printDAG(self):
        print("roots: ")
        for root in self.roots:
            print(root)

        print("DAG: ")
        for ii in range(len(self.DAGNodeArray)):
            print("Action Index: " + str(ii) + "  " + str(self.DAGNodeArray[ii]) + ", ")

    def paramIndexForAction(self, actionIndex):
        return self.DAGNodeArray[actionIndex].paraList

    def composeIndexMappings(self, indexMappings):
        # indexMappings is a list of indexMapping
        composed = [None] * len(indexMappings[0])
        for indexMapping in indexMappings:
            for ii in range(len(composed)):
                if composed[ii] == None:
                    composed[ii] = indexMapping[ii]
                else:
                    if composed[ii] != indexMapping[ii]:
                        return None
        # if composed is still a list of None, then return None
        if all([x == None for x in composed]):
            return None
        return composed
    
    def paths2ComposedIndexMappings(self, path, parents_indexMappings):
        indexMappings = []
        for ii in range(len(path)):
            indexMappings.append(parents_indexMappings[ii][path[ii]])
        return self.composeIndexMappings(indexMappings)
            
    def composeParentsIndexMappings(self, parents_indexMappings):
        ## TODO: could be optimized
        numOfParents = len(parents_indexMappings)
        numOfRows = numOfParents
        finalAnswers = []
        row = 0
        column = 0
        paths = [0]
        while True:
            # print("path at row {} column {} ".format(row, column))
            if column != paths[-1]:
                sys.exit("column != paths[-1]")

            # reach the end of the row
            if column > len(parents_indexMappings[row]) - 1:
                paths.pop()
                row = row - 1
                if len(paths) == 0:
                    # reach the end
                    break
                column = paths[-1] + 1
                paths[-1] = column
                continue
            
            # reach the end of the column
            if row == numOfRows - 1:
                if row == 0:
                    finalAnswers.append(paths.copy())
                    break
                finalAnswers.append(paths.copy())
                paths.pop()
                column = column + 1
                paths.append(column)
                continue

            row = row + 1
            column = 0 
            paths.append(column)

        returns = []
        for path in finalAnswers:
            kk = self.paths2ComposedIndexMappings(path, parents_indexMappings)
            if kk != None:
                returns.append(kk)
        return returns

            

    def isSubDAGOfHelper(self, thisNode, otherDAGNode, indexMapping):
        thisParents = thisNode.parents
        otherParents = otherDAGNode.parents
        if len(thisParents) > len(otherParents) or thisNode.DAGSize() > otherDAGNode.DAGSize():
            return []
        
        thisParentsActions = [x.action.__name__ for x in thisParents]
        otherParentsActions = [x.action.__name__ for x in otherParents]
        
        matches = find_matching_permutations(thisParentsActions, otherParentsActions)
        if len(matches) == 0:
            return []

        new_indexMappings = [] 
        # matches eg. [[0, 1, 6], [3, 1, 6]]
        for match in matches:
            new_indexMapping = indexMapping.copy()
            for ii in range(len(thisParents)):
                if new_indexMapping[thisParents[ii].index] != None:
                    continue # illegal matching, conflict with previous assignments
                else:
                    new_indexMapping[thisParents[ii].index] = otherParents[match[ii]].index
            new_indexMappings.append(new_indexMapping)

        # contains_none = any(None in sublist for sublist in new_indexMappings)
        # if not contains_none:
        #     return new_indexMappings
        # otherwise contains None, we need to further expand

        
        # new_indexMappings: all possible indexMappings for thisNode's parents
        # eg. [[None, 3]]
        
        possibleMappings = []
        for new_indexMapping in new_indexMappings:
            parents_indexMappings = []

            if len(thisParents) == 0:
                possibleMappings.append(new_indexMapping)
                continue

            for parent in thisParents:
                parentIndex = parent.index
                otherParentIndex = new_indexMapping[parentIndex]
                parent_indexMappings = self.isSubDAGOfHelper( parent, self.otherAttackDAG.DAGNodeArray[otherParentIndex], new_indexMapping)
                # parent_indexMappings should always be a list of lists
                if parent_indexMappings != [[]]  and len(parent_indexMappings) != 0:
                    parents_indexMappings.append( parent_indexMappings )
                else:
                    # no possible parent matching
                    parents_indexMappings = []
                    break

            # remove duplicate lists inside parents_indexMappings
            # unique_lists = set(tuple(x) for x in parents_indexMappings)
            # result = [list(x) for x in unique_lists]

            # if len(thisParents) == 0:
            # have a cross product 
            if len(parents_indexMappings) == 0:
                merged = []
            elif len(parents_indexMappings) > 1:
                merged = self.composeParentsIndexMappings(parents_indexMappings)
                possibleMappings += merged
            else:
                merged = parents_indexMappings[0]
                possibleMappings += merged
        
        # print("possibleMappings: " + str(possibleMappings))
        # possible mappings should always be a list of lists
        return possibleMappings
    

    def isEquivalent(self, otherAttackDAG):
        # if len(self.DAGNodeArray) != len(otherAttackDAG.DAGNodeArray):
        #     return False
        if len(self.isSubDAGOf(otherAttackDAG)) and otherAttackDAG.isSubDAGOf(self):
            return True
        else:
            return False


    def isSubDAGOf(self, otherAttackDAG): # usually otherAttackDAG is a larger DAG
        indexMapping = [None] * len(self.DAGNodeArray)
        thisLastNode = self.DAGNodeArray[-1]
        otherLastNode = otherAttackDAG.DAGNodeArray[-1]
        self.otherAttackDAG = otherAttackDAG

        if thisLastNode.action.__name__ != otherLastNode.action.__name__:
            sys.exit("thisLastNode.action.__name__ != otherLastNode.action.__name__")
        else:
            indexMapping[-1] = otherLastNode.index
        
        possibleMappings = self.isSubDAGOfHelper(thisLastNode, otherLastNode, indexMapping)
        
        return possibleMappings

    
    def setSelfConverter(self):
        inputIndexes = []
        for node in self.DAGNodeArray:
            if node is not None:
                inputIndexes += node.paraList
        self.selfConverterInputIndexes = inputIndexes

    def convertSelfInputs(self, inputs):
        if self.selfConverterInputIndexes == None:
            self.setSelfConverter()
        new_inputs = []
        for index in self.selfConverterInputIndexes:
            new_inputs.append(inputs[index])
        return new_inputs
        

    def setSimplifierExpander(self, targetAttackDAG):
        # when doing initial data pass,
        #      convert equivalent dags to equivalent dags
        # when doing inference,
        #      convert smaller dag to larger dag
        #
        # The mapping depends only on (self, targetAttackDAG) — both immutable once built
        # by generateDAG — yet simulate() calls this ~15M times per synthesis with the
        # SAME pair (only the numeric inputs vary), each time re-running the expensive
        # isSubDAGOf graph match. That recompute was ~75% of synthesize's runtime, so
        # skip it when the target is unchanged (identity check: generateDAG returns the
        # same cached DAG object each call, so the hot path hits this).
        if getattr(self, "targetAttackDAG", None) is targetAttackDAG:
            return
        possibleMappings = self.isSubDAGOf(targetAttackDAG)
        ConverterInputIndexesVector = []
        for possibleMapping in possibleMappings:
            inputIndexes = []
            for ii in range(len(self.DAGNodeArray)):
                node = self.DAGNodeArray[ii]
                if node is not None:
                    inputIndexes += targetAttackDAG.DAGNodeArray[ possibleMapping[ii] ].paraList
            ConverterInputIndexesVector.append(inputIndexes)
        self.ConverterInputIndexesVector = ConverterInputIndexesVector
        self.targetAttackDAG = targetAttackDAG
        
    def simplifyInputs(self, inputs):
        # inputs: targetAttackDAG inputs
        # Return: self inputs
        new_inputsVector = []
        for inputIndexes in self.ConverterInputIndexesVector:
            new_inputs = []
            for index in inputIndexes:
                new_inputs.append(inputs[index])
            new_inputsVector.append(new_inputs)
        return new_inputsVector

    def extendInputs(self, inputs):
        # inputs: self inputs
        # return: targetAttackDAG inputs
        new_inputsVector = []
        # inputs = self.convertSelfInputs(copy.deepcopy(inputs))
        for inputIndexes in self.ConverterInputIndexesVector:

            new_inputs = [0] * self.targetAttackDAG.numOfInputs
            for ii in range(len(inputIndexes)):
                new_inputs[inputIndexes[ii]] = inputs[ii]
            
            new_inputs = self.targetAttackDAG.convertSelfInputs(new_inputs)
            new_inputsVector.append(new_inputs)

        unique_lists = set(tuple(x) for x in new_inputsVector)
        new_inputsVector = [list(x) for x in unique_lists]
        
        return new_inputsVector
                



        
        



        
            
        


class AttackDAGNode():
    def __init__(self, action, index, paraList) -> None:
        self.action = action # val is a tuple (action, actionIndex, parameterIndex)
        self.index = index
        self.paraList = paraList
        self.children = []
        self.parents = []
    
    def addChild(self, child):
        self.children.append(child)

    def addParent(self, parent):
        self.parents.append(parent)

    def DAGSize(self):
        if len(self.parents) == 0:
            return 1
        else:
            return sum([parent.DAGSize() for parent in self.parents]) + 1

    def __str__(self):
        name = self.action.__name__
        index = self.index
        paraList = self.paraList
        # children = [child.__str__() for child in self.children]
        parents = [parent.index for parent in self.parents]
        return str(index) + "-" + name + "-parents:" + str(parents)




class AttackDAGGenerator():
    @classmethod
    def setActionDependency(cls, actionDependency):
        cls.actionDependency = actionDependency
        cls.generated = []
        cls.subTree = []
        cls.superTree = []
        cls.name2index = {}

    @classmethod
    def generateDAG(cls, actionVector):
        # build string
        name = ""
        for action in actionVector:
            name += action.__name__ + "_"
        name = name[:-1]

        if name in cls.name2index:
            index = cls.name2index[name]
            return cls.generated[index], index

        DAGNodeArray = []
        paraIndex = 0
        dag = AttackDAG()
        for ii in range(len(actionVector)):
            action = actionVector[ii]
            numInputs = action.numInputs
            DAGNode = None
            if numInputs == 0:
                # no input, add the action node
                DAGNode = AttackDAGNode(action, ii, [])
            else:
                paraList = []
                for jj in range(numInputs):
                    paraList.append( paraIndex + jj )
                paraIndex += numInputs
                DAGNode = AttackDAGNode(action, ii, paraList)
            DAGNodeArray.append(DAGNode)
            # add the dependency
            dependencyList = cls.actionDependency[action.__name__]
            
            counter = 0
            for dependency in dependencyList:
                depnedencyIndexes = [i for i, x in enumerate(actionVector[0:ii]) if x == dependency]
                for dependencyIndex in depnedencyIndexes:
                    DAGNodeArray[dependencyIndex].addChild(DAGNode)
                    DAGNode.addParent(DAGNodeArray[dependencyIndex])
                    counter += 1
            if counter == 0:
                dag.roots.append(DAGNode)
        dag.numOfInputs = paraIndex

        # set DAGNodeArray[ii] to None if it does not contribute to the final action
        counterVec = [0] * len(DAGNodeArray)
        stack = []
        curr = DAGNodeArray[-1]
        stack.append(curr)
        while len(stack) != 0:
            curr = stack.pop()
            counterVec[curr.index] += 1
            for parent in curr.parents:
                stack.append(parent)
        for ii in range(len(DAGNodeArray)):
            if counterVec[ii] == 0:
                DAGNodeArray[ii] = None

                
        dag.DAGNodeArray = DAGNodeArray

        subDAGIndexes = []
        superDAGIndexes = []
        equivalentIndex = -1
        for ii in range(len(cls.generated)):
            old_dag = cls.generated[ii]
            if old_dag.DAGNodeArray[-1].action.__name__ != dag.DAGNodeArray[-1].action.__name__:
                continue

            # sanity check
            old_attackVector = [None if node == None else node.action for node in old_dag.DAGNodeArray]
            attackVector = [None if node == None else node.action for node in dag.DAGNodeArray]
            # two pointer technique
            oldLonger = len(old_attackVector) > len(attackVector)
            counter = 0
            iii = 0
            jjj = 0
            while iii < len(old_attackVector) and jjj < len(attackVector):
                if old_attackVector[iii] is not None and \
                    attackVector[jjj] is not None and \
                    old_attackVector[iii].__name__ == attackVector[jjj].__name__:
                    iii += 1
                    jjj += 1
                    counter += 1
                else:
                    if oldLonger:
                        iii += 1
                    else:
                        jjj += 1
            
            if counter == len(old_attackVector) and not old_dag.isSubDAGOf(dag):
                sys.exit("Error: old_dag is not a subDAG of dag") 
            if counter == len(attackVector) and not dag.isSubDAGOf(old_dag):
                sys.exit("Error: dag is not a subDAG of old_dag")



            isSubTree = False
            isSuperTree = False
            if dag.isSubDAGOf(old_dag):
                superDAGIndexes.append(ii)
                isSubTree = True
            if old_dag.isSubDAGOf(dag):
                subDAGIndexes.append(ii)
                isSuperTree = True
                if isSubTree and isSuperTree:
                    equivalentIndex = ii
                    break
        
        if equivalentIndex != -1:
            # Cache the name here too: without this, a sequence that maps to an
            # existing (equivalent) DAG is never memoised, so a later lookup of the
            # same sequence re-runs the equivalence search against a now-larger
            # `generated` list and can mint a fresh, non-matching index — which makes
            # Pruning 6's dataMap lookup miss the data runinitialPass keyed under the
            # original index. Memoising keeps a sequence pinned to one stable index.
            cls.name2index[name] = equivalentIndex
            return dag, equivalentIndex

        cls.subTree.append(subDAGIndexes)
        cls.superTree.append(superDAGIndexes)
        thisDAGIndex = len(cls.subTree) - 1
        for index in subDAGIndexes:
            cls.superTree[index].append(thisDAGIndex)
        for index in superDAGIndexes:
            cls.subTree[index].append(thisDAGIndex)

        cls.name2index[name] = thisDAGIndex
        
        cls.generated.append(dag)
        return dag, thisDAGIndex

        

   
def find_matching_permutations(list1, list2):
    indexesList = []
    for aa in list1:
        indexes = [index for index in range(len(list2)) if list2[index] == aa]
        indexesList.append(indexes)
    # Generate all possible combinations of elements
    output_list = list(itertools.product(*indexesList))
    
    # Filter out combinations that contain duplicates
    output_list = [list(t) for t in output_list if len(t) == len(set(t))]
    # print(output_list)
    return output_list




def generateActionDependency(actionList, actionDependencies):
    if len(actionList) != len(actionDependencies):
        sys.exit("Error: actionList and actionDependencies have different lengths")
    actionDependency = {}
    for ii in range(len(actionList)):
        action = actionList[ii]
        dependency = actionDependencies[ii]
        actionDependency[action.__name__] = dependency
    return actionDependency



if __name__ == "__main__":
    action1 = MintLPUniswapV2
    action2 = SwapUniswapWETH2DAI
    action3 = SwapUniswapDAI2WETH
    action4 = LP2BorrowLimit
    action5 = BorrowSCUSDC
    action6 = BorrowSCDAI
    # action_list = [action1, action2, action4, action1, action5, action6, action3]
    # action_list1 = [action1, action2, action3]
    # result = find_matching_permutations(action_list1, action_list)
    # print(result)

    # print("should print: ", [ [0, 1, 6], [3, 1, 6] ])


    action1_prestate_dependency = [SwapUniswapWETH2DAI, SwapUniswapDAI2WETH, MintLPUniswapV2]
    action2_prestate_dependency = [MintLPUniswapV2, SwapUniswapDAI2WETH, SwapUniswapWETH2DAI]
    action3_prestate_dependency = [MintLPUniswapV2, SwapUniswapWETH2DAI, SwapUniswapDAI2WETH]
    action4_prestate_dependency = [LP2BorrowLimit]
    action5_prestate_dependency = [MintLPUniswapV2, SwapUniswapWETH2DAI, BorrowSCDAI, SwapUniswapDAI2WETH, BorrowSCUSDC]
    action6_prestate_dependency = [MintLPUniswapV2, SwapUniswapWETH2DAI, BorrowSCUSDC, SwapUniswapDAI2WETH, BorrowSCDAI]

    actionList = [action1, action2, action3, action4, action5, action6]
    actionDependencies = [action1_prestate_dependency, action2_prestate_dependency, \
                          action3_prestate_dependency, action4_prestate_dependency, \
                          action5_prestate_dependency, action6_prestate_dependency]


    actionDependency = generateActionDependency(actionList, actionDependencies)

    actionVector = [SwapUniswapWETH2DAI, LP2BorrowLimit, SwapUniswapWETH2DAI, MintLPUniswapV2, MintLPUniswapV2, MintLPUniswapV2]
    actionVector2 = [SwapUniswapWETH2DAI, LP2BorrowLimit, MintLPUniswapV2]
    actionVector3 = [SwapUniswapWETH2DAI, LP2BorrowLimit, MintLPUniswapV2]

    AttackDAGGenerator.setActionDependency(actionDependency)
    dag1, index = AttackDAGGenerator.generateDAG(actionVector)
    print("DAG1: ", "index: ", index)
    dag1.printDAG()
    dag2, index2 = AttackDAGGenerator.generateDAG(actionVector2)
    print("\nDAG2: ", "index: ", index2)
    dag2.printDAG()
    possibleMappings = dag2.isSubDAGOf(dag1)
    # print("possibleMappings: ", possibleMappings)

    dag3, index3 = AttackDAGGenerator.generateDAG(actionVector3)
    print("\nDAG3: ", "index: ", index3)
    dag3.printDAG()


    dag1Input = [1111, 2222, 3333, 4444, 5555, 6666]


    print("dag1 == dag2: ", dag1.isEquivalent(dag2))
    print("is dag2 a subdag of dag1: ", dag2.isSubDAGOf(dag1))
    dag2.setSimplifierExpander(dag1)
    dag2Input = [5, 10, 12]
    print("dag1Input: ", dag1Input)
    print("Convert self inputs", dag2.convertSelfInputs(dag1Input))
    print("Simplified input", dag2.simplifyInputs(dag1Input))
    print("Extended input", dag2.extendInputs(dag2Input))


    print("dag1 == dag3: ", dag1.isEquivalent(dag3))
    print("is dag3 a subdag of dag1: ", dag3.isSubDAGOf(dag1))
    dag3.setSimplifierExpander(dag1)
    dag3Input = [5, 10, 12]
    print("dag1Input: ", dag1Input)
    print("Simplified input", dag3.simplifyInputs(dag1Input))
    print("Extended input", dag3.extendInputs(dag3Input))



    print("dag2 == dag3: ", dag2.isEquivalent(dag3))
    print("is dag2 a subdag of dag3: ", dag2.isSubDAGOf(dag3))
    
    dag3Input = [5, 10, 12]
    print("dag3Input: ", dag3Input)
    print("convertSelfInputs:", dag2.convertSelfInputs(dag3Input))

    dag2.setSimplifierExpander(dag3)
    print("Simplified input", dag2.simplifyInputs(dag3Input))
    print("Extended input", dag2.extendInputs(dag3Input))
                                                            # None
    actionVector4 = [SwapUniswapWETH2DAI, MintLPUniswapV2, LP2BorrowLimit, BorrowSCUSDC, SwapUniswapDAI2WETH, BorrowSCDAI]
    dag4, index4 = AttackDAGGenerator.generateDAG(actionVector4)
                                                                                # None
    actionVector5 = [MintLPUniswapV2, SwapUniswapDAI2WETH, SwapUniswapWETH2DAI, LP2BorrowLimit, BorrowSCUSDC, BorrowSCDAI]
    dag5, index5 = AttackDAGGenerator.generateDAG(actionVector5)

    dag4.isSubDAGOf(dag5)

    # [2, 0, None, 4, 1, 5]
    

