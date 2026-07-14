# `deps.json` — the action dependency graph

`deps.json` is an **optional, hand-written** input that narrows FlashSyn's search. Drop one
next to an example's `manifest.toml` (`examples/<name>/deps.json`) and it is **auto-loaded**
by `collect` and `synthesize` — there is no flag and no generator; its presence is the switch.

- **Absent** (the default) → the engine uses a conservative *all-others* graph: every action's
  prestate is assumed to depend on every other action. This is **sound** — it never prunes a
  prefix the search needs — but it collects longer prefixes and explores more orderings.
- **Present** → the engine uses your graph instead, after validating it (see *Validation*).

You author it by hand because the dependencies that matter are usually *semantic* (a
liquidation needs a prior deposit + donate to make the position underwater), and those are
exactly the ones a purely mechanical analysis misses.

## What a dependency means

`A depends on B` means **B must be able to run before A for A to reach a usable prestate.**
Concretely the engine uses the graph two ways:

1. **Data collection** (`collect`): to sample action `A`, it first runs `A`'s dependency
   actions as a prefix. If the prefix is missing an action `A` truly needs, `A` reverts and
   produces no data point.
2. **Search pruning** (`synthesize`): a candidate trace is dropped if no data was collected
   for its shape (`prune.py`, "Pruning 6"). Actions with **no** dependency between them are
   treated as commuting — only one of their orderings is searched, skipping the `k!`
   permutations. That pruning is the whole point: it is what lets the search scale.

## Format

```json
{
  "depends_on": {
    "<actionName>": ["<dependencyActionName>", ...],
    ...
  }
}
```

- Keys and values are action `name`s from the manifest's `[[actions]]`.
- Only `depends_on` is read; any other keys are ignored.

### Validation (all fail loud)

1. **Every action must appear as a key** — even ones with no dependencies (`[]`). This is the
   staleness guard: rename or add an action and a matching-actions check forces you to update
   the file.
2. **Every dependency must be a known action** — catches typos and removed actions.
3. **Do not list an action as its own dependency** — the engine adds that self-edge
   automatically (it wires edges between repeated occurrences of the same action in a trace,
   e.g. `deposit` then `deposit`).

## Authoring it safely

The danger is **omitting a real dependency**: that starves an action of collected data, the
search prunes every trace using it, and you silently miss attacks. So the safe direction is
to list **more**, not fewer:

- Start from all-others (list every other action for each action) — that reproduces the safe
  default — then **remove only the pairs you are confident commute** (genuinely independent
  actions). The removals are where the speedup comes from.
- After editing, **verify**: run `synthesize` and confirm the known attack still appears. If a
  vector you expected disappears, you over-pruned — add dependencies back.
- A too-sparse graph does not just miss attacks; it can leave an action with degenerate
  (empty-prefix) data and crash the downstream approximator. Erring generous avoids this.

## Worked example: `examples/euler/deps.json`

```json
{
  "depends_on": {
    "eulerDeposit": [],
    "eulerTouch": [],
    "eulerMint": ["eulerDeposit"],
    "eulerBurn": ["eulerDeposit", "eulerMint"],
    "eulerDonate": ["eulerDeposit", "eulerMint"],
    "eulerLiquidateWithdraw": ["eulerDeposit", "eulerMint", "eulerDonate"]
  }
}
```

Reading it against the Euler exploit (`deposit` collateral → `mint` to inflate the
position → `donate` to make it underwater → `liquidate` it):

- `eulerDeposit` and `eulerTouch` are **roots** (`[]`): `deposit` runs from the attacker's
  starting USDC; `touch` just refreshes an account and needs nothing.
- `eulerMint` needs collateral, so it depends on `eulerDeposit`.
- `eulerDonate` / `eulerBurn` act on the eUSDC/dUSDC position, so they depend on
  `eulerDeposit` + `eulerMint`.
- `eulerLiquidateWithdraw` only succeeds against an **underwater** position, which
  `deposit` + `mint` + `donate` create — hence those three.

Verified: with this file, `synthesize euler` finds the headline attack
`eulerDeposit, eulerMint, eulerDonate, eulerLiquidateWithdraw` (~$22.4M) and does not crash.
It is slightly more aggressive than all-others — it drops the lower-value variant that uses
`donate` twice — which is the expected trade for a narrower graph. If you wanted both back,
loosen the graph (e.g. give `eulerLiquidateWithdraw` more dependencies).

## Where it is consumed

`src/manifest.py:_load_dependencies` reads the file, adds the self-edge, validates, and hands
the per-action dependency list to the DAG builder (`src/Actions/AttackDAG.py`) and the initial
data collection. Search pruning that relies on it lives in `src/Actions/prune.py`.
