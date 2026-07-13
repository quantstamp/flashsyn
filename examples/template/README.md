# FlashSyn benchmark template

Copy this directory to `examples/<your-name>/` and fill in the two files. This is the
starting point for analyzing a new protocol with the manifest flow.

```
examples/<your-name>/
  manifest.toml    # the benchmark as data — the CLI builds the action model from it
  attack.t.sol     # the Foundry harness — the only code you write
```

## What you write vs. what's automated

**You write:**

1. **`attack.t.sol`** — protocol-specific Solidity **only**: interfaces, contract addresses, a
   `setUp()` that funds the attacker with the flash-loan capital and sets approvals, and a
   `profitSummary()` that prints the profit-token balances. No test functions — the CLI
   generates the collectors and the per-action smoke tests (`flashsyn.py validate`) from the manifest.
2. **`manifest.toml`** — the search config: chain/block/contract, initial balances, token
   prices, `token_info`, and one `[[actions]]` entry per action (`tokens_in/out`, `range`,
   and the one Solidity snippet).

**Automated for you** (used to be hand-written Python):

- `numInputs` — counted from the `$$` in each action's `solidity`.
- the **data collector** — generated from `tokens_out`/`effects` + `token_info`, emitted through the harness's `Collect` helper.
- the **balance transition** (`transit`) — generated from `tokens_in`/`tokens_out` (override with `effects`).
- `calcProfit` — derived from `profit_tokens` + balances + prices.
- the **action dependency graph** — all-others default (refine with `deps`).
- no file copying, no source editing to switch collection vs. synthesis.

## Run flow (from the repo root)

```sh
python3 flashsyn.py compile    <your-name>   # harness compiles + runs against the fork
python3 flashsyn.py deps       <your-name>   # (optional) action dependency graph
python3 flashsyn.py collect    <your-name>   # sample the actions -> initialDataPoints/<name>/
python3 flashsyn.py synthesize <your-name> > run.log
```

`collect` writes `.pkl` sample files; `synthesize` reads them, fits a polynomial per
action, searches action sequences + parameters, and validates candidates live on the
fork. The tail of `run.log` prints the best profit and winning vector + params. If you
change an action's `range`/`solidity` or add an action, **re-`collect`** before
`synthesize` (the samples go stale). Changing only `max_synthesis_len` needs just
`synthesize`.

## Writing actions

An action's `solidity` is embedded verbatim, so it can be **one call or many**.

- **`$$` is an independent search parameter.** Each `$$` becomes a distinct variable the
  optimizer searches. Reusing one value across calls → capture it once:
  `uint amt = $$ * 1e6;` then reference `amt`. Zero `$$` is a fixed action.
- **`tokens_in`/`tokens_out` are the NET flow** of the whole snippet. The collector
  measures the net balance delta of each `tokens_out` around the entire action.
- **Whatever the snippet references must be declared in the harness** — temp vars, a
  second account, structs, extra interfaces.

## When the default doesn't fit

Collectors are always emitted through the harness's `Collect` helper (deployed in `setUp`).
The default measures each `tokens_out` as a gain and the default `transit()` assumes the `$$`
params are the consumed `tokens_in` amounts and `simulate()`'s outputs go to `tokens_out`.
When an action breaks those assumptions:

- **`effects`** — a declarative balance transition (replaces `transit`), a list of
  `{token, op, src}` where `op` is `add | sub | set` and `src` is `input` (the sole `$$`;
  `inputN` for multi), `collected` (this token's own collected value), or a number constant.
  For actions that invert parameter/collection (borrow, mint), set a balance to a constant
  (a liquidation → `op = set, src = 0`; any whole-token number works), or have no measured
  output (donate, burn). `effects` also drives the derived collector: each `collected` token
  is `gained` (`add`) or `spent` (`sub`).
- **inline measurement** — when the collected quantity is an *internal* value (not a
  start-to-end balance delta, e.g. borrow's collateral `_dep`), record it in `solidity` with
  `collect.spent("<tok>", value)` / `collect.gained(...)`; the engine just appends `collect.flush()`.
- **native tokens** — a `token_info` entry `["", 18, "native"]` makes the collector read
  `address(attacker).balance` instead of `balanceOf`.

`tokens_in`/`tokens_out` always describe token *flow* for the search graph, independent of
`effects`.

## Worked examples

- `examples/harvest_usdt/`, `examples/harvest_usdc/` — plain swaps/deposits, all auto-derived.
- `examples/puppet/` — every path: inverted `effects` + inline measurement on `borrow`; a
  derived native-ETH swap; a derived ERC20 swap.
- `examples/euler/` — the `effects` reference: `op = set` (self-liquidation
  zeroes balances), inverted `mint`, and no-output `donate`/`burn`.
