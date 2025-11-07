# Live Trading Client

High-level Python wrapper for live trading with HftBacktest.

## Quick Links

- **Example:** See `examples/python_live_connector.py` for a complete working example
- **Testing without connector:** Use `StubConnectorBot` from `hftbacktest.live` for CI/CD and development
- **Full setup guide:** See `docs/python_connector_setup.md`

## Installation

The live feature requires building the extension with the `live` Rust feature enabled:

```bash
# Development build
maturin develop --manifest-path py-hftbacktest/Cargo.toml --features live

# Production build
maturin build --release --manifest-path py-hftbacktest/Cargo.toml --features live
pip install target/wheels/hftbacktest-*.whl
```

### System Requirements

The live feature depends on Iceoryx2 for zero-copy IPC:
- **Linux**: Kernel 4.19+ required
- **macOS**: 10.15+ (Catalina or later)
- **Windows**: Not currently supported

## Quick Start

```python
from hftbacktest import LiveInstrument, HashMapMarketDepthLiveBot
from hftbacktest.live import LiveClient, Side

# Configure the live instrument (connects via Iceoryx2)
instrument = LiveInstrument("BTCUSDT", tick_size=0.01, lot_size=0.001)

# Create the low-level bot
bot = HashMapMarketDepthLiveBot([instrument])

# Wrap with high-level client
with LiveClient(bot) as client:
    # Process market data
    while True:
        # Get latest trade
        trade = client.get_trade_nowait()
        if trade:
            print(f"Trade: {trade.price} @ {trade.qty} {trade.side}")
        
        # Get book update
        book = client.get_book_update_nowait()
        if book:
            print(f"Book: {book.bid_price} / {book.ask_price}")
        
        # Submit order
        response = client.submit_order(
            side=Side.BUY,
            price=50000.0,
            qty=0.001,
            asset_no=0
        )
        
        if response.error:
            print(f"Order error: {response.error}")
        else:
            print(f"Order submitted: {response.order_id}")
            
            # Cancel order
            cancel = client.cancel_order(response.order_id)
            print(f"Order cancelled: {cancel.status}")
        
        # Check health
        health = client.health
        if not health.connected:
            print("Connection lost!")
            break
```

## Async Support

The client provides async methods for integration with asyncio applications:

```python
import asyncio
from hftbacktest.live import LiveClient

async def trade_handler(client):
    while True:
        trade = await client.get_trade(timeout=1.0)
        if trade:
            print(f"Trade: {trade}")

async def book_handler(client):
    while True:
        book = await client.get_book_update(timeout=1.0)
        if book:
            print(f"Book: {book}")

async def main():
    # Create client...
    with LiveClient(bot) as client:
        await asyncio.gather(
            trade_handler(client),
            book_handler(client)
        )

asyncio.run(main())
```

## API Reference

### LiveClient

Constructor parameters:
- `bot`: Low-level bot instance (`HashMapMarketDepthLiveBot` or `ROIVectorMarketDepthLiveBot`)
- `trade_queue_size`: Maximum trades to buffer (default: 1000)
- `book_queue_size`: Maximum book updates to buffer (default: 1000)
- `snapshot_queue_size`: Maximum snapshots to buffer (default: 100)
- `health_check_interval`: Seconds between health checks (default: 5.0)
- `feed_timeout_ns`: Nanoseconds to wait for feeds (default: 10s)
- `on_connection_lost`: Callback when connection drops
- `on_error`: Callback for errors

Methods:
- `start()`: Start background threads
- `stop()`: Stop background threads
- `close()`: Stop and clean up resources
- `submit_order(side, price, qty, ...)`: Submit buy/sell order
- `cancel_order(order_id, ...)`: Cancel existing order
- `get_trade_nowait()`: Non-blocking trade retrieval
- `get_book_update_nowait()`: Non-blocking book retrieval
- `get_snapshot_nowait()`: Non-blocking snapshot retrieval
- `get_trade(timeout)`: Async trade retrieval
- `get_book_update(timeout)`: Async book retrieval
- `get_snapshot(timeout)`: Async snapshot retrieval
- `get_position(asset_no)`: Get current position
- `get_orders(asset_no)`: Get active orders

