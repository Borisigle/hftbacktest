# Connector Runner

Automated lifecycle management for the HftBacktest connector binary.

## Overview

The `ConnectorRunner` utility manages the complete lifecycle of the Rust connector binary that streams market data via Iceoryx2 IPC. It simplifies bot development by handling:

- **Building**: Automatically builds the connector binary if missing
- **Starting**: Launches the process with proper configuration
- **Health Checks**: Verifies Iceoryx channels are available before proceeding
- **Stopping**: Gracefully shuts down with proper signal handling (SIGTERM/SIGINT)
- **Error Handling**: Provides detailed error messages for debugging

## Quick Start

### Basic Usage

```python
from pathlib import Path
from hftbacktest.live import ConnectorRunner, ConnectorConfig

# Configure the connector
config = ConnectorConfig(
    connector_name="binancefutures",
    connector_type="binancefutures",
    config_path=Path("connector/examples/binancefutures.toml")
)

# Use as context manager (automatically starts and stops)
with ConnectorRunner(config) as runner:
    # Connector is running and ready
    # Create your bot and trading logic here
    pass
# Connector is automatically stopped
```

### Complete Example

```python
from pathlib import Path
from hftbacktest import LiveInstrument, HashMapMarketDepthLiveBot
from hftbacktest.live import (
    ConnectorRunner,
    ConnectorConfig,
    LiveClient,
    ConnectorBuildError,
    ConnectorStartupError
)

# Configure connector
config = ConnectorConfig(
    connector_name="binancefutures",
    connector_type="binancefutures",
    config_path=Path("config.toml"),
    auto_build=True,           # Build if binary missing
    startup_timeout=15.0,      # Wait up to 15s for startup
    capture_output=True,       # Capture logs for debugging
    env={"RUST_LOG": "info"}  # Set logging level
)

try:
    # Start connector
    with ConnectorRunner(config) as runner:
        # Create bot (name must match config.connector_name)
        instrument = (
            LiveInstrument()
            .connector("binancefutures")
            .symbol("BTCUSDT")
            .tick_size(0.1)
            .lot_size(0.001)
        )
        bot = HashMapMarketDepthLiveBot([instrument])
        
        # Use LiveClient
        with LiveClient(bot) as client:
            # Your trading logic
            trade = client.get_trade_nowait()
            if trade:
                print(f"Trade: {trade.price}")
        
except ConnectorBuildError as e:
    print(f"Build failed: {e}")
except ConnectorStartupError as e:
    print(f"Startup failed: {e}")
```

## Configuration

### ConnectorConfig Parameters

```python
ConnectorConfig(
    connector_name: str,              # Unique name (for Iceoryx channels)
    connector_type: str,              # "binancefutures", "binancespot", or "bybit"
    config_path: Path,                # Path to TOML config file
    
    # Optional parameters with defaults:
    project_root: Optional[Path] = None,         # Auto-detected
    binary_path: Optional[Path] = None,          # target/release/connector
    build_features: Optional[List[str]] = None,  # [connector_type]
    startup_timeout: float = 10.0,               # Seconds to wait for startup
    shutdown_timeout: float = 5.0,               # Seconds to wait for shutdown
    env: Dict[str, str] = {},                    # Additional env vars
    auto_build: bool = True,                     # Build if binary missing
    capture_output: bool = True                  # Capture stdout/stderr
)
```

### Connector Name

The `connector_name` is used to create the Iceoryx2 channel names. It **must match** the name you pass to `LiveInstrument.connector()` when building your bot:

```python
# Config
config = ConnectorConfig(
    connector_name="my_exchange",  # <-- This name
    ...
)

# Bot
instrument = LiveInstrument().connector("my_exchange")  # <-- Must match
```

### Connector Type

The `connector_type` determines which exchange connector to build and run:
- `"binancefutures"`: Binance USD-M Futures
- `"binancespot"`: Binance Spot
- `"bybit"`: Bybit Linear Futures

### Configuration File

The `config_path` points to a TOML file with exchange-specific settings:

```toml
# Example: binancefutures.toml
stream_url = "wss://fstream.binancefuture.com/ws"
api_url = "https://testnet.binancefuture.com"
order_prefix = "test"
api_key = "your_api_key"
secret = "your_secret"
```

See `connector/examples/` for more examples.

## Methods

