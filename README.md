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
  euler/                                       # worked example (opt-in, not on the default path)
  harvest_usdt/                                # worked example — Harvest Finance fUSDC leg (2020)
  harvest_usdc/                                # worked example — Harvest Finance fUSDT leg (2020)
```

## What you author

1. **A Foundry test** — copy `src/foundryModule/src/test/template.t.sol` to `attack.t.sol`, fill in
   the interfaces, `setUp()`, and one `testExample()` per action. Forks the chain at the exploit block.
2. **A Python action model** — copy `src/FlashSynProActions/template.py`, fill the numbered TODOs:
   initial balances, token prices, a `tokenInfo` map (token → Solidity variable + decimals), and one
   subclass per protocol action (`actionStr`, `tokensIn/Out`, `range`). The data collector and the
   balance `transit()` are derived automatically from `tokensIn/Out` + `tokenInfo`; only write your
   own `collectorStr`/`transit` for an exotic action whose output isn't a simple balance delta.

## Run procedure

An example that lives under `examples/<name>/` (with a `flashsyn_setup()` in its
action model) runs through the CLI — no copying files, no editing source to switch
between collection and synthesis:

```sh
python3 -m pip install -r requirements.txt   # prerequisites: Foundry + Python deps

python3 flashsyn.py compile    <name>        # compile the harness against the fork
python3 flashsyn.py deps       <name>        # (optional) action dependency graph
python3 flashsyn.py collect    <name>        # collect initial data points
python3 flashsyn.py synthesize <name> > run.log
```

The tail of `run.log` prints the best profit and the winning action sequence +
parameters. (The older Euler example predates the CLI; run it with the manual
steps below.)

## Running the Euler example

The example is kept off the default path so a fresh clone stays blank. To run it, place its two files
where the engine expects them:

```sh
cp examples/euler/EulerActions.py src/FlashSynProActions/
cp examples/euler/attack.t.sol    src/foundryModule/src/test/attack.t.sol
```

Then follow the run procedure with `./run.sh euler ETH 16818064`. See
[`examples/euler/README.md`](examples/euler/README.md).

Two more worked examples use the streamlined CLI: the **Harvest Finance** exploits
of Oct 2020 — the fUSDC leg ([`examples/harvest_usdt/`](examples/harvest_usdt/README.md),
block 11129474) and the fUSDT leg ([`examples/harvest_usdc/`](examples/harvest_usdc/README.md),
block 11129500). Both are Curve-price-manipulation → vault-mispricing attacks with
four actions each. Run with `python3 flashsyn.py collect harvest_usdt` then
`python3 flashsyn.py synthesize harvest_usdt` (likewise `harvest_usdc`) — no file
copying. Both are verified end-to-end (FlashSyn rediscovers each exploit).

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

**Verification status.** Run end-to-end against the Euler example on native arm64 with the modern
stack (Python 3.12, numpy 2.2 / scipy 1.15 / scikit-learn 1.6, vendored shgo; mainnet archive fork
at block 16818064, forge 1.7.1): compile → synthesis passes and FlashSyn **rediscovers the exploit** —
sequence `deposit → mint → donate → liquidateWithdraw`, **Best Profit 22,415,805** with parameters
`[100585937, 1501953125, 908203125]`, byte-identical to the frozen-stack (scipy 1.7.3) reference run.
This equivalence is what pins the vendored shgo: with stock modern scipy shgo the same run yields
`0 executions succeed` and never converges.

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
  Euler example rediscovers the exact ~$22.4M exploit, identical to the frozen-stack reference). Do not
  swap it back to the stock scipy shgo without re-verifying the Euler result.
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