Properties:
- `health`: Connection health status
- `current_timestamp`: Current bot timestamp
- `num_assets`: Number of assets

### Models

#### Trade
- `timestamp`: Exchange timestamp (nanoseconds)
- `price`: Trade price
- `qty`: Trade quantity
- `side`: `Side.BUY` or `Side.SELL`
- `asset_no`: Asset index

#### BookUpdate
- `timestamp`: Update timestamp
- `bid_price`: Best bid price
- `bid_qty`: Best bid quantity
- `ask_price`: Best ask price
- `ask_qty`: Best ask quantity
- `asset_no`: Asset index

#### DepthSnapshot
- `timestamp`: Snapshot timestamp
- `bids`: List of `BookLevel` (price, qty)
- `asks`: List of `BookLevel` (price, qty)
- `asset_no`: Asset index

#### OrderResponse
- `order_id`: Order ID
- `status`: `"submitted"`, `"cancelled"`, or `"error"`
- `filled_qty`: Filled quantity
- `avg_price`: Average fill price
- `timestamp`: Response timestamp
- `asset_no`: Asset index
- `error`: Error message if status is `"error"`

#### ConnectionHealth
- `connected`: Boolean connection status
- `feed_latency_ns`: Feed latency in nanoseconds
- `order_latency_ns`: Order latency in nanoseconds
- `last_feed_time`: Last feed timestamp
- `last_order_time`: Last order timestamp

## Connector Setup

Before running your Python bot, start the connector binary:

```bash
# Build connector
cargo build --release --manifest-path connector/Cargo.toml --features binancefutures

# Start connector (name must match LiveInstrument)
./target/release/connector binancefutures BTCUSDT config.toml
```

The connector handles WebSocket connections and publishes market data via Iceoryx2 shared memory.

## Error Handling

```python
from hftbacktest.live import LiveClient, LiveClientError

try:
    with LiveClient(bot) as client:
        response = client.submit_order(...)
        if response.error:
            # Handle order rejection
            print(f"Order failed: {response.error}")
except LiveClientError as e:
    # Handle client errors
    print(f"Client error: {e}")
```

## Thread Safety

The `LiveClient` is thread-safe for order submission and query methods. Event retrieval methods should be called from a single consumer thread or coroutine.

## Lifecycle

The client automatically:
1. Starts background threads for feed processing and health monitoring
2. Buffers events in thread-safe queues
3. Cleans up resources on exit (context manager recommended)
4. Calls user callbacks on connection loss or errors

Always use the context manager or explicitly call `close()` to ensure proper cleanup:

```python
# Recommended: context manager
with LiveClient(bot) as client:
    # Trading logic
    pass

# Manual lifecycle
client = LiveClient(bot)
try:
    client.start()
    # Trading logic
finally:
    client.close()
```

## Testing Without a Connector

For development, testing, and CI/CD environments, use the `StubConnectorBot` which provides a mock connector without requiring Iceoryx2 IPC:

```python
from hftbacktest.live import LiveClient, StubConnectorBot

# Create a stub bot for testing
bot = StubConnectorBot(base_price=50000.0, seed=42)

with LiveClient(bot) as client:
    # Your trading logic here
    trade = client.get_trade_nowait()
    if trade:
        print(f"Trade: {trade.price}")
```

### StubConnectorBot Features

- **No Iceoryx2 required** - Works on any system with Python
- **Synthetic market data** - Generates realistic trades and depth updates
- **Configurable volatility** - Adjust price movement and spread dynamics
- **Deterministic with seed** - Reproducible test data
- **Order simulation** - Accepts, tracks, and simulates order fills
- **Latency simulation** - Realistic feed and order latencies

### Example: Unit Testing Your Strategy

```python
import unittest
from hftbacktest.live import LiveClient, StubConnectorBot

class TestMyStrategy(unittest.TestCase):
    def test_strategy_with_stub(self):
        bot = StubConnectorBot(seed=42)  # Reproducible
        
        with LiveClient(bot) as client:
            trades_collected = 0
            while trades_collected < 100:
                trade = client.get_trade_nowait()
                if trade:
                    trades_collected += 1
                    # Test your logic
                    assert trade.price > 0
        
        self.assertGreater(trades_collected, 0)
```

See `examples/python_live_connector.py` for a complete example.
