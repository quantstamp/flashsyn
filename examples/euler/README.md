# Euler example

The [Euler Finance](https://phalcon.xyz/tx/eth/0x465a6780145f1efe3ab52f94c006065575712d2003d83d85481f3d110ed131d9)
exploit (March 2023), as a worked FlashSyn analysis. This is the reference for filling in the templates
in `src/`.

- `EulerActions.py` — the filled-in Python action model (counterpart to `src/FlashSynProActions/template.py`).
- `attack.t.sol` — the filled-in Foundry harness (counterpart to `src/foundryModule/src/test/template.t.sol`).

Chain: Ethereum mainnet, fork block **16818064**. Initial capital: 400,000,000 USDC.

## Run it

From the repo root, place the two files where the engine expects them, then follow the standard flow:

```sh
cp examples/euler/EulerActions.py src/FlashSynProActions/
cp examples/euler/attack.t.sol    src/foundryModule/src/test/attack.t.sol

cd src/foundryModule && ./run.sh euler ETH 16818064          # 1. compile
cd ..                                                        # back to src/
python3 dependencyCheck.py "./run.sh euler ETH 16818064 -vvv"  # 2. dependencies
python3 FlashSynProActions/EulerActions.py                   # 3. collect data points
# 4. edit EulerActions.py: comment out initialPass(), uncomment the Synthesizer block
python3 FlashSynProActions/EulerActions.py > EulerLog.txt    # 5. synthesize
```

> Note: `EulerActions.py` already sets `config.command = "./run.sh euler ETH 16818064"` to match the
> generic runner. Create `initialDataPoints/euler/` before step 3 if it does not exist.
