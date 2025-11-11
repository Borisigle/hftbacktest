# Bybit Trade History Fetcher

This module provides utilities for fetching historical trade data from Bybit's v5 REST API.

## Overview

The `fetch_trades()` function enables users to retrieve Bybit trade history between two timestamps with automatic pagination, rate-limit backoff, and optional authentication.

## Quick Start

### Basic Usage (Public Endpoint)

```python
from hftbacktest.bybit import fetch_trades
from datetime import datetime

# Define time range
start = int(datetime(2024, 1, 1, 0, 0, 0).timestamp() * 1000)  # milliseconds
end = int(datetime(2024, 1, 1, 1, 0, 0).timestamp() * 1000)

# Fetch trades
trades = fetch_trades("BTCUSDT", start, end)

# Process trades
for trade in trades:
    print(f"{trade['timestamp']} {trade['symbol']} {trade['side']} {trade['size']} @ {trade['price']}")
```

### Authenticated Requests

For higher rate limits, provide API credentials:

```python
trades = fetch_trades(
    "BTCUSDT",
    start,
    end,
    api_key="your-api-key",
    secret="your-api-secret"
)
```

## API Reference

### `fetch_trades(symbol, start_time, end_time, *, limit=1000, api_key="", secret="", base_url="https://api.bybit.com")`

Fetch historical trades from Bybit between two timestamps.

#### Parameters

- **symbol** (str): Trading symbol (e.g., "BTCUSDT", "ETHUSDT", "XRPUSDT")
- **start_time** (int): Start timestamp in milliseconds (inclusive)
- **end_time** (int): End timestamp in milliseconds (inclusive)
- **limit** (int, optional): Trades per request. Default: 1000 (Bybit max: 1000)
- **api_key** (str, optional): API key for authentication. Default: "" (public endpoint)
- **secret** (str, optional): API secret for authentication. Default: "" (public endpoint)
- **base_url** (str, optional): Bybit API base URL. Default: "https://api.bybit.com"

#### Returns

List of dictionaries with the following structure:

```python
[
    {
        "timestamp": 1704067200000,      # Trade timestamp in milliseconds
        "symbol": "BTCUSDT",              # Trading symbol
        "side": "Buy",                    # Trade side: "Buy" (taker is buyer) or "Sell"
        "size": 0.123,                    # Trade quantity
        "price": 42345.67                 # Trade price
    },
    # ... more trades
]
```

#### Raises

- **RuntimeError**: If API request fails, returns non-zero status code, or rate limit exceeded

## Features

### Automatic Pagination

The function automatically handles pagination to fetch all trades within the specified time range, even if the result set is large:

```python
# This automatically fetches all trades and handles pagination
trades = fetch_trades("BTCUSDT", start, end)
print(f"Fetched {len(trades)} trades")  # May be thousands
```

### Rate Limit Handling

The function includes exponential backoff for rate-limited requests (HTTP 429):

- Initial backoff: 50ms
- Exponential: 50ms, 100ms, 200ms, 400ms, 800ms
- Max retries: 5
- Max wait: ~1.55 seconds total

```python
try:
    trades = fetch_trades("BTCUSDT", start, end)
except RuntimeError as e:
    print(f"Failed after retries: {e}")
```

### Authentication

Use API key/secret for higher rate limits:

```python
# Public endpoint: ~10 requests/second limit
trades_public = fetch_trades("BTCUSDT", start, end)

# Authenticated endpoint: Higher rate limits
trades_auth = fetch_trades(
    "BTCUSDT",
    start,
    end,
    api_key="ABC123...",
    secret="XYZ789..."
)
```

## Usage Examples

### Fetch Trades for Data Analysis

