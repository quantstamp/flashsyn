# syntax=docker/dockerfile:1
#
# FlashSyn reusable template — reproducible environment.
#
# Builds natively on the host architecture (arm64 and amd64). Python 3.12 with a
# modern, pinned stack (numpy 2.2, scipy 1.15, scikit-learn 1.6, pandas 2.3, web3 7);
# all ship prebuilt cp312 wheels for both linux/amd64 and linux/arm64, so no emulation
# is needed — including on Apple Silicon. (The image was previously pinned to
# linux/amd64 only because of pykdtree, a dependency that was never actually imported;
# it has been dropped.)
#
# Foundry install mode is selectable:
#   FOUNDRY_INSTALL=latest         (default) prebuilt current forge via foundryup — fast, always builds.
#                                  This is the right choice: the Python parsers were modernised to
#                                  consume `forge test --json` / `-vvvv`, so a current forge works.
#   FOUNDRY_INSTALL=pinned-source  builds the 2023 commit from source. OBSOLETE and currently broken
#                                  (see the stage below); kept only as a historical reference.
# Build examples are in README.md ("Docker").

ARG FOUNDRY_INSTALL=latest
ARG FOUNDRY_COMMIT=5be158b
ARG RUST_VERSION=1.72.0

# ---------- Foundry: prebuilt latest ----------
# bookworm (glibc 2.36): current forge binaries require glibc >= ~2.34, so bullseye (2.31) fails.
FROM debian:bookworm-slim AS foundry-latest
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl git ca-certificates && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.foundry/bin:${PATH}"
RUN curl -L https://foundry.paradigm.xyz | bash && foundryup
RUN mkdir -p /out && cp /root/.foundry/bin/forge /out/ \
      && cp /root/.foundry/bin/cast /out/ 2>/dev/null || true \
      && cp /root/.foundry/bin/anvil /out/ 2>/dev/null || true

# ---------- Foundry: pinned commit, built from source ----------
# KNOWN BROKEN at commit 5be158b (verified 2026-07): a build dependency, svm-rs-builds,
# code-generates solc-version constants from the current release list and now collides on
# solc versions released after 2023 (E0428: SOLC_VERSION_0_8_35 defined twice). foundryup
# also no longer offers prebuilt-by-commit binaries. Getting the exact 2023 forge is not
# practical today; the real path is modernizing FlashSyn's forge-output parsers (forge --json).
FROM rust:${RUST_VERSION}-slim-bookworm AS foundry-pinned-source
ARG FOUNDRY_COMMIT
RUN apt-get update && apt-get install -y --no-install-recommends \
      git libssl-dev pkg-config ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/foundry-rs/foundry /src \
      && cd /src && git checkout ${FOUNDRY_COMMIT} \
      && cargo build --release --bins
RUN mkdir -p /out && cp /src/target/release/forge /out/ \
      && cp /src/target/release/cast /out/ 2>/dev/null || true \
      && cp /src/target/release/anvil /out/ 2>/dev/null || true

# select the mode chosen by FOUNDRY_INSTALL
FROM foundry-${FOUNDRY_INSTALL} AS foundry

# ---------- Python deps (isolated so it can be built/verified alone) ----------
FROM python:3.12-slim-bookworm AS deps
ENV DEBIAN_FRONTEND=noninteractive
# build-essential + gfortran + libgomp1 cover any dep that falls back to a source build (pykdtree/scipy).
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential gfortran libgomp1 git ca-certificates \
      && rm -rf /var/lib/apt/lists/*
WORKDIR /flashsyn
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Final image ----------
FROM deps AS runtime
COPY --from=foundry /out/ /usr/local/bin/
COPY . /flashsyn
# quick self-check that forge is on PATH at build time
RUN forge --version
WORKDIR /flashsyn
CMD ["/bin/bash"]
