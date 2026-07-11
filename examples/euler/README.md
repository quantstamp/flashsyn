# Euler example

The [Euler Finance](https://phalcon.xyz/tx/eth/0x465a6780145f1efe3ab52f94c006065575712d2003d83d85481f3d110ed131d9)
exploit (March 2023), as a worked FlashSyn analysis. It exercises the full range of the
manifest model: the self-liquidation zeroes several balances at once (`effects` with
`op = set`) and `mint` inverts the default parameter/approximation direction.

Euler is also the **prototype for `use_collect_helper`** (see below): every collector is
*derived from `effects`* and emitted through a `Collect` helper in the harness, so no action
writes a `collector` field.

- `manifest.toml` — the action model as data. `use_collect_helper = true`; each action is just
  `solidity` + `effects` (+ `token_info` for decimals). Collectors are generated.
- `attack.t.sol` — the Foundry harness (the preamble the engine reads: interfaces, `setUp()`,
  `profitSummary()`, and the contract-level `temp`/`repay`/`yield` locals the liquidation reuses).
  It also defines the `Collect` helper contract, deployed in `setUp()`.

## The `use_collect_helper` prototype

With `use_collect_helper = true`, the engine builds each collector from the action's `effects`
instead of a hand-written `collector` string:

- for every `approxN` effect, measure that token's balance delta — `op = add` → gained
  (`after − before`), `op = sub` → spent (`before − after`) — in `approxN` order;
- decimals come from `token_info` (single source), and the value is recorded with
  `collect.balanceChange("<token>", wholeTokenDelta)`;
- the engine appends `collect.flush()`, which reverts `FlashSyn: <token>=<val> ...` for the
  parser (no measured token → `FlashSyn: 0`).

So `eulerBurn` is just `solidity = "eUSDC.burn(0, $$ * 1e18);"` + two `sub` effects, and its
collector — two before-reads, the burn, two `balanceChange` calls, a flush — is generated.
The action Solidity is written once; the collector is never duplicated. The flag is off by
default, so `harvest_*` and `puppet` are unaffected. **Prototype status:** the revert format is
parsed positionally (values in `approxN` order), so it produces byte-identical data to the old
per-action collectors; the token *names* in the revert string are not yet consumed by the parser
(a named/decimals-in-Python follow-up).

Chain: Ethereum mainnet, fork block **16818064**. Initial capital: 400,000,000 USDC.

## Run it (from the repo root)

Euler runs through the unified CLI, like the other examples — no copying files, no editing
source:

```sh
python3 flashsyn.py compile    euler        # compile the harness against the fork
python3 flashsyn.py deps       euler        # (optional) action dependency graph
python3 flashsyn.py collect    euler        # collect initial data points (~9 min)
python3 flashsyn.py synthesize euler > run.log   # counter-example synthesis
```

Expected result: FlashSyn rediscovers the exploit — best vector
`eulerDeposit → eulerMint → eulerDonate → eulerLiquidateWithdraw`, **Best Profit 29,185,439**
with parameters `[199600000, 1479041079, 423197409]`. (This is a higher-profit
parameterization of the same self-liquidation than the historical ~22.4M reference; the
modern optimizer settles on a different optimum.) Early rounds printing `0 executions
succeed` / `Best Profit 0.2` are the pre-refinement phase, not a failure — let it run to
`End of Synthesis`.

> Note: `eulerLiquidateWithdraw` and `eulerTouch` have `numInputs = 0`; `eulerTouch` is a
> no-op (it collects no data and is skipped during collection). The exploit does not use it.