```python
from hftbacktest.bybit import fetch_trades
from datetime import datetime, timedelta
import pandas as pd

# Fetch 1 hour of data
start = int(datetime(2024, 1, 1, 12, 0, 0).timestamp() * 1000)
end = int(datetime(2024, 1, 1, 13, 0, 0).timestamp() * 1000)

trades = fetch_trades("BTCUSDT", start, end)

# Convert to DataFrame for analysis
df = pd.DataFrame(trades)
print(f"Total trades: {len(df)}")
print(f"Buy/Sell ratio: {len(df[df['side']=='Buy']) / len(df):.2%}")
print(f"Volume: {df['size'].sum():.3f}")
print(f"Weighted avg price: {(df['price'] * df['size']).sum() / df['size'].sum():.2f}")
```

### Fetch and Store for Backtesting

```python
from hftbacktest.bybit import fetch_trades
from datetime import datetime
import numpy as np

# Fetch trades
start = int(datetime(2024, 1, 1).timestamp() * 1000)
end = int(datetime(2024, 1, 2).timestamp() * 1000)
trades = fetch_trades("BTCUSDT", start, end, limit=500)

# Convert to numpy array for backtesting
trade_data = np.array([
    (t['timestamp'], t['symbol'], t['side'], t['size'], t['price'])
    for t in trades
], dtype=[
    ('timestamp', 'i8'),
    ('symbol', 'U20'),
    ('side', 'U4'),
    ('size', 'f8'),
    ('price', 'f8')
])

# Save for later use
np.savez_compressed('btcusdt_trades.npz', trades=trade_data)
```

### Fetch Multiple Symbols

```python
from hftbacktest.bybit import fetch_trades
from datetime import datetime
import asyncio

start = int(datetime(2024, 1, 1).timestamp() * 1000)
end = int(datetime(2024, 1, 2).timestamp() * 1000)

symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
all_trades = {}

for symbol in symbols:
    print(f"Fetching {symbol}...")
    all_trades[symbol] = fetch_trades(symbol, start, end, limit=500)
    print(f"  -> {len(all_trades[symbol])} trades")
```

## Bybit API Reference

For more information about Bybit's trade endpoint:
- [Bybit v5 Market Trade API](https://bybit-exchange.github.io/docs/v5/market/trades)
- [Bybit API Rate Limits](https://bybit-exchange.github.io/docs/v5/intro#rate-limit)

## Troubleshooting

### "Module not found" Error

If you get `ImportError: hftbacktest extension module not found`:

1. Ensure py-hftbacktest is installed: `pip install -e py-hftbacktest/`
2. Or build it manually: `maturin develop --manifest-path py-hftbacktest/Cargo.toml`

### Rate Limit Exceeded

If you get `RuntimeError: Rate limited: max retries exceeded`:

1. Add delays between requests: `import time; time.sleep(1)`
2. Use authenticated API key/secret for higher limits
3. Reduce the time range per request
4. Consider using a different data source

### Network Timeout

If requests time out:

1. Check internet connectivity
2. Try a different `base_url` (e.g., testnet)
3. Increase timeout in custom implementation

### No Trades Returned

Possible causes:

1. Symbol doesn't exist or has no trading activity
2. Time range is too old (historical data availability)
3. Time range has no trades (try narrowing to recent time)

## Performance Considerations

### Data Volume

Bybit typically has high trading volume. For popular symbols:
- **BTCUSDT**: ~100-500 trades per minute
- **ETHUSDT**: ~100-400 trades per minute
- **BNBUSDT**: ~50-200 trades per minute

Adjust `limit` and time ranges accordingly:

```python
from datetime import datetime, timedelta

# For heavy traffic: fetch smaller time windows
end = datetime.now()
start = end - timedelta(hours=1)  # 1-hour window

trades = fetch_trades("BTCUSDT", 
    int(start.timestamp() * 1000),
    int(end.timestamp() * 1000),
    limit=1000
)
```

### Rate Limits

- **Public endpoint**: ~10 requests/second
- **Authenticated endpoint**: ~50 requests/second (with proper tier)

Plan accordingly when fetching large datasets.

## Development & Testing

For testing with mock server, see `tests/test_bybit_fetch_trades.py`.

The test suite includes:
- Basic functionality tests
- Pagination verification
- Rate limit handling
- Error scenarios
- API contract verification
