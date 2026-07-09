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


# TODO  1. Rename this class to be <nameOfProtocol>Action. This is the base class from which all other protocol actions will be derived
class protocolAction(ActionPro):  

    # TODO 2. Define the dict below to include the initial balances of the attacker account. {"currency": value}
        # Value ignores the decimals of the token. Ex: initialBalances = {"USDC": 400000000}
    initialBalances = {}
 
    currentBalances = initialBalances.copy()  # DON'T CHANGE

    
    # TODO: 3. Define the dict below to include the prices of all tokens of interest. 
        # Stablecoins can be hardcoded to $1. Price data at the time the chain was forked should be used for other assets. 
        # Values ignore decimals. Ex: tokenPrices = {"ETH": 1000.0, "USDC": 1.0}
    
    # Used to calculate the profit 
    TokenPrices = {}   

    # tokens of interest
    TargetTokens = TokenPrices.keys()    # DON'T CHANGE

    # TODO 3b. Map every token an action moves to its Solidity variable in the harness
    # and its decimals: {"USDC": ("USDC", 6)}. The default collectorStr() reads
    # balances via these to measure each action's output, so a plain action only
    # needs actionStr(). Ex: tokenInfo = {"USDC": ("USDC", 6), "eUSDC": ("eUSDC", 18)}
    tokenInfo = {}



    # TODO 4. (Optional) The Solidity preamble the collectors are appended to.
        # Leave this unset and the engine reads it straight from your attack.t.sol —
        # one source of truth, nothing to keep in sync. Only assign a start_str
        # literal here if you need to override that (the Euler example still does).
        # start_str = '''...preamble up to the first testExample function...'''

    # TODO 5. Define this function based on the objective function identified in the Protocol Analysis.
    def calcProfit(stats):
        if stats == None:
            return 0         
        # We choose to calculate profit here because it's hard to handle integer subtraction in the Solidity.
        USDC_earned = stats[0] - protocolAction.initialBalances['USDC']
        return USDC_earned

    @classmethod
    # Used to collect initial round of data points
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

        # NOTE TargetDataPoints will be 500 for most executions however this may vary depending on the protocol (i.e., high maxSynthesisLength)

        initialPassCollectData4( actionSpecs , ActionWrapper, TargetDataPoints = 500, maxLenGlobal = maxLen)
        ShowDataPointsForEachAction( action_list_1 )
        end = time.time()
        print("in total it takes %f seconds" % (end - start))


    @classmethod
    def runinitialPass(cls):  # DON'T CHANGE
        # Build one approximator per terminal action from the collected data.
        # The action sequence comes from each file's saved payload (names), and
        # classes are resolved via the registry (cls.action_by_name) — not by
        # splitting the pkl filename on "_" or looking names up in globals().
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


# TODO 7. Define each Protocol Action subclass below.
    #  Each class should be named as: `<protocolName>ActionName()`, and derive the protocolAction class declared above.
    #  IMPORTANT: give each action a distinct name — do NOT reuse `protocolAction`, or it will shadow the base
    #  class and `ActionWrapper` in main() will point at an action instead of the base.
    # Reference the examples/ directory as needed.
class protocolActionExample(protocolAction):
    approximators = NumericalApproximatorsPro()

    # TODO 7a. Define the following variables as it relates to this Action
    numInputs = 0
    tokensIn = []    
    tokensOut = []    
    range = []     

    # TODO 7b. Define `action` to be the Solidity code FlashSyn will use to search for inputs to this Action.
        # Include a comment with the Action name.
        # Insert dollar signs ($$) as the argument for the value that FlashSyn will approximate.
    @classmethod
    def actionStr(cls):
        action = '''
        // Action:
        '''
        return action

    # That's usually all an action needs. Given tokensIn/tokensOut + the wrapper's
    # tokenInfo, the base class derives BOTH:
    #   - collectorStr(): wraps actionStr() in balance reads and reverts the output delta
    #   - transit(): subtracts the tokensIn amounts, adds the simulate() outputs to tokensOut
    #
    # TODO 7c (only if needed). Override them for an exotic action — e.g. output that
    # isn't a simple attacker-balance delta, or funds that move in a non-1:1 way.
    # The Euler example's liquidation is one such case. Sketch:
    #
    #   @classmethod
    #   def collectorStr(cls):
    #       return '''<read before> <actionStr body> revert(Strings.append("FlashSyn: ", <delta>));'''
    #
    #   @classmethod
    #   def transit(cls, inputs, actionList):
    #       ...  # update cls.currentBalances[...] however this action really moves funds

# TODO 8. Include all remaining Protocol Action classes.

# TODO 9. Complete the main() function.
def main():
    # DO NOT CHANGE ExecutionMode. 
    config.ExecutionMode = DVD  # DVD for normal cases. 
                                # The only exception is some functions requires to be called by a contract instead of an EOA
                                # In this case, contact Jeff to set up a custimized execution mode. 

    config.command = ""  # TODO 9a. Define the command used by the Foundry to run the contract. This will likely be the name of the protocol.
    config.benchmarkName = ""  # TODO 9b. Define the name of the benchmark, simply for distinguishing between different benchmarks

    # ===========================================================================================================
    # =========================== run dependencyCheck.py to get the following information =====================
    # ===========================================================================================================

    # NOTE: If you are waiting for the completion of the Foundry script, just complete this section as if all actions were dependent on eachother.

    # TODO - 9c. Define variables for all Action classes included in this script.

    action1 = protocolActionExample

    # TODO - 9d. Define an `action_list` that contains all of the Actions defined above.

    action_list = []

    # TODO - 9e. Define lists of each prestate dependency for the actions. 
        # The last value of each prestate dependency should be the Action itself.
        # Ex: action1_prestate_dependency = [action2, action3, action4, action5, action6] + [action1]

    # prestate_dependency means executing the actions inside the actionX_prestate_dependency vector 
    # will alter the prestates of actionX. It is used to reach a wider range of data points
    # If you are unsure about the prestates, just list all actions inside the actionX_prestate_dependency

    action1_prestate_dependency = []

    # TODO - 9f. Define list `actionDependencies` that contains all of the lists you just defined

    actionDependencies = [action1_prestate_dependency]

    actionDependency = generateActionDependency(action_list, actionDependencies) #DO NOT CHANGE

    attackDAGGenerator.setActionDependency(actionDependency) # DO NOT CHANGE

    # ===========================================================================================================
    # =========================== Set up execution parameters ===================================================
    # ===========================================================================================================

    # TODO 9g. Define ActionWrapper to be the base class for all other Protocol Actions (the first class you defined in Step 1).
    ActionWrapper = protocolAction
    ActionWrapper.initialPass(action_list, actionDependencies, ActionWrapper) # DO NOT CHANGE

    # TODO 10. Congrats! Your Python Script for FlashSyn Analysis should now be complete.
        # Now, you will run FlashSyn to collect initial data points. Don't forget to include the folder initialDataPoints/protocolName before execution.


    #TODO 11. Once the initial data points have been collected, comment out the call to initialPass() and uncomment everything below to run the synthesis.

    # CounterExampleLoop = True
    # Pruning = True
    # maxSynthesisLen = 6
    # isFlashSynPro2 = True

    # ActionWrapper.runinitialPass()
    # config.benchmarkName = ""  # same benchmark name as set in 9b
    # config.processNum = 1

    # Synthesizer = synthesizer(action_list, protocolAction, config.processNum)
    # Synthesizer.synthesis(maxSynthesisLen, Pruning, CounterExampleLoop, isFlashSynPro2)





if __name__ == "__main__":
    main()
    