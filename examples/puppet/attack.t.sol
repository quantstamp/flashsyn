// SPDX-License-Identifier: MIT
pragma solidity 0.8.12;

// Damn Vulnerable DeFi — "Puppet" (V1). A lending pool prices its DVT collateral
// off a Uniswap V1 spot oracle (ETH balance / DVT balance of the exchange). Dumping
// DVT into the tiny exchange collapses that spot price, so the pool then lets you
// borrow its entire DVT reserve for almost no ETH collateral.
//
// Unlike the mainnet examples, nothing is read off the fork: setUp() DEPLOYS the
// whole scenario locally (DVT, a Uniswap V1 exchange via deployCode, the pool), so
// the fork block in the run command is irrelevant — any archive block the RPC serves
// works. Template used: https://github.com/nicolasgarcia214/damn-vulnerable-defi-foundry

import {DSTest} from "ds-test/test.sol";
import {Vm} from "forge-std/Vm.sol";
import {stdCheats} from "forge-std/stdlib.sol";
import {Strings} from "mylib/StringCon.sol";
import {Collect} from "mylib/Collect.sol";
import {ERC20} from "openzeppelin-contracts/token/ERC20/ERC20.sol";
import {ReentrancyGuard} from "openzeppelin-contracts/security/ReentrancyGuard.sol";
import {Address} from "openzeppelin-contracts/utils/Address.sol";


// --- Damn Vulnerable DeFi contracts (inlined, verbatim from the DVD suite) ---------

contract DamnValuableToken is ERC20 {
    constructor() ERC20("DamnValuableToken", "DVT") {
        _mint(msg.sender, type(uint256).max);
    }
}

// PuppetPool: borrow DVT by depositing 2x its value in ETH, where "value" is read
// from the Uniswap V1 spot price. That oracle is the vulnerability.
contract PuppetPool is ReentrancyGuard {
    using Address for address payable;

    mapping(address => uint256) public deposits;
    address public immutable uniswapPair;
    DamnValuableToken public immutable token;

    error NotDepositingEnoughCollateral();
    error TransferFailed();

    constructor(address tokenAddress, address uniswapPairAddress) {
        token = DamnValuableToken(tokenAddress);
        uniswapPair = uniswapPairAddress;
    }

    function borrow(uint256 borrowAmount) public payable nonReentrant {
        uint256 depositRequired = calculateDepositRequired(borrowAmount);
        if (msg.value < depositRequired) revert NotDepositingEnoughCollateral();
        if (msg.value > depositRequired) {
            payable(msg.sender).sendValue(msg.value - depositRequired);
        }
        deposits[msg.sender] = deposits[msg.sender] + depositRequired;
        if (!token.transfer(msg.sender, borrowAmount)) revert TransferFailed();
    }

    function calculateDepositRequired(uint256 amount) public view returns (uint256) {
        return (amount * _computeOraclePrice() * 2) / 10**18;
    }

    function _computeOraclePrice() private view returns (uint256) {
        // price of the token in wei, per the Uniswap pair's reserves
        return (uniswapPair.balance * (10**18)) / token.balanceOf(uniswapPair);
    }
}


// --- Uniswap V1 (deployed from Vyper bytecode via deployCode) -----------------------

interface UniswapV1Exchange {
    function addLiquidity(uint256 min_liquidity, uint256 max_tokens, uint256 deadline)
        external payable returns (uint256);
    function tokenToEthSwapInput(uint256 tokens_sold, uint256 min_eth, uint256 deadline)
        external returns (uint256);
    function ethToTokenSwapInput(uint256 min_tokens, uint256 deadline)
        external payable returns (uint256);
}

interface UniswapV1Factory {
    function initializeFactory(address template) external;
    function createExchange(address token) external returns (address);
}


// --- FlashSyn harness ---------------------------------------------------------------
// The engine reads everything above the first generated/test function as the preamble
// and appends its collector/attack functions inside this contract, so `Puppet` must be
// the last contract and its state (dvt, puppetPool, uniswapExchange, attacker) is what
// the action snippets reference. (This comment must not contain the preamble-boundary
// tokens themselves — see src/conventions.py.)
contract Puppet is DSTest, stdCheats {
    Vm internal constant vm = Vm(HEVM_ADDRESS);

    uint256 internal constant UNISWAP_INITIAL_TOKEN_RESERVE = 10e18;
    uint256 internal constant UNISWAP_INITIAL_ETH_RESERVE = 10e18;
    uint256 internal constant ATTACKER_INITIAL_TOKEN_BALANCE = 1_000e18;
    uint256 internal constant ATTACKER_INITIAL_ETH_BALANCE = 25e18;
    uint256 internal constant POOL_INITIAL_TOKEN_BALANCE = 100_000e18;
    uint256 internal constant DEADLINE = 10_000_000;

    UniswapV1Exchange internal uniswapExchange;
    UniswapV1Factory internal uniswapV1Factory;
    DamnValuableToken internal dvt;
    PuppetPool internal puppetPool;
    address payable internal attacker;

    // Scratch state for the PoolBorrow action snippet. These are contract-level (not
    // locals) so the snippet can be inlined more than once in a sequence without
    // re-declaring a variable — the generated collector concatenates action snippets.
    uint256 internal _amt;
    uint256 internal _dep;

    Collect internal collect;

    function setUp() public {
        collect = new Collect();
        attacker = payable(address(uint160(uint256(keccak256(abi.encodePacked("attacker"))))));
        vm.label(attacker, "Attacker");
        vm.deal(attacker, ATTACKER_INITIAL_ETH_BALANCE);
        // On a fork this test contract's address holds no ETH, so fund it to seed the
        // exchange below (setUp runs unpranked, i.e. as this contract).
        vm.deal(address(this), UNISWAP_INITIAL_ETH_RESERVE);

        // Token traded on Uniswap. `new` mints max supply to this test contract.
        dvt = new DamnValuableToken();
        vm.label(address(dvt), "DVT");

        // Deploy a Uniswap V1 factory + exchange template from vendored Vyper bytecode.
        uniswapV1Factory = UniswapV1Factory(deployCode("./src/build-uniswap/v1/UniswapV1Factory.json"));
        UniswapV1Exchange template = UniswapV1Exchange(deployCode("./src/build-uniswap/v1/UniswapV1Exchange.json"));
        uniswapV1Factory.initializeFactory(address(template));
        uniswapExchange = UniswapV1Exchange(uniswapV1Factory.createExchange(address(dvt)));
        vm.label(address(uniswapExchange), "Uniswap Exchange");

        // The vulnerable lending pool, priced off the exchange above.
        puppetPool = new PuppetPool(address(dvt), address(uniswapExchange));
        vm.label(address(puppetPool), "Puppet Pool");

        // Seed the exchange with 10 DVT / 10 ETH and the pool with 100k DVT.
        dvt.approve(address(uniswapExchange), UNISWAP_INITIAL_TOKEN_RESERVE);
        // Deadline must be block-relative: on a fork block.timestamp is ~1.7e9, so a
        // small constant deadline would already be in the past and revert.
        uniswapExchange.addLiquidity{value: UNISWAP_INITIAL_ETH_RESERVE}(
            0, UNISWAP_INITIAL_TOKEN_RESERVE, block.timestamp + 1000);
        dvt.transfer(attacker, ATTACKER_INITIAL_TOKEN_BALANCE);
        dvt.transfer(address(puppetPool), POOL_INITIAL_TOKEN_BALANCE);

        // Fail loud if the pool didn't wire up to the expected 2x-collateral oracle.
        require(
            puppetPool.calculateDepositRequired(POOL_INITIAL_TOKEN_BALANCE) == POOL_INITIAL_TOKEN_BALANCE * 2,
            "Puppet: unexpected initial oracle price");

        // Everything after this runs as the attacker (25 ETH + 1000 DVT).
        vm.startPrank(attacker);
        dvt.approve(address(uniswapExchange), 2 ** 256 - 1);
    }
}
