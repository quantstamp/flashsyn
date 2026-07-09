# Puppet (Damn Vulnerable DeFi) — worked example

The first **Damn Vulnerable DeFi** benchmark in this repo. Unlike the mainnet examples
(Euler, Harvest), the whole scenario is **deployed locally in `setUp()`** rather than
read off a fork — so the fork block in the run command is arbitrary.

## The vulnerability

`PuppetPool` lends DVT against ETH collateral, and prices DVT off a **Uniswap V1 spot
oracle**: `depositRequired = 2 * amount * (exchange.ETH / exchange.DVT)`. The exchange
holds only 10 ETH / 10 DVT, so dumping the attacker's 1000 DVT into it collapses the
DVT price, after which the pool lets you borrow its entire 100,000-DVT reserve for a
negligible ETH deposit.

The exploit FlashSyn should rediscover: **`SwapUniswapDVT2ETH` → `PoolBorrow`**.

## Why this is a Python model, not a `manifest.toml`

Two of the three actions are ordinary swaps that fit the manifest model, but **`borrow`
inverts it**. The manifest assumes the consumed `tokens_in` amount is the search
parameter and the produced `tokens_out` amount is the approximation. For `borrow` it is
reversed: you *choose* the DVT amount to borrow (the parameter, received as `tokens_out`)
and *pay* an ETH collateral that is an approximated function of the manipulated oracle
(consumed `tokens_in`). That can't be expressed declaratively, so `PoolBorrow` overrides
`transit()` and `collectorStr()` — the same escape hatch Euler uses. See
`../../examples/template/README.md` ("When you need Python instead").

The two swaps keep `ActionPro`'s default `transit()`; they override only `collectorStr()`
because they move **native ETH**, which has no `balanceOf()` for the default collector to
read.

## Files

- `attack.t.sol` — harness. Inlines the DVD contracts (`DamnValuableToken`, `PuppetPool`)
  and deploys a Uniswap V1 exchange from vendored Vyper bytecode
  (`src/foundryModule/src/build-uniswap/v1/*.json`) via `deployCode`. `profitSummary()`
  prints DVT then ETH.
- `PuppetActions.py` — the three actions + `flashsyn_setup()`.

## Run (from the repo root)

```sh
python3 flashsyn.py compile    puppet     # deploy + validate the harness on a fork
python3 flashsyn.py deps       puppet     # (optional) action dependency graph
python3 flashsyn.py collect    puppet     # sample the actions
python3 flashsyn.py synthesize puppet > run.log
```

**Verified end-to-end** (Docker image, mainnet fork at block 16818064, forge 1.7.1).
FlashSyn rediscovers the exploit:

```
Best Attack Vector:  SwapUniswapDVT2ETH, PoolBorrow
Best Profit:         89000.0
Parameters:          [999, 99999]
```

i.e. dump 999 DVT to crash the oracle, then borrow 99,999 DVT out of the pool's 100k
reserve for a negligible ETH deposit. `compile` also validates the whole exploit on-chain
(`testExample2` reverts `FlashSyn: 100000 15`). Profit is the weighted metric
`(DVT - 1000)*1 + (ETH - 25)*1000`.

Needs Foundry + the pinned Python stack + an archive RPC — the Docker image is the
reliable environment (see the top-level README).

## Fork-specific setUp notes

The DVD tutorial ran unforked; this engine always forks, which required three
adjustments in `setUp()` that are easy to miss when porting a DVD challenge:
- fund the **test contract** with ETH (`vm.deal(address(this), ...)`) — on a fork its
  address holds no ETH, but it seeds the exchange before any prank;
- give `addLiquidity` a **block-relative deadline** (`block.timestamp + 1000`) — a small
  constant is already in the past at a 2023 fork timestamp;
- the run command's contract arg is **case-sensitive** (`Puppet`, matching the contract).
