# Python Live Connector Example

This example demonstrates how to use the HftBacktest LiveClient wrapper to subscribe to connector feeds and collect market statistics.

## Quick Start

### Running with Stub (No Real Connector Required)

The easiest way to see the example in action is to use the built-in `StubConnectorBot` which generates synthetic market data:

```bash
python examples/python_live_connector.py --stub --duration 5
```

This will:
1. Create a stub connector bot
2. Subscribe to trades and depth updates
3. Collect market statistics
4. Print a summary after 5 seconds

### Running with a Real Connector

To connect to a live exchange:

1. **Build the connector binary:**
   ```bash
   cargo build --release --manifest-path connector/Cargo.toml --features binancefutures
   ```

2. **Build the Python wheel with live feature:**
   ```bash
   maturin develop --manifest-path py-hftbacktest/Cargo.toml --features live
   ```

3. **Create a configuration file** (e.g., `binancefutures.toml`):
   ```toml
   stream_url = "wss://fstream.binancefuture.com/ws"
   api_url = "https://testnet.binancefuture.com"
   order_prefix = "test"
   api_key = "your_api_key"
   secret = "your_secret"
   ```

4. **Start the connector:**
   ```bash
   ./target/release/connector binancefutures BTCUSDT binancefutures.toml
   ```

5. **Run the example** (without `--stub` flag):
   ```bash
   python examples/python_live_connector.py --duration 30
   ```

## Command-Line Options

```
usage: python_live_connector.py [-h] [--stub] [--duration DURATION]

HftBacktest Live Connector Example

options:
  -h, --help            show this help message and exit
  --stub                Use stub connector for testing (default: connect to real connector)
  --duration DURATION   Duration to run in seconds (default: 10)
```

## What the Example Shows

### 1. Market Data Collection
The example demonstrates how to:
- Create a LiveClient connected to a bot
- Subscribe to trades with `get_trade_nowait()`
- Subscribe to depth updates with `get_book_update_nowait()`

### 2. Statistics Aggregation
The `MarketStatistics` class tracks:
- Total number of trades
- Buy/sell volume
- Last bid/ask prices and spread
- Depth update count
- Trades per second

### 3. Context Manager Pattern
Shows proper resource cleanup using Python's context manager pattern:
```python
with LiveClient(bot) as client:
    # Use client
    trade = client.get_trade_nowait()
```

### 4. Graceful Shutdown
Demonstrates how to:
- Stop polling when duration expires
- Handle Ctrl+C interrupts
- Close the client connection cleanly

## Code Structure

### Main Components

**MarketStatistics Class:**
- Dataclass that aggregates market statistics
- Calculates derived values like total_volume
- Provides formatted string representation

**Example Functions:**

- `get_stub_bot()` - Creates a stub bot for testing
- `get_real_bot()` - Creates a real bot connected to a connector
- `run_connector_example()` - Main example logic
- `main()` - Entry point with CLI argument parsing

## Integration with Your Strategy

You can use this example as a template for your own strategy:

```python
from hftbacktest.live import LiveClient, StubConnectorBot

# Create your bot (stub or real)
bot = StubConnectorBot()

with LiveClient(bot) as client:
    while your_condition:
        # Collect market data
        trade = client.get_trade_nowait()
        if trade:
            # Your strategy logic
            your_signal = calculate_signal(trade)
        
        # Execute orders if needed
        if your_signal:
            response = client.submit_order(
                side=Side.BUY,
                price=trade.price,
                qty=0.1
            )
```

## StubConnectorBot Features

The `StubConnectorBot` is a lightweight mock that:

- **Generates realistic synthetic data** with configurable volatility
- **Simulates latencies** (feed latency ~100μs, order latency ~1ms)
- **Maintains order state** - accepts, tracks, and fills orders
- **Is deterministic** - supports seed-based reproducibility for tests
- **Works everywhere** - no Iceoryx2 IPC required

Example with seed for reproducibility:

```python
from hftbacktest.live import StubConnectorBot

bot = StubConnectorBot(base_price=50000.0, seed=42)
# Same bot behavior every run with seed=42
```

## Testing Your Strategy

The example includes comprehensive tests in `py-hftbacktest/tests/test_python_live_connector_example.py`:

```bash
python -m pytest py-hftbacktest/tests/test_python_live_connector_example.py -v
```

Or run with unittest:

```bash
python -m unittest tests.test_python_live_connector_example -v
```

Test coverage includes:
- Stub bot creation and feed generation
- Trade and depth data generation
- Order submission and cancellation
- LiveClient integration with stub
- MarketStatistics functionality
- Full example execution with stub

## Output Example

Running `python examples/python_live_connector.py --stub --duration 5`:

```
HftBacktest Live Connector Example
============================================================
Using STUB connector (no real connector required)

✓ LiveClient connected
  Timestamp: 1699372800000000000
  Assets: 1

Collecting market data... Press Ctrl+C to stop
============================================================

[2.0s] Live market data:
  Trades: 45
  Volume: 12.3456
  Bid: 50000.50 Ask: 50001.20

[4.0s] Live market data:
  Trades: 92
  Volume: 25.6789
  Bid: 50000.40 Ask: 50001.30

============================================================
Market Statistics
============================================================
Total Trades:        105
Total Volume:        28.5000
  Buy Volume:        18.2000
  Sell Volume:       10.3000
Trades/Second:       21.00
Last Bid:            50000.40
Last Ask:            50001.30
Current Spread:      0.9000
Max Spread:          2.0000
Min Spread:          0.5000
Depth Updates:       250
============================================================
Example completed successfully (duration: 5.0s)
```

## Troubleshooting

### "Live features not available" error
Make sure to build with the `live` feature:
```bash
maturin develop --manifest-path py-hftbacktest/Cargo.toml --features live
```

### Stub bot generates no data
This is normal - the stub generates data probabilistically. Run for longer or check that you're calling `get_trade_nowait()` etc. in your loop.

### Connection timeout with real connector
1. Verify connector is running: `./target/release/connector binancefutures BTCUSDT config.toml`
2. Check configuration file is correct
3. Verify Iceoryx2 system dependencies are installed
4. Check system requirements: Linux 4.19+ or macOS 10.15+

## Related Files

- **Example Script:** `examples/python_live_connector.py`
- **Stub Module:** `py-hftbacktest/hftbacktest/live/stub.py`
- **Tests:** `py-hftbacktest/tests/test_python_live_connector_example.py`
- **LiveClient API:** `py-hftbacktest/hftbacktest/live/client.py`
- **Documentation:** `docs/python_live_connector_example.rst`
- **Setup Guide:** `docs/python_connector_setup.md`

## Further Reading

- [LiveClient API Reference](../py-hftbacktest/hftbacktest/live/README.md)
- [Python Connector Setup Guide](../docs/python_connector_setup.md)
- [Complex Market Making Example](live_trading_example.py)
- [Build Documentation](../py-hftbacktest/BUILD_LIVE.md)
