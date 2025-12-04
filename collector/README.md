# Collector

A high-performance market data collector for cryptocurrency exchanges. Records real-time trade, order book, liquidation, and mark price data to compressed files for later backtesting and analysis.

## Supported Exchanges

- **Binance Futures (USDT-M)**: `binancefutures` or `binancefuturesum`
- **Binance Futures (Coin-M)**: `binancefuturescm`
- **Binance Spot**: `binance` or `binancespot`
- **Bybit**: `bybit`
- **Hyperliquid**: `hyperliquid`

## Installation

```bash
cargo build --release -p collector
```

## Usage

### Basic Usage

```bash
# Collect BTCUSDT data from Binance Futures
cargo run -p collector --release -- <output_dir> binancefutures BTCUSDT

# Collect multiple symbols
cargo run -p collector --release -- <output_dir> binancefutures BTCUSDT ETHUSDT SOLUSDT
```

### Additional Data Streams (Binance Futures)

The collector supports additional data streams beyond the default trade and order book feeds:

```bash
# Include liquidation events (forceOrder)
cargo run -p collector --release -- <output_dir> binancefutures BTCUSDT --include-liquidations

# Include mark price updates (1 second intervals)
cargo run -p collector --release -- <output_dir> binancefutures BTCUSDT --include-mark-price

# Include both liquidations and mark price
cargo run -p collector --release -- <output_dir> binancefutures BTCUSDT \
    --include-liquidations \
    --include-mark-price

# Exclude book ticker (best bid/ask) - included by default
cargo run -p collector --release -- <output_dir> binancefutures BTCUSDT --exclude-book-ticker

# Full Smart Money Order Flow collection (recommended for BTCUSDT strategy)
cargo run -p collector --release -- ./data binancefutures BTCUSDT \
    --include-liquidations \
    --include-mark-price
```

### Command Line Options

```
USAGE:
    collector [OPTIONS] <PATH> <EXCHANGE> [SYMBOLS]...

ARGS:
    <PATH>         Path for the files where collected data will be written
    <EXCHANGE>     Name of the exchange (binancefutures, binancefuturescm, binance, bybit, hyperliquid)
    <SYMBOLS>...   Symbols for which data will be collected

OPTIONS:
    --include-liquidations    Include liquidation (forceOrder) events
    --include-mark-price      Include mark price updates (@1s interval)
    --exclude-book-ticker     Exclude book ticker (best bid/ask) events
    -h, --help                Print help information
    -V, --version             Print version information
```

## Output File Structure

Data is organized by symbol and event type in nested directories:

```
<output_dir>/
├── btcusdt/
│   ├── trade_YYYYMMDD.gz        # Trade events
│   ├── depth_YYYYMMDD.gz        # Order book depth updates
│   ├── bookticker_YYYYMMDD.gz   # Best bid/ask updates
│   ├── liquidation_YYYYMMDD.gz  # Forced liquidation orders
│   ├── markprice_YYYYMMDD.gz    # Mark price updates
│   └── unknown_YYYYMMDD.gz      # Depth snapshots and other data
├── ethusdt/
│   ├── trade_YYYYMMDD.gz
│   └── ...
└── ...
```

### File Format

Each line in the gzipped files contains:
```
<timestamp_nanos> <json_data>
```

Where:
- `timestamp_nanos`: Unix timestamp in nanoseconds when the data was received
- `json_data`: The raw JSON message from the exchange WebSocket

### Event Types

| Stream | Event Type (`e` field) | Output File |
|--------|----------------------|-------------|
| `@trade` | `trade` | `trade_YYYYMMDD.gz` |
| `@depth@0ms` | `depthUpdate` | `depth_YYYYMMDD.gz` |
| `@bookTicker` | `bookTicker` | `bookticker_YYYYMMDD.gz` |
| `@forceOrder` | `forceOrder` | `liquidation_YYYYMMDD.gz` |
| `@markPrice@1s` | `markPriceUpdate` | `markprice_YYYYMMDD.gz` |
| REST snapshot | (none) | `unknown_YYYYMMDD.gz` |

## Examples

### Smart Money Order Flow Strategy Data Collection

For the Smart Money Order Flow / Liquidation Run strategy, collect comprehensive BTCUSDT data:

```bash
# Create data directory
mkdir -p ./market_data

# Start collector with all relevant feeds
cargo run -p collector --release -- ./market_data binancefutures BTCUSDT \
    --include-liquidations \
    --include-mark-price

# Run for multi-hour sessions (use screen/tmux for long-running collection)
screen -S btcusdt_collector
cargo run -p collector --release -- ./market_data binancefutures BTCUSDT \
    --include-liquidations \
    --include-mark-price
# Ctrl+A D to detach
```

### Multi-Symbol Collection

```bash
# Collect major pairs for cross-market analysis
cargo run -p collector --release -- ./market_data binancefutures \
    BTCUSDT ETHUSDT SOLUSDT BNBUSDT \
    --include-liquidations \
    --include-mark-price
```

## Depth Snapshot Resync

The collector automatically detects gaps in the order book depth stream by monitoring the `pu` (previous update ID) field. When a gap is detected:

1. A warning is logged
2. A full depth snapshot is fetched via REST API
3. The snapshot is written to the output for later reconstruction

This ensures the order book can be accurately rebuilt during backtesting even if some WebSocket messages were missed.

## Development

### Running Tests

```bash
cargo test -p collector
```

### Building for Production

```bash
cargo build --release -p collector

# Binary location
./target/release/collector
```

## Integration with hftbacktest

The collected data files can be processed by the hftbacktest data pipeline:

1. Decompress and parse the `.gz` files
2. Convert to the NPZ format expected by the backtest engine
3. Use the `DataSource::File` or `DataSource::from_npz` to load into backtests

See the main hftbacktest documentation for details on data ingestion.

## License

MIT License - See the repository root for full license text.
