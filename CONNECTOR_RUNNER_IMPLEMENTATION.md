# Connector Runner Implementation Summary

This document summarizes the implementation of the `ConnectorRunner` utility for managing the lifecycle of the HftBacktest connector binary.

## Overview

The `ConnectorRunner` provides a high-level Python API for managing the Rust connector binary that streams market data via Iceoryx2 IPC. It automates:

1. Building the connector binary if missing
2. Starting the process with proper configuration
3. Health-checking Iceoryx channel availability
4. Gracefully stopping with signal handling
5. Error reporting and logging

## Files Created/Modified

### Core Implementation

- **`py-hftbacktest/hftbacktest/live/connector_runner.py`** (489 lines)
  - `ConnectorConfig` dataclass for configuration
  - `ConnectorRunner` class with full lifecycle management
  - Custom exceptions: `ConnectorRunnerError`, `ConnectorBuildError`, `ConnectorStartupError`, `ConnectorNotFoundError`
  - Context manager support
  - Auto-detection of project root
  - Health checks via Iceoryx channel availability

### Tests

- **`py-hftbacktest/tests/test_connector_runner.py`** (562 lines)
  - 22 test cases covering all functionality
  - Tests use mocked subprocesses (no actual binary required)
  - Coverage:
    - Configuration validation
    - Binary existence checks
    - Build process (success/failure)
    - Process startup (success/failure/immediate death)
    - Lifecycle management (start/stop/health checks)
    - Context manager usage
    - Error handling

### Examples

- **`examples/connector_runner_example.py`** (250 lines)
  - Complete working example demonstrating:
    - Automated connector management
    - Integration with LiveClient
    - Market data collection
    - CLI argument parsing
    - Error handling
    - Logging

### Documentation

- **`py-hftbacktest/hftbacktest/live/CONNECTOR_RUNNER.md`**
  - Complete API reference
  - Usage examples
  - Configuration options
  - Error handling guide
  - Troubleshooting section

- **Updated `py-hftbacktest/BUILD_LIVE.md`**
  - Added "Connector Runner (Automated Management)" section
  - Examples of usage
  - Configuration options
  - Error handling

- **Updated `py-hftbacktest/hftbacktest/live/README.md`**
  - Added "Connector Setup" section with automated option
  - Manual invocation instructions

- **Updated `examples/README_PYTHON_LIVE_CONNECTOR.md`**
  - Added automated connector management option
  - Reference to connector_runner_example.py

### Module Exports

- **Updated `py-hftbacktest/hftbacktest/live/__init__.py`**
  - Exports: `ConnectorRunner`, `ConnectorConfig`, `ConnectorRunnerError`, `ConnectorBuildError`, `ConnectorStartupError`, `ConnectorNotFoundError`
  - Works even without live feature enabled (graceful degradation)

## Key Features

### 1. Auto-Build

```python
config = ConnectorConfig(
    connector_name="binancefutures",
    connector_type="binancefutures",
    config_path=Path("config.toml"),
    auto_build=True  # Builds if binary missing
)
```

Runs: `cargo build --release --manifest-path connector/Cargo.toml --features binancefutures`

### 2. Health Checks

The `wait_for_ready()` method:
- Polls process status
- Attempts to create a minimal bot to verify Iceoryx channels exist
- Times out after `startup_timeout` seconds
- Raises detailed error if process dies

### 3. Graceful Shutdown

The `stop()` method:
- Sends SIGTERM for graceful shutdown
- Waits up to `shutdown_timeout` seconds
- Falls back to SIGKILL if needed
- Ensures process cleanup

### 4. Project Root Detection

Searches for workspace `Cargo.toml`:
1. Starts from connector_runner.py location
2. Walks up directory tree
3. Looks for `[workspace]` in Cargo.toml or `connector/Cargo.toml`
4. Falls back to `HFTBACKTEST_ROOT` environment variable

### 5. Configuration Validation

Validates at initialization:
- Config file exists
- Connector type is valid (binancefutures/binancespot/bybit)
- Paths are resolved correctly

### 6. Context Manager

Preferred usage pattern:
```python
with ConnectorRunner(config) as runner:
    # Automatically: build_if_missing() → start() → wait_for_ready()
    # Your trading logic here
    pass
# Automatically: stop()
```

## API Surface

### ConnectorConfig

```python
@dataclass
class ConnectorConfig:
    connector_name: str              # Required
    connector_type: str              # Required
    config_path: Path                # Required
    project_root: Optional[Path]     # Auto-detected
    binary_path: Optional[Path]      # Default: target/release/connector
    build_features: Optional[List]   # Default: [connector_type]
    startup_timeout: float           # Default: 10.0
    shutdown_timeout: float          # Default: 5.0
    env: Dict[str, str]             # Default: {}
    auto_build: bool                # Default: True
    capture_output: bool            # Default: True
```

