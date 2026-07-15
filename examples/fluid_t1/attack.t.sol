// SPDX-License-Identifier: MIT
pragma solidity >0.4.21;

// Fluid protocol (Instadapp) T1 vault — the DEBT-SHIM pattern. Pairs with manifest.toml.
//
// Borrow-side debt modeling. Fluid vault debt is NFT-internal (non-fungible), so a naive
// "borrow USDC" action would inflate the attacker's USDC balance and look like profit while
// the liability escapes FlashSyn's balance-delta model. We fix that WITHOUT touching the
// engine: a DebtShim contract exposes the position's live debt as `balanceOf(attacker)`,
// and the manifest registers it as a negative-priced pseudo-token `dUSDC`. Borrowing then
// nets ~0 (received USDC + equal debt), and profit only appears from a real mispricing.
// The pattern generalizes to any NFT-position lending vault.

import {DSTest} from "ds-test/test.sol";
import {Vm} from "forge-std/Vm.sol";
import {stdCheats} from "forge-std/stdlib.sol";
import {Strings} from "mylib/StringCon.sol";
import {FlashSynHarness} from "mylib/Harness.sol";


interface IUSDC {
    function approve(address spender, uint256 value) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function configureMinter(address minter, uint256 minterAllowedAmount) external returns (bool);
    function masterMinter() external view returns (address);
    function mint(address _to, uint256 _amount) external returns (bool);
}

interface IERC20 {
    function approve(address spender, uint256 value) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

// Fluid T1 vault (normal collateral + normal debt). operate: +col/+debt add, -col/-debt remove.
interface IFluidVaultT1 {
    function operate(uint256 nftId, int256 newCol, int256 newDebt, address to)
        external payable returns (uint256, int256, int256);
}

// Only the FIRST struct that VaultResolver.positionByNftId returns. The ABI head is offsets,
// so declaring just this one decodes it correctly and ignores the trailing VaultEntireData.
struct UserPosition {
    uint256 nftId; address owner; bool isLiquidated; bool isSupplyPosition;
    int256 tick; uint256 tickId; uint256 beforeSupply; uint256 beforeBorrow;
    uint256 beforeDustBorrow; uint256 supply; uint256 borrow; uint256 dustBorrow;
}
interface IVaultResolver {
    function positionByNftId(uint256 nftId) external view returns (UserPosition memory);
}

// The debt shim: reports the attacker position's live debt (in USDC, 6 decimals) as an ERC20
// balance, so the manifest's derived collector and profit readout can read it like any token.
// This is the whole trick — it lets a NEGATIVE-priced pseudo-token stand in for NFT-internal debt.
contract DebtShim {
    IVaultResolver constant RES = IVaultResolver(address(0xA5C3E16523eeeDDcC34706b0E6bE88b4c6EA95cC));
    uint256 public nftId;
    function setNft(uint256 id) external { nftId = id; }
    function balanceOf(address) external view returns (uint256) {
        if (nftId == 0) return 0;
        return RES.positionByNftId(nftId).borrow;   // position debt, USDC 6-dec (incl. interest)
    }
}

contract Fluid_T1 is DSTest, stdCheats, FlashSynHarness {
    Vm internal constant vm = Vm(HEVM_ADDRESS);
    address payable constant attacker = payable(address(uint160(uint256(keccak256(abi.encodePacked("attacker"))))));

    IUSDC          internal constant USDC   = IUSDC(address(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48));
    IERC20         internal constant WSTETH = IERC20(address(0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0));
    IFluidVaultT1  internal constant VAULT  = IFluidVaultT1(address(0x1982CC7b1570C2503282d0A0B41F69b3B28fdcc3));

    // token_info var name for the dUSDC pseudo-token points at this deployed shim.
    DebtShim internal debtShim;
    uint256 public vaultNft;

    // Capital the attacker enters with (matches manifest [initial_balances]).
    uint256 constant USDC_CAPITAL   = 1000000e6;   // 1,000,000 USDC (for paybacks / working capital)
    uint256 constant WSTETH_COL     = 100e18;      // 100 wstETH deposited as collateral in setUp
    uint256 constant OPEN_DEBT      = 50000e6;     // open the position with 50,000 USDC debt so
                                                   // payback runs from a non-empty position

    function setUp() public {
        vm.label(attacker, "Attacker");

        // Fund: wstETH via forge-std tip (finds the balance slot), USDC via masterMinter.
        tip(address(WSTETH), attacker, WSTETH_COL);
        address MasterMinter = USDC.masterMinter();
        vm.prank(MasterMinter);
        USDC.configureMinter(attacker, type(uint256).max);

        vm.startPrank(attacker);
        USDC.mint(attacker, USDC_CAPITAL);
        require(USDC.balanceOf(attacker) == USDC_CAPITAL, "USDC funding failed");
        require(WSTETH.balanceOf(attacker) == WSTETH_COL, "wstETH funding failed");
        WSTETH.approve(address(VAULT), type(uint256).max);
        USDC.approve(address(VAULT), type(uint256).max);

        // Deploy the debt shim (prank is the attacker, but that's fine — it's a plain contract).
        debtShim = new DebtShim();

        // Open a T1 position: 100 wstETH collateral + 50,000 USDC debt (so payback runs from a
        // non-empty position). Register the NFT with the shim so dUSDC = the position's live debt.
        (vaultNft, , ) = VAULT.operate(0, int256(WSTETH_COL), int256(OPEN_DEBT), attacker);
        require(vaultNft != 0, "vault open failed");
        debtShim.setNft(vaultNft);
        require(debtShim.balanceOf(attacker) >= OPEN_DEBT, "expected initial debt");

        // Leave prank(attacker) open for the generated actions.
    }

    // Profit readout is derived from the manifest (profit_tokens + token_info), including the
    // negative-priced dUSDC read from debtShim.balanceOf(attacker).
}
