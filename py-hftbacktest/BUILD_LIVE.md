# Building HftBacktest with Live Trading Support

This guide explains how to build and install HftBacktest with live trading features.

## Overview

The `live` feature enables real-time trading functionality through:
- Zero-copy IPC via Iceoryx2 for market data streaming
- Connector binaries for exchange integration (Binance Futures/Spot, Bybit)
- High-level Python client wrapping low-level FFI bindings
- Asyncio-friendly event queues for market data consumption
- Thread-safe order management and position tracking

## System Requirements

### Operating Systems
- **Linux**: Kernel 4.19 or later (required for Iceoryx2)
- **macOS**: 10.15 (Catalina) or later
- **Windows**: Not currently supported

### Dependencies
- Python 3.11 or later
- Rust toolchain (for building from source)
- Maturin 1.7+
- Iceoryx2 system libraries (installed automatically by Cargo)

## Building Steps

### 1. Install Maturin

```bash
pip install maturin~=1.7
```

### 2. Build the Python Extension with Live Feature

#### Development Build (for local testing)

```bash
cd py-hftbacktest
maturin develop --features live
```

This installs the package in development mode in your current Python environment.

#### Production Build (for distribution)

```bash
cd py-hftbacktest
maturin build --release --features live
```

The wheel will be created in `target/wheels/`. Install it with:

```bash
pip install target/wheels/hftbacktest-*.whl
```

### 3. Build the Connector Binary

The connector binary is required to stream market data from exchanges.

```bash
# For Binance Futures
cargo build --release --manifest-path connector/Cargo.toml --features binancefutures

# For Binance Spot
cargo build --release --manifest-path connector/Cargo.toml --features binancespot

# For Bybit
cargo build --release --manifest-path connector/Cargo.toml --features bybit
```

The binary will be at `target/release/connector`.

## Verification

### 1. Check Python Import

```python
python3 -c "from hftbacktest import LiveInstrument, HashMapMarketDepthLiveBot; print('Live features available')"
```

If this succeeds, the live bindings are installed correctly.

### 2. Check Live Client

```python
python3 -c "from hftbacktest.live import LiveClient; print('Live client available')"
```

### 3. Run Tests

```bash
cd py-hftbacktest
python3 -m unittest tests.test_live_client -v
```

Note: Tests will be skipped if the live feature is not built.

## Configuration

### Connector Configuration

Create a TOML configuration file for the connector:

```toml
# config.toml
[general]
symbols = ["BTCUSDT"]

[binancefutures]
api_key = "your_api_key"
secret_key = "your_secret_key"
testnet = true

[depth]
snapshot_only = false
```

### Starting the Connector

Before running your Python bot, start the connector:

```bash
./target/release/connector binancefutures BTCUSDT config.toml
```

The connector will:
1. Connect to the exchange WebSocket
2. Set up Iceoryx2 shared memory publisher
3. Stream market data (trades, book updates, snapshots)

### Running Your Bot

Once the connector is running:

```python
from hftbacktest import LiveInstrument, HashMapMarketDepthLiveBot
from hftbacktest.live import LiveClient, Side

# Configure instrument (name must match connector)
instrument = LiveInstrument("BTCUSDT")
instrument.tick_size(0.01)
instrument.lot_size(0.001)

# Create bot
bot = HashMapMarketDepthLiveBot([instrument])

# Use high-level client
with LiveClient(bot) as client:
    # Your trading logic here
    pass
```

## Troubleshooting

### "Live features not available" Error

**Cause**: The package was built without the `live` feature.

**Solution**: Rebuild with `maturin develop --features live`

### "Service not found" or IPC Errors

**Cause**: Connector not running or wrong instrument name.

**Solution**: 
1. Start the connector first
2. Ensure instrument names match exactly between connector and Python code
3. Check that only one connector instance is running per instrument

### Iceoryx2 Build Errors

**Cause**: Missing system dependencies or incompatible kernel.

**Solution**:
- Linux: Ensure kernel 4.19+
- macOS: Ensure macOS 10.15+
- Check Rust toolchain is up to date: `rustup update`

### Permission Errors

**Cause**: Shared memory permissions issues.

**Solution**: On Linux, you may need to adjust `/dev/shm` permissions or run with appropriate user privileges.

## Building for Different Platforms

### Linux (x86_64)

```bash
maturin build --release --features live --target x86_64-unknown-linux-gnu
```

### macOS (ARM64 / Apple Silicon)

```bash
maturin build --release --features live --target aarch64-apple-darwin
```

### macOS (Intel)

