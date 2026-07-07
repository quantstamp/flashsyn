# syntax=docker/dockerfile:1
#
# FlashSyn reusable template — reproducible environment.
#
# Pinned to linux/amd64 on purpose: the 2021-era Python deps (numpy 1.21, scipy 1.7,
# scikit-learn 1.0.2, pykdtree) ship prebuilt wheels for amd64 but rarely for arm64.
# On Apple Silicon this image runs under emulation (slower, but it builds and works).
#
# Foundry install mode is selectable:
#   FOUNDRY_INSTALL=latest         (default) prebuilt current forge via foundryup — fast, always builds.
#   FOUNDRY_INSTALL=pinned-source  builds forge from the upstream-pinned commit for output-format
#                                  fidelity (FlashSyn's Python parsers were written against it).
# Build examples are in README.md ("Docker").

ARG FOUNDRY_INSTALL=latest
ARG FOUNDRY_COMMIT=5be158b
ARG RUST_VERSION=1.72.0

# ---------- Foundry: prebuilt latest ----------
FROM --platform=linux/amd64 debian:bullseye-slim AS foundry-latest
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl git ca-certificates && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.foundry/bin:${PATH}"
RUN curl -L https://foundry.paradigm.xyz | bash && foundryup
RUN mkdir -p /out && cp /root/.foundry/bin/forge /out/ \
      && cp /root/.foundry/bin/cast /out/ 2>/dev/null || true \
      && cp /root/.foundry/bin/anvil /out/ 2>/dev/null || true

# ---------- Foundry: pinned commit, built from source ----------
FROM --platform=linux/amd64 rust:${RUST_VERSION}-slim-bullseye AS foundry-pinned-source
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
FROM --platform=linux/amd64 python:3.9-slim-bullseye AS deps
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
