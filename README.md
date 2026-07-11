# FlashSyn (reusable template)

A clean, protocol-agnostic extraction of [FlashSyn](https://arxiv.org/abs/2206.10708) — an automated
flash-loan / price-manipulation attack synthesizer. This repo ships the **fixed engine plus a blank
template**, not a baked-in exploit. To analyze a protocol you fill in two files; the engine is never
edited.

A full walkthrough (with the two-part `$$` / `revert("FlashSyn: …")` contract explained) is in
[`docs/REUSABLE_WORKFLOW.html`](docs/REUSABLE_WORKFLOW.html).

## Layout

```
src/
  synthesizer.py, Partial.py, shgo/, forge/   # search engine (do not edit)
  Actions/                                     # engine internals: approximation, DAG, data collection
  dependencyCheck.py                           # storage read/write dependency analysis
  FlashSynProActions/
    ActionPro.py                               # action base class (do not edit)
    template.py        <-- copy this           # Python action-model template
  foundryModule/
    run.sh                                     # generic forge runner (contract + chain + block)
    src/test/template.t.sol   <-- copy this    # Solidity harness template
    lib/                                       # ds-test, forge-std, mylib, openzeppelin
examples/
  euler/                                       # worked example — Euler self-liquidation (Python model)
  harvest_usdt/                                # worked example — Harvest Finance fUSDC leg (2020)
  harvest_usdc/                                # worked example — Harvest Finance fUSDT leg (2020)
  puppet/                                      # worked example — Damn Vulnerable DeFi "Puppet" (local deploy)
```

## What you author

Copy [`examples/template/`](examples/template/) to `examples/<name>/` — a fully commented
starting point — and fill in its two files:

1. **`attack.t.sol`** — the Foundry harness: interfaces, a `setUp()` that funds the attacker with the
   flash-loan capital and sets approvals, and a `profitSummary()`. The only code you write.
2. **`manifest.toml`** — the benchmark as data: chain/block/contract, initial balances, token prices,
   `token_info` (token → Solidity variable + decimals), and one entry per action (`tokens_in/out`,
   `range`, and the Solidity call). The engine builds the action model from it — `numInputs`, the data
   collector, the balance `transit()`, `calcProfit`, and the dependency graph are all derived.

Every example is a manifest — there is no separate Python action-model format. Data collectors are
generated and emitted through a shared `Collect` helper deployed in the harness
(`src/foundryModule/lib/mylib/Collect.sol`): the collector measures each output as a balance delta
and records it with `collect.balanceChange("<tok>", value)`, then the engine appends
`collect.flush()`. Two things shape an action that doesn't fit the plain swap/deposit default:

- **`effects`** — a declarative balance transition (`[{token, op = add|sub|set, src = paramN|approxN|0}]`),
  replacing the default `transit()`, for actions that invert parameter/approximation (borrow, mint),
  zero a balance (a liquidation), or have no measured output (donate, burn). `effects` also drives what
  the derived collector measures (each `approxN` token; `add`→gain, `sub`→spend).
- **inline measurement** — when the measured quantity is an *internal* value rather than a start-to-end
  balance delta (e.g. borrow's collateral `_dep`), the action records it directly in its `solidity` with
  a `collect.balanceChange("<tok>", value)` call; the engine just adds the `flush()`.

`token_info`'s optional 3rd element `"native"` makes the collector read `address(attacker).balance`
(for native ETH). `tokens_in/out` always describe token *flow* for the search graph, independent of the
above. See the Puppet manifest (both mechanisms) and `examples/template/README.md` for the full flow.

## Run procedure

An example that lives under `examples/<name>/` (a `manifest.toml` plus its
`attack.t.sol`) runs through the CLI — no copying files, no editing source to switch
between collection and synthesis:

```sh
python3 -m pip install -r requirements.txt   # prerequisites: Foundry + Python deps

python3 flashsyn.py compile    <name>        # compile the harness against the fork
python3 flashsyn.py deps       <name>        # (optional) action dependency graph
python3 flashsyn.py collect    <name>        # collect initial data points
python3 flashsyn.py synthesize <name> > run.log
```

The tail of `run.log` prints the best profit and the winning action sequence +
parameters. This works for **every** example, including Euler.

**Faster runs (`--fast-using-anvil`).** Add `--fast-using-anvil` to any subcommand to
route forge through one local [anvil](https://book.getfoundry.sh/anvil/) fork of the
example's chain/block instead of re-forking over the RPC on every invocation:

```sh
python3 flashsyn.py collect euler --fast-using-anvil     # ~3.4x faster (248s -> 72s)
```

`collect` fires forge ~200 times, and each fresh forge re-establishes its fork over the
RPC (several sequential round-trips); anvil collapses those to localhost. Measured
**3.44x on the Euler collect** (identical data, zero flakes); `synthesize` gains only
~5% since it's dominated by the optimizer, not forge. The flag needs `anvil` on PATH
(ships with Foundry) and the chain's real endpoint to fork from (`ETH=<rpc>`, else
run.sh's default). Under Docker, the `foundry-cache` volume persists fetched fork state
across `--rm` runs, compounding the win.

## Worked examples

The **Euler Finance** exploit (March 2023) is the reference example for `effects` — its
self-liquidation zeroes several balances at once (`op = set`) and its `mint` inverts
parameter/approximation, none of which the default `transit` expresses. It runs
through the CLI like the others (`python3 flashsyn.py collect euler` then
`python3 flashsyn.py synthesize euler`); FlashSyn rediscovers the exploit —
`eulerDeposit → eulerMint → eulerDonate → eulerLiquidateWithdraw`, **Best Profit 29,185,439**,
params `[199600000, 1479041079, 423197409]`. See
[`examples/euler/README.md`](examples/euler/README.md).

Two more worked examples use the streamlined CLI: the **Harvest Finance** exploits
of Oct 2020 — the fUSDC leg ([`examples/harvest_usdt/`](examples/harvest_usdt/README.md),
block 11129474) and the fUSDT leg ([`examples/harvest_usdc/`](examples/harvest_usdc/README.md),
block 11129500). Both are Curve-price-manipulation → vault-mispricing attacks with
four actions each. Run with `python3 flashsyn.py collect harvest_usdt` then
`python3 flashsyn.py synthesize harvest_usdt` (likewise `harvest_usdc`) — no file
copying. Both are verified end-to-end (FlashSyn rediscovers each exploit).

A **Damn Vulnerable DeFi** example lives in [`examples/puppet/`](examples/puppet/README.md):
the "Puppet" challenge, whose lending pool prices DVT off a Uniswap V1 spot oracle. Unlike
the mainnet examples it **deploys the whole scenario locally in `setUp()`** (DVT + a Uniswap
V1 exchange via `deployCode` + the pool), so the fork block is arbitrary. Its `borrow` action records
its collateral inline (`collect.balanceChange("ETH", _dep / 1e18)`) with inverted `effects`, because
the ETH collateral is an approximated function of the manipulated price, not the search parameter —
see the example's README. The two Uniswap V1 Vyper build artifacts it deploys
are vendored under `src/foundryModule/src/build-uniswap/v1/`. Run with
`python3 flashsyn.py collect puppet` then `python3 flashsyn.py synthesize puppet`.
Verified end-to-end (block 16818064): FlashSyn rediscovers the exploit — vector
`SwapUniswapDVT2ETH → PoolBorrow`, **Best Profit 89,000**, parameters `[999, 99999]`.

## Docker

A `Dockerfile` pins the whole environment (Foundry + the 2021-era Python stack), which is the
reliable way to run FlashSyn today. The image **builds natively on both `linux/amd64` and
`linux/arm64`** — the pinned 2021-era wheels (numpy 1.21, scipy 1.7, scikit-learn 1.0.2, …) all ship
cp39 wheels for both, so there is **no emulation** even on Apple Silicon.

```sh
# fast path: prebuilt current Foundry
docker build -t flashsyn .
docker run --rm -it -e ETH=<your-mainnet-archive-rpc> flashsyn

# or with compose (bind-mounts the repo so edits + logs persist on the host)
ETH=<your-mainnet-archive-rpc> docker compose run --rm flashsyn
```

Inside the container the workflow is unchanged — `./run.sh <contract> <chain> <block>`, then
`dependencyCheck.py`, etc. Pass your archive-node endpoint via `-e ETH=...` (or `BSC`/`Fantom`/
`Polygon`); `run.sh` reads them from the environment.

**Foundry fidelity.** FlashSyn's parsers have been modernised to consume **`forge test --json`**
(data collectors) and the plain decoded **`-vvvv` trace** (`dependencyCheck.py`), so the **default,
latest forge just works** — no version pin needed. The old code scraped ANSI-coloured `-vvv` text,
which a piped modern forge no longer emits; that is fixed. A `pinned-source` build arg exists to
compile the 2023 commit `5be158b` from source, but it is **obsolete and currently broken** — kept only
for the historical note below:

> **Known broken (verified 2026-07).** The source build at `5be158b` fails: a build dependency
> (`svm-rs-builds`) code-generates solc-version constants from the current release list and now
> collides on solc versions released after 2023 (`E0428: SOLC_VERSION_0_8_35 defined twice`).
> `foundryup -C <commit>` also no longer offers prebuilt-by-commit binaries. The exact 2023 forge
> can't be reproduced today — which is why the parsers were modernised instead.

**Verification status.** Run end-to-end through the CLI against the Euler example on native arm64 with
the modern stack (Python 3.12, numpy 2.2 / scipy 1.15 / scikit-learn 1.6, vendored shgo; mainnet archive
fork at block 16818064, forge 1.7.1): `collect` → `synthesize` and FlashSyn **rediscovers the exploit** —
sequence `deposit → mint → donate → liquidateWithdraw`, **Best Profit 29,185,439** with parameters
`[199600000, 1479041079, 423197409]`. (This is a higher-profit parameterization than the historical
~$22.4M frozen-stack reference; the modern optimizer settles on a different optimum given the data the
CLI collects. shgo itself is deterministic per data set — this is why the vendored copy is pinned: with
stock modern scipy shgo the same run yields `0 executions succeed` and never converges.)

> Note: run FlashSyn commands from the **repo root** — `settings.toml` is loaded via a path relative
> to the working directory.

## Prerequisites & known gaps

- **Foundry** — any current forge works; parsers consume `--json` / `-vvvv` (tested on 1.7.1). The
  original 2023 pin is no longer required.
- **Python** — 3.12 with a modern, pinned stack (numpy 2.2, scipy 1.15, scikit-learn 1.6, pandas 2.3,
  web3 7); `requirements.txt` holds the top-level pins and `requirements.lock` the full transitive lock.
- **Optimizer (shgo)** — scipy rewrote `shgo`'s sampling/simplicial internals after 1.7.x, which changes
  the optima it returns in ≥4 dimensions and stops FlashSyn's candidates from validating on-chain. So
  `src/vendored_shgo/` carries a self-contained copy of scipy 1.7.3's shgo, and the engine imports that
  instead of `scipy.optimize.shgo`. This keeps results reproducible on the modern stack (verified: the
  Euler example rediscovers the self-liquidation exploit end-to-end via the CLI). Do not swap it back to
  the stock scipy shgo without re-verifying the Euler result.
- **RPC** — `settings.toml` / `run.sh` carry shared, rented archive-node endpoints that may be closed;
  supply your own.
- **Runtime** — a full Euler synthesis was ~10–12 min under the old amd64-emulation image (Apple
  Silicon); the native arm64 image should be faster. Early synthesis rounds print `0 executions
  succeed` / `Best Profit 0.2` — that is
  the pre-refinement Strength-0 phase, **not** a failure; let the counter-example loop run to the end.

## Provenance

Extracted from Quantstamp's `flashsyn-euler` (the proceduralized "Pro" line) — engine + templates only;
the Euler-specific action file, the filled-in `attack.t.sol`, compiled artifacts, and logs were left
behind. `research-flashsyn` holds ~17 additional worked benchmarks usable as a regression suite.
Licensed Apache 2.0, per the upstream project.