```bash
maturin build --release --features live --target x86_64-apple-darwin
```

## Cross-Compilation

Cross-compilation of the live feature is complex due to Iceoryx2 dependencies. Build natively on the target platform when possible.

## Docker

When building in Docker, ensure:
1. Sufficient shared memory: `--shm-size=2g`
2. Modern kernel (4.19+) on host
3. Appropriate user permissions for `/dev/shm`

Example Dockerfile:

```dockerfile
FROM rust:1.75 as builder

RUN pip install maturin~=1.7

WORKDIR /app
COPY . .

RUN cd py-hftbacktest && maturin build --release --features live

FROM python:3.11-slim

COPY --from=builder /app/target/wheels/*.whl /tmp/
RUN pip install /tmp/*.whl

CMD ["python3", "your_bot.py"]
```

Run with:
```bash
docker run --shm-size=2g your-image
```

## Performance Considerations

- The live feature adds minimal overhead due to zero-copy shared memory
- Feed latency is typically <100μs from connector to Python
- Order submission latency depends on exchange API and network
- Use `ROIVectorMarketDepthLiveBot` for lower memory usage with sparse books
- Use `HashMapMarketDepthLiveBot` for faster random price level access

## Connector Runner (Automated Management)

For automated management of the connector binary lifecycle, use the `ConnectorRunner` utility:

```python
from pathlib import Path
from hftbacktest.live import ConnectorRunner, ConnectorConfig

# Configure the connector
config = ConnectorConfig(
    connector_name="binancefutures",
    connector_type="binancefutures",
    config_path=Path("connector/examples/binancefutures.toml")
)

# Use as context manager (automatically builds, starts, and stops)
with ConnectorRunner(config) as runner:
    # Connector is now running and ready
    # Your bot code here
    pass
# Connector is automatically stopped
```

### ConnectorRunner Features

- **Auto-build**: Builds the connector binary if missing
- **Lifecycle management**: Handles start, stop, and graceful shutdown
- **Health checks**: Verifies Iceoryx channels are available before proceeding
- **Error handling**: Provides detailed error messages for startup failures
- **Log capture**: Optionally captures stdout/stderr for debugging
- **Signal handling**: Properly handles SIGTERM/SIGINT for clean shutdown

### Manual Control

```python
from pathlib import Path
from hftbacktest.live import ConnectorRunner, ConnectorConfig

config = ConnectorConfig(
    connector_name="binancefutures",
    connector_type="binancefutures",
    config_path=Path("config.toml"),
    auto_build=True,
    startup_timeout=10.0,
    shutdown_timeout=5.0
)

runner = ConnectorRunner(config)

# Build if necessary
runner.build_if_missing()

# Start the connector
runner.start()

# Wait for it to be ready
if runner.wait_for_ready():
    print("Connector is ready!")
    # Your trading logic here
else:
    print("Connector failed to start")

# Stop when done
runner.stop()
```

### Configuration Options

```python
config = ConnectorConfig(
    connector_name="binancefutures",      # Unique name (for Iceoryx channels)
    connector_type="binancefutures",      # Type: binancefutures/binancespot/bybit
    config_path=Path("config.toml"),      # Path to TOML config
    project_root=Path("/path/to/repo"),   # Optional: auto-detected
    binary_path=Path("connector"),        # Optional: defaults to target/release/connector
    build_features=["binancefutures"],    # Optional: Cargo features
    startup_timeout=10.0,                 # Max seconds to wait for startup
    shutdown_timeout=5.0,                 # Max seconds to wait for shutdown
    env={"RUST_LOG": "info"},            # Additional environment variables
    auto_build=True,                      # Build if binary missing
    capture_output=True                   # Capture logs
)
```

### Error Handling

```python
from hftbacktest.live import (
    ConnectorRunner,
    ConnectorConfig,
    ConnectorBuildError,
    ConnectorStartupError,
    ConnectorNotFoundError
)

try:
    with ConnectorRunner(config) as runner:
        # Trading logic
        pass
except ConnectorBuildError as e:
    print(f"Build failed: {e}")
except ConnectorStartupError as e:
    print(f"Startup failed: {e}")
except ConnectorNotFoundError as e:
    print(f"Binary not found: {e}")
```

## See Also

- [Live Client README](hftbacktest/live/README.md) - High-level client usage
- [Example Code](hftbacktest/live/example.py) - Complete examples
- [Test Suite](tests/test_live_client.py) - Unit tests
- [Connector Runner Tests](tests/test_connector_runner.py) - Connector runner tests