### ConnectorRunner Methods

#### `__init__(config: ConnectorConfig)`
Initialize the runner with configuration.

```python
runner = ConnectorRunner(config)
```

#### `build(force: bool = False)`
Build the connector binary.

```python
runner.build()           # Build if missing
runner.build(force=True) # Rebuild even if exists
```

**Raises:**
- `ConnectorBuildError`: If build fails

#### `build_if_missing()`
Build the connector only if the binary doesn't exist.

```python
runner.build_if_missing()
```

**Raises:**
- `ConnectorNotFoundError`: If binary missing and `auto_build=False`
- `ConnectorBuildError`: If build fails

#### `start()`
Start the connector process.

```python
runner.start()
```

**Raises:**
- `ConnectorNotFoundError`: If binary doesn't exist
- `ConnectorStartupError`: If process dies immediately

#### `wait_for_ready(timeout: Optional[float] = None) -> bool`
Wait for the connector to be ready by checking Iceoryx channels.

```python
if runner.wait_for_ready(timeout=10.0):
    print("Connector is ready!")
else:
    print("Timeout waiting for connector")
```

**Returns:**
- `True` if ready
- `False` if timeout

**Raises:**
- `ConnectorStartupError`: If process dies while waiting

#### `stop(timeout: Optional[float] = None)`
Stop the connector process gracefully.

```python
runner.stop()           # Use config.shutdown_timeout
runner.stop(timeout=10) # Custom timeout
```

Tries SIGTERM first, then SIGKILL if timeout expires.

#### `is_running() -> bool`
Check if the connector process is running.

```python
if runner.is_running():
    print("Connector is running")
```

#### `binary_exists() -> bool`
Check if the connector binary exists.

```python
if runner.binary_exists():
    print("Binary found")
```

#### `get_output() -> tuple[str, str]`
Get captured stdout and stderr (only available if `capture_output=True`).

```python
stdout, stderr = runner.get_output()
print(f"Connector logs:\n{stdout}")
```

**Raises:**
- `ConnectorRunnerError`: If output capture not enabled or process still running

### Context Manager

The recommended way to use `ConnectorRunner` is as a context manager:

```python
with ConnectorRunner(config) as runner:
    # Connector is built (if needed), started, and ready
    # Your code here
    pass
# Connector is automatically stopped
```

This is equivalent to:
```python
runner = ConnectorRunner(config)
runner.build_if_missing()
runner.start()
runner.wait_for_ready()
try:
    # Your code here
    pass
finally:
    runner.stop()
```

## Error Handling

### Exception Hierarchy

```
ConnectorRunnerError (base)
├── ConnectorBuildError
├── ConnectorStartupError
└── ConnectorNotFoundError
```

### Example Error Handling

```python
from hftbacktest.live import (
    ConnectorRunner,
    ConnectorConfig,
    ConnectorBuildError,
    ConnectorStartupError,
    ConnectorNotFoundError,
    ConnectorRunnerError
)

try:
    with ConnectorRunner(config) as runner:
        # Trading logic
        pass
        
except ConnectorBuildError as e:
    print(f"Build failed: {e}")
    # Cargo build error, check Rust toolchain
    
except ConnectorStartupError as e:
    print(f"Startup failed: {e}")
    # Process died immediately, check config file and logs
    
except ConnectorNotFoundError as e:
    print(f"Binary not found: {e}")
    # Set auto_build=True or build manually
    
except ConnectorRunnerError as e:
    print(f"General error: {e}")
    # Catch-all for other errors
```

## Advanced Usage

### Custom Binary Path

Specify a custom binary location:

```python
config = ConnectorConfig(
    connector_name="test",
    connector_type="binancefutures",
    config_path=Path("config.toml"),
    binary_path=Path("/custom/path/to/connector")
)
```

### Custom Build Features

Enable additional Cargo features:

```python
config = ConnectorConfig(
    connector_name="test",
    connector_type="binancefutures",
    config_path=Path("config.toml"),
    build_features=["binancefutures", "extra_feature"]
)
```

### Environment Variables

Pass environment variables to the connector:

```python
config = ConnectorConfig(
    connector_name="test",
    connector_type="binancefutures",
    config_path=Path("config.toml"),
    env={
        "RUST_LOG": "debug",
        "CUSTOM_VAR": "value"
    }
)
```

