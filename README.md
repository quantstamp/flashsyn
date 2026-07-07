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

## Prerequisites & known gaps

- **Foundry** — the original was pinned to a 2023 build (`foundryup -C 5be158b`). The Python side
  scrapes forge's exact log/color output, so a modern forge may break `dependencyCheck.py` and the
  data collectors. Resolving this pin is part of bringing the tool current.
- **Python** — `requirements.txt` targets the 3.7-era stack (numpy 1.21, scipy 1.7, …).
- **RPC** — `settings.toml` / `run.sh` carry shared, rented archive-node endpoints that may be closed;
  supply your own.
- **Not yet run end-to-end** in this environment. The extraction is verified structurally, not by
  execution.

## Provenance

Extracted from Quantstamp's `flashsyn-euler` (the proceduralized "Pro" line) — engine + templates only;
the Euler-specific action file, the filled-in `attack.t.sol`, compiled artifacts, and logs were left
behind. `research-flashsyn` holds ~17 additional worked benchmarks usable as a regression suite.
Licensed Apache 2.0, per the upstream project.
