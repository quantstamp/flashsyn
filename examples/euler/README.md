# Euler example

The [Euler Finance](https://phalcon.xyz/tx/eth/0x465a6780145f1efe3ab52f94c006065575712d2003d83d85481f3d110ed131d9)
exploit (March 2023), as a worked FlashSyn analysis. This is the reference for the **Python
action-model** style — the escape hatch for actions whose fund movement a `manifest.toml`
can't express (Euler's self-liquidation zeroes several balances at once).

- `EulerActions.py` — the Python action model, exposing `flashsyn_setup()`.
- `attack.t.sol` — the Foundry harness (the preamble the engine reads: interfaces, `setUp()`,
  `profitSummary()`).

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