### Project Root Detection

The runner auto-detects the project root by searching for `Cargo.toml` with `[workspace]`. You can override this:

```python
config = ConnectorConfig(
    connector_name="test",
    connector_type="binancefutures",
    config_path=Path("config.toml"),
    project_root=Path("/path/to/hftbacktest")
)
```

Or set the `HFTBACKTEST_ROOT` environment variable:

```bash
export HFTBACKTEST_ROOT=/path/to/hftbacktest
```

### Manual Lifecycle Control

For more control, use the runner without the context manager:

```python
runner = ConnectorRunner(config)

# Build
if not runner.binary_exists():
    print("Building connector...")
    runner.build()

# Start
print("Starting connector...")
runner.start()

# Wait for ready
print("Waiting for connector...")
if runner.wait_for_ready(timeout=15.0):
    print("Connector is ready!")
    
    # Check status
    if runner.is_running():
        print(f"PID: {runner.process.pid}")
    
    # Your trading logic here
    time.sleep(10)
    
else:
    print("Connector failed to start")

# Stop
print("Stopping connector...")
runner.stop()

# Get logs (if capture_output=True)
stdout, stderr = runner.get_output()
print(f"Connector output:\n{stdout}")
```

## Testing

### Running Tests

```bash
# Unit tests
python -m unittest py-hftbacktest/tests/test_connector_runner.py -v

# Or with pytest
pytest py-hftbacktest/tests/test_connector_runner.py -v
```

### Using in Tests

The `ConnectorRunner` works with mocked subprocesses for testing:

```python
import unittest
from unittest.mock import Mock, patch
from hftbacktest.live import ConnectorRunner, ConnectorConfig

class TestMyBot(unittest.TestCase):
    @patch('subprocess.Popen')
    def test_with_connector(self, mock_popen):
        # Mock process
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process
        
        config = ConnectorConfig(
            connector_name="test",
            connector_type="binancefutures",
            config_path=Path("config.toml"),
            auto_build=False  # Skip build in tests
        )
        
        with ConnectorRunner(config) as runner:
            # Test your bot logic
            pass
```

## Examples

See the complete example at `examples/connector_runner_example.py`:

```bash
python examples/connector_runner_example.py --help
python examples/connector_runner_example.py --duration 30
```

## Troubleshooting

### "Could not find project root"

**Cause:** Runner can't auto-detect the project root.

**Solution:**
- Run from within the project directory
- Set `HFTBACKTEST_ROOT` environment variable
- Pass `project_root` in config

### "Configuration file not found"

**Cause:** The config file path is incorrect.

**Solution:**
- Check the path exists: `ls -la connector/examples/binancefutures.toml`
- Use absolute paths or paths relative to current directory
- Config path is resolved relative to current working directory

### "Invalid connector type"

**Cause:** Invalid `connector_type` value.

**Solution:** Use one of: `binancefutures`, `binancespot`, `bybit`

### "Build failed"

**Cause:** Cargo build error.

**Solution:**
- Check Rust toolchain is installed: `cargo --version`
- Check build output for compilation errors
- Verify dependencies are available
- Try building manually: `cargo build --release --manifest-path connector/Cargo.toml --features binancefutures`

### "Connector process died immediately"

**Cause:** Connector crashed on startup.

**Solution:**
- Check config file syntax (must be valid TOML)
- Verify API keys and URLs in config
- Check connector logs (enable `capture_output=True`)
- Try running connector manually to see error messages

### "Timeout waiting for connector"

**Cause:** Iceoryx channels not available within timeout.

**Solution:**
- Increase `startup_timeout`
- Check connector is actually starting (enable logging)
- Verify no port/resource conflicts
- Check system requirements (Linux 4.19+ or macOS 10.15+)

### "cargo command not found"

**Cause:** Rust toolchain not installed or not in PATH.

**Solution:**
- Install Rust: https://rustup.rs/
- Verify installation: `cargo --version`
- Add to PATH: `export PATH="$HOME/.cargo/bin:$PATH"`

## Related Documentation

- [Live Client README](README.md) - High-level LiveClient API
- [BUILD_LIVE.md](../../BUILD_LIVE.md) - Building with live features
- [Connector Runner Example](../../../examples/connector_runner_example.py) - Complete example
- [Test Suite](../../tests/test_connector_runner.py) - Unit tests
