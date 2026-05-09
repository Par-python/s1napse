# Vendored: pyRfactor2SharedMemory

Source: https://github.com/TonyWhitley/pyRfactor2SharedMemory
Upstream commit: `32261e05d4103104d0da8fa0dffcebd441d2cef9`
License: MIT (see `License.txt`)

This library is not published on PyPI and has no `setup.py`/`pyproject.toml`,
so we vendor the two source modules directly. Update by replacing
`sharedMemoryAPI.py` and `rF2data.py` from a fresh upstream checkout.

Used by `s1napse/readers/lmu.py` to read Le Mans Ultimate telemetry via
the rFactor 2 Shared Memory Plugin.
