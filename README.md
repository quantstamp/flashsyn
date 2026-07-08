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
```

## What you author

1. **A Foundry test** — copy `src/foundryModule/src/test/template.t.sol` to `attack.t.sol`, fill in
   the interfaces, `setUp()`, and one `testExample()` per action. Forks the chain at the exploit block.
2. **A Python action model** — copy `src/FlashSynProActions/template.py`, fill the numbered TODOs:
   initial balances, token prices, and one subclass per protocol action (`actionStr`, `collectorStr`,
   `tokensIn/Out`, `range`, `transit`).

## Run procedure

```sh
# 0. prerequisites: Foundry (see note below) + Python deps
python3 -m pip install -r requirements.txt

# 1. compile the Foundry script
cd src/foundryModule && ./run.sh <contract> <ETH|BSC|Fantom|Polygon> <fork-block>

# 2. compute action dependencies (paste the graph into your action model's main())
python3 src/dependencyCheck.py "./run.sh <contract> <chain> <fork-block> -vvv"

# 3. collect initial data points
python3 <your-action-model>.py

# 4. run the synthesis (comment out initialPass(), uncomment the Synthesizer block first)
python3 <your-action-model>.py > run.log
```

The tail of `run.log` prints the best profit and the winning action sequence + parameters.

## Running the Euler example

The example is kept off the default path so a fresh clone stays blank. To run it, place its two files
where the engine expects them:

```sh
cp examples/euler/EulerActions.py src/FlashSynProActions/
cp examples/euler/attack.t.sol    src/foundryModule/src/test/attack.t.sol
```

Then follow the run procedure with `./run.sh euler ETH 16818064`. See
[`examples/euler/README.md`](examples/euler/README.md).

## Docker

A `Dockerfile` pins the whole environment (Foundry + the 2021-era Python stack), which is the
reliable way to run FlashSyn today. The image targets **`linux/amd64`** on purpose — the old pinned
wheels exist for amd64 but not arm64 — so on Apple Silicon it runs under emulation (slower, but it
builds).

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

**Verification status.** Run end-to-end against the Euler example on an arm64 host (amd64 emulation,
mainnet archive fork at block 16818064, forge 1.7.1): compile → `dependencyCheck` → data collection
(all actions) → synthesis all pass, and FlashSyn **rediscovers the exploit** — sequence
`deposit → mint → donate → liquidateWithdraw`, ~$22.4M profit, with the polynomial estimate matching
the on-chain execution to the dollar.

> Note: run FlashSyn commands from the **repo root** — `settings.toml` is loaded via a path relative
> to the working directory.

## Prerequisites & known gaps

- **Foundry** — any current forge works; parsers consume `--json` / `-vvvv` (tested on 1.7.1). The
  original 2023 pin is no longer required.
- **Python** — `requirements.txt` targets the 3.7-era stack (numpy 1.21, scipy 1.7, …).
- **RPC** — `settings.toml` / `run.sh` carry shared, rented archive-node endpoints that may be closed;
  supply your own.
- **Runtime** — a full Euler synthesis is ~10–12 min under amd64 emulation (Apple Silicon); native
  amd64 is faster. Early synthesis rounds print `0 executions succeed` / `Best Profit 0.2` — that is
  the pre-refinement Strength-0 phase, **not** a failure; let the counter-example loop run to the end.

## Provenance

Extracted from Quantstamp's `flashsyn-euler` (the proceduralized "Pro" line) — engine + templates only;
the Euler-specific action file, the filled-in `attack.t.sol`, compiled artifacts, and logs were left
behind. `research-flashsyn` holds ~17 additional worked benchmarks usable as a regression suite.
Licensed Apache 2.0, per the upstream project.
