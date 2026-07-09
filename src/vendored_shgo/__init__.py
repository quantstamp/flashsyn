# Self-contained vendor of scipy 1.7.3's shgo optimizer.
#
# Why this exists: scipy rewrote shgo's simplicial/sampling internals after 1.7.x
# (the `_shgo_lib` refactor). On modern scipy (>=1.9) the stock `scipy.optimize.shgo`
# returns DIFFERENT optima for the same objective in >=4 dimensions, which makes
# FlashSyn emit candidate parameters that no longer validate on-chain (verified:
# frozen scipy 1.7.3 rediscovers the Euler ~$22.4M exploit; modern stock shgo does
# not). Freezing the optimizer here decouples FlashSyn's results from the installed
# scipy version while keeping the rest of the stack modern.
#
# Sourced verbatim from scipy 1.7.3 (`optimize/_shgo.py` + `_shgo_lib/triangulation.py`);
# the only edit is the triangulation import, made relative. Sobol sampling still comes
# from the installed `scipy.stats.qmc`, which produces byte-identical unscrambled
# sequences across 1.7.3 and 1.13 (verified), so behavior is reproduced exactly.
from ._shgo import shgo

__all__ = ['shgo']
