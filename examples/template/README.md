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

1. **`attack.t.sol`** — protocol-specific Solidity: interfaces, contract addresses, a
   `setUp()` that funds the attacker with the flash-loan capital and sets approvals, and a
   `profitSummary()` that prints the profit-token balances. (Optional `testExample`
   functions let `compile`/`deps` validate.)
2. **`manifest.toml`** — the search config: chain/block/contract, initial balances, token
   prices, `token_info`, and one `[[actions]]` entry per action (`tokens_in/out`, `range`,
   and the one Solidity snippet).

**Automated for you** (used to be hand-written Python):

- `numInputs` — counted from the `$$` in each action's `solidity`.
- the **data collector** — generated from `tokens_out` + `token_info` (override with `collector`).
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

## Two escape-hatch fields (still TOML)

The derived collector assumes each `tokens_out` is measured by a `balanceOf` delta, and the
derived `transit()` assumes the `$$` params are the consumed `tokens_in` amounts and
`simulate()`'s outputs go to `tokens_out`. When an action breaks those assumptions, two
**optional** per-action fields cover it without leaving the manifest:

- **`collector`** — raw Solidity used verbatim as the data collector (replaces the derived
  one). For outputs a `balanceOf` delta can't read: native ETH, an input-side amount, custom
  decimals.
- **`effects`** — a declarative balance transition (replaces `transit`), a list of
  `{token, op, src}` where `op` is `add | sub | set` and `src` is `paramN` (the Nth `$$`),
  `approxN` (the Nth collector output), or `0`. For actions that invert
  parameter/approximation (borrow, mint), zero a balance (a liquidation → `op = set, src = 0`),
  or have no measured output (donate, burn).

`tokens_in`/`tokens_out` always describe token *flow* for the search graph, independent of
`effects`.

## Worked examples

- `examples/harvest_usdt/`, `examples/harvest_usdc/` — manifest-only, verified end-to-end.
- `examples/puppet/` — `collector` + inverted `effects` on `borrow`; `collector`-only on a
  native-ETH swap; the reverse swap is pure defaults.
- `examples/euler/` — the escape-hatch reference: `effects` with `op = set` (self-liquidation
  zeroes balances), inverted `mint`, and no-output `donate`/`burn`.
