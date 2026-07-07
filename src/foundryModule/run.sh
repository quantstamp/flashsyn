#!/bin/sh
# Archive-node RPC endpoints. Replace with your own — these are shared/rented and may be closed.
# You can also override any of them from the environment, e.g. `ETH=https://... ./run.sh ...`.
ETH="${ETH:-https://eth-mainnet.example.com/v2/YOUR_ALCHEMY_KEY}"
BSC="${BSC:-https://YOUR_BSC_RPC_ENDPOINT}"
Fantom="${Fantom:-https://YOUR_FANTOM_RPC_ENDPOINT}"
Polygon="${Polygon:-https://polygon-mainnet.example.com/v2/YOUR_ALCHEMY_KEY}"

# Usage: ./run.sh <contract> <chain> <fork-block> [extra forge args...]
#   <contract>   name of the test contract (matches --match-contract)
#   <chain>      ETH | BSC | Fantom | Polygon
#   <fork-block> block number to fork at (just before the exploit)
# Example (Euler): ./run.sh euler ETH 16818064
CONTRACT="$1"; CHAIN="$2"; BLOCK="$3"
[ $# -ge 3 ] && shift 3
eval RPC=\$$CHAIN

if [ -z "$CONTRACT" ] || [ -z "$RPC" ] || [ -z "$BLOCK" ]; then
   echo "Usage: ./run.sh <contract> <ETH|BSC|Fantom|Polygon> <fork-block> [forge args]"
   exit 1
fi

forge test --match-contract "$CONTRACT" --fork-url "$RPC" --fork-block-number "$BLOCK" "$@"
