# Euler example

The [Euler Finance](https://phalcon.xyz/tx/eth/0x465a6780145f1efe3ab52f94c006065575712d2003d83d85481f3d110ed131d9)
exploit (March 2023), as a worked FlashSyn analysis. It's the reference example for `effects`:
the self-liquidation zeroes several balances at once (`op = set`) and `mint` inverts the default
parameter/approximation direction.

- `manifest.toml` — the action model as data. Each action is just `solidity` + `effects`
  (+ `token_info` for decimals); collectors are generated.
- `attack.t.sol` — the Foundry harness (the preamble the engine reads: interfaces, `setUp()`,
  `profitSummary()`, and the contract-level `temp`/`repay`/`yield` locals the liquidation reuses).
  It imports the shared `Collect` helper and deploys it in `setUp()`.

## How the collectors are generated

Collectors are always derived from an action's `effects` and emitted through the `Collect` helper
(`src/foundryModule/lib/mylib/Collect.sol`):

- for every `collected` effect, measure that token's balance delta and record it with
  `collect.gained("<token>", raw)` (`op = add`, `after − before`) or `collect.spent(...)`
  (`op = sub`, `before − after`);
- the engine appends `collect.flush()`, which reverts `FlashSyn: <token>=<raw> ...`; the parser
  maps values to tokens by name and scales each by `token_info` decimals (single source) as a float.

So `eulerBurn` is just `solidity = "eUSDC.burn(0, $$ * 1e18);"` + two `{op="sub", src="collected"}`
effects, and its collector — two before-reads, the burn, two `collect.spent` calls, a flush — is
generated. The action Solidity is written once; the collector is never duplicated.

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
`eulerDeposit → eulerMint → eulerDonate → eulerLiquidateWithdraw`, **Best Profit 22,415,806**
with parameters `[100585937, 1501953125, 908203125]` — close to the historical ~22.4M
reference, and deterministic (three runs land on the same profit). Early rounds printing
`0 executions succeed` / `Best Profit 0.2` are the pre-refinement phase, not a failure — let
it run to `End of Synthesis`.

> Note: `eulerLiquidateWithdraw` and `eulerTouch` have `numInputs = 0`; `eulerTouch` is a
> no-op (it collects no data and is skipped during collection). The exploit does not use it.