### ConnectorRunner

**Methods:**
- `__init__(config: ConnectorConfig)` - Initialize
- `build(force: bool = False)` - Build connector
- `build_if_missing()` - Build only if needed
- `binary_exists() -> bool` - Check binary exists
- `start()` - Start connector process
- `wait_for_ready(timeout: Optional[float] = None) -> bool` - Wait for ready
- `is_running() -> bool` - Check if running
- `stop(timeout: Optional[float] = None)` - Stop connector
- `get_output() -> tuple[str, str]` - Get captured output
- `__enter__()` / `__exit__()` - Context manager support

**Properties:**
- `config: ConnectorConfig` - Configuration
- `process: Optional[subprocess.Popen]` - Process handle

**Exceptions:**
- `ConnectorRunnerError` - Base exception
- `ConnectorBuildError` - Build failures
- `ConnectorStartupError` - Startup failures
- `ConnectorNotFoundError` - Binary not found

## Design Decisions

### 1. Subprocess Management

- Uses `subprocess.Popen` for process control
- Captures stdout/stderr when `capture_output=True`
- Proper signal handling (SIGTERM → SIGKILL)
- Timeout-based waiting

### 2. Health Checking

Attempts to create a bot to verify channels:
```python
instrument = LiveInstrument().connector(name).symbol("_HEALTH_CHECK_")
bot = HashMapMarketDepthLiveBot([instrument])
```

If this succeeds, Iceoryx channels are available.

### 3. Error Hierarchy

Specific exceptions for different failure modes:
- Build errors (cargo failures)
- Startup errors (process crashes)
- Not found errors (missing binary)

### 4. Graceful Degradation

Works even without live feature:
- Import succeeds
- Classes available
- Warnings issued if live module unavailable

### 5. Path Resolution

- Absolute paths preferred
- Config path resolved relative to CWD
- Binary path defaults to workspace target/release
- Project root auto-detected or from env var

## Testing Strategy

Tests use mocked subprocesses to avoid dependencies:
- `@patch('subprocess.run')` for build
- `@patch('subprocess.Popen')` for start
- Mock process objects for lifecycle

Tests cover:
- Configuration validation (valid/invalid types, missing files)
- Binary existence checks
- Build success/failure/timeout
- Start success/immediate death/not found
- Stop graceful/forced kill
- Context manager
- Error types

## Integration Points

### With LiveClient

```python
with ConnectorRunner(config) as runner:
    bot = HashMapMarketDepthLiveBot([instrument])
    with LiveClient(bot) as client:
        # Trading logic
        pass
```

### With StubConnectorBot

No connector needed:
```python
from hftbacktest.live import StubConnectorBot, LiveClient

bot = StubConnectorBot()
with LiveClient(bot) as client:
    # Testing without connector
    pass
```

### With Manual Connector

Still works if user prefers manual control:
```bash
./target/release/connector binancefutures binancefutures config.toml &
```

## Usage Examples

### Minimal

```python
from pathlib import Path
from hftbacktest.live import ConnectorRunner, ConnectorConfig

config = ConnectorConfig(
    connector_name="binancefutures",
    connector_type="binancefutures",
    config_path=Path("config.toml")
)

with ConnectorRunner(config) as runner:
    # Your bot code
    pass
```

### With Custom Settings

```python
config = ConnectorConfig(
    connector_name="my_exchange",
    connector_type="bybit",
    config_path=Path("config.toml"),
    startup_timeout=20.0,
    env={"RUST_LOG": "debug"},
    auto_build=True
)

with ConnectorRunner(config) as runner:
    # Your bot code
    pass
```

### Manual Control

```python
runner = ConnectorRunner(config)
runner.build_if_missing()
runner.start()

if runner.wait_for_ready():
    # Your bot code
    pass

runner.stop()
stdout, stderr = runner.get_output()
print(f"Logs:\n{stdout}")
```

## Future Enhancements

Possible improvements:
1. Log streaming (tail -f style)
2. Multiple connector instances
3. Restart on failure
4. Metrics/monitoring hooks
5. Config file generation
6. Validator for TOML configs
7. Docker integration
8. Systemd service management

## Conclusion

The `ConnectorRunner` simplifies bot development by handling all connector lifecycle management automatically. It provides a clean, Pythonic API with proper error handling, logging, and resource cleanup.

Key benefits:
- **Zero manual setup** - Auto-builds and starts connector
- **Health checks** - Verifies Iceoryx channels before proceeding
- **Clean shutdown** - Handles signals properly
- **Testing support** - Works with mocked subprocesses
- **Well-documented** - Comprehensive API docs and examples
- **Production-ready** - Proper error handling and logging
