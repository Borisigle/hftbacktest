# Bybit Trade History Fetching Feature

## Overview

This document describes the Bybit trade history fetching feature added to py-hftbacktest. The feature enables users to fetch historical trade data from Bybit's v5 REST API with automatic pagination, rate-limit backoff, and optional authentication support.

## Implementation Summary

### Rust Implementation (`py-hftbacktest/src/bybit.rs`)

The core functionality is implemented in Rust for performance:

1. **`BybitTradeHistoryFetcher`**: Main struct that handles API communication
   - Sends GET requests to Bybit's v5 `/market/trades` endpoint
   - Implements request signing using HMAC-SHA256
   - Handles authentication with API key/secret
   - Manages pagination with cursor-based navigation

2. **Rate Limiting and Backoff**:
   - Detects HTTP 429 (Too Many Requests) responses
   - Implements exponential backoff: 50ms, 100ms, 200ms, 400ms, 800ms
   - Max retries: 5 attempts
   - Automatic cursor reset on successful requests

3. **Response Parsing**:
   - Deserializes Bybit's JSON response format
   - Extracts trade fields: execId, symbol, price, size, side, time, isBlockTrade
   - Converts string numbers to typed values (f64 for price/size, i64 for timestamp)
   - Validates numeric conversions with proper error handling

4. **Data Conversion**:
   - `TradeRow` struct maintains trade data in Rust
   - `to_dict()` method converts trades to Python dictionaries
   - Exposed via `fetch_trades()` PyFunction

### Python Wrapper (`py-hftbacktest/hftbacktest/bybit/__init__.py`)

The Python wrapper provides:

1. **`fetch_trades()` Function**:
   - Main public API with comprehensive documentation
   - Parameters: symbol, start_time, end_time, limit, api_key, secret, base_url
   - Returns: List of trade dictionaries with fields: timestamp, symbol, side, size, price
   - Graceful error handling and import error messages

2. **Type Hints**: Full typing for IDE support and mypy compatibility

3. **Module Export**: Accessible via `from hftbacktest.bybit import fetch_trades`

### Integration with PyO3

- Added `mod bybit` to `py-hftbacktest/src/lib.rs`
- Registered `fetch_trades` function via `wrap_pyfunction!` in the pymodule
- Dependencies added to `py-hftbacktest/Cargo.toml`:
  - tokio (async runtime)
  - reqwest (HTTP client)
  - serde/serde_json (JSON serialization)
  - chrono (timestamp handling)
  - hmac/sha2 (request signing)

## API Contract

### Request Parameters

```python
fetch_trades(
    symbol: str,              # "BTCUSDT", "ETHUSDT", etc.
    start_time: int,          # Milliseconds since epoch
    end_time: int,            # Milliseconds since epoch
    *,
    limit: int = 1000,        # Trades per request (max 1000)
    api_key: str = "",        # Bybit API key (optional)
    secret: str = "",         # Bybit API secret (optional)
    base_url: str = "https://api.bybit.com"  # API endpoint
) -> List[Dict]
```

### Response Format

Each trade is a dictionary:

```python
{
    "timestamp": int,         # Milliseconds since epoch
    "symbol": str,            # Trading pair symbol
    "side": str,              # "Buy" or "Sell" (taker side)
    "size": float,            # Trade quantity
    "price": float            # Trade price
}
```

### Error Handling

- **ImportError**: If extension module not found
- **RuntimeError**: If API request fails, returns non-zero status, or rate limit exceeded

## Key Features

### 1. Automatic Pagination

The function transparently handles pagination to fetch all trades within a time range:

```python
# Automatically fetches all trades even if results span multiple pages
trades = fetch_trades("BTCUSDT", start_ms, end_ms)
```

Implementation:
- Extracts `nextPageCursor` from response
- Uses cursor in subsequent requests
- Continues until `nextPageCursor` is None

### 2. Rate Limit Handling

Implements exponential backoff for HTTP 429 responses:

- Initial backoff: 50ms
- Exponential: doubling on each retry
- Max retries: 5
- Max total wait: ~1.55 seconds

Example flow:
1. Request → 429 response → wait 50ms
2. Retry → 429 response → wait 100ms
3. Retry → 429 response → wait 200ms
4. ... (continues up to 5 retries)
5. If still rate limited → RuntimeError

### 3. Authentication Support

Optional API key/secret for higher rate limits:

```python
trades = fetch_trades(
    "BTCUSDT",
    start_ms,
    end_ms,
    api_key="your-key",
    secret="your-secret"
)
```

Request Signing:
- Constructs signature body: `{timestamp}GET/v5/market/trades{query_string}5000`
- Signs with HMAC-SHA256
- Includes in X-BAPI-SIGN header

### 4. Dependency Injection

The implementation supports custom HTTP client and base URL:

```python
# Use testnet
trades = fetch_trades(
    "BTCUSDT",
    start_ms,
    end_ms,
    base_url="https://testnet.bybit.com"
)
```

## Testing

### Unit Tests (`tests/test_bybit_module.py`)

Comprehensive test suite covering:

1. **Module Structure**:
   - Import verification
   - Function callable check
   - Signature validation
   - Docstring presence

2. **API Contract**:
   - Parameter passing
   - Return type validation
   - Response schema verification

3. **Error Handling**:
   - Missing extension module handling
   - Underlying function error propagation

4. **Documentation**:
   - Rate limiting documentation
   - Pagination documentation
   - Authentication documentation

### Integration Tests (`tests/test_bybit_fetch_trades.py`)

Mock-based integration tests with:

1. **Mock Server** (`MockBybitServer`):
   - Simulates Bybit API responses
   - Implements pagination
   - Tracks symbol and time range

2. **Test Cases**:
   - Basic trade fetching
   - Empty result handling
   - Custom limit parameter
   - Response format validation
   - Pagination verification
   - Invalid symbol handling
   - Multiple trade sides (Buy/Sell)

Tests use the `responses` library to mock HTTP requests.

## Documentation

### README (`py-hftbacktest/hftbacktest/bybit/README.md`)

Comprehensive user guide including:
- Quick start examples
- API reference
- Feature details
- Usage examples
- Performance considerations
- Troubleshooting

### RST Documentation (`docs/bybit_fetch_trades.rst`)

Sphinx-compatible documentation with:
- Overview and features
- Quick start
- API reference
- Multiple usage examples
- Troubleshooting guide
- Performance tips
- Related documentation links

### Example Script (`examples/bybit_fetch_trades.py`)

Runnable examples demonstrating:
1. Basic trade fetching
2. Fetching multiple symbols
3. Trade analysis and statistics
4. Authenticated requests
5. Saving data for backtesting

## Usage Examples

### Fetch Trades

```python
from hftbacktest.bybit import fetch_trades
from datetime import datetime, timedelta

end = datetime.utcnow()
start = end - timedelta(hours=1)

trades = fetch_trades(
    "BTCUSDT",
    int(start.timestamp() * 1000),
    int(end.timestamp() * 1000)
)

print(f"Fetched {len(trades)} trades")
```

### Analyze Trades

```python
buy_trades = [t for t in trades if t["side"] == "Buy"]
sell_trades = [t for t in trades if t["side"] == "Sell"]
total_volume = sum(t["size"] for t in trades)
avg_price = sum(t["price"] * t["size"] for t in trades) / total_volume

print(f"Buy ratio: {len(buy_trades) / len(trades) * 100:.1f}%")
print(f"Total volume: {total_volume:.3f}")
print(f"Weighted avg price: {avg_price:.2f}")
```

### Use with Authentication

```python
trades = fetch_trades(
    "BTCUSDT",
    start_ms,
    end_ms,
    api_key="your-api-key",
    secret="your-api-secret"
)
```

## Performance Considerations

### Data Volume

Typical trade counts per minute:
- BTCUSDT: 100-500 trades/min
- ETHUSDT: 100-400 trades/min
- BNBUSDT: 50-200 trades/min

Recommendation: Fetch 1-hour windows for initial testing, adjust based on volume

### Rate Limits

- Public endpoint: ~10 requests/second
- Authenticated endpoint: ~50 requests/second (tier-dependent)

Strategy:
- Use authentication for higher throughput
- Add small delays (50-200ms) between requests
- Reduce time range per request if hitting limits

### Network Performance

- Timeout: 10 seconds per request
- Automatic retry with exponential backoff
- Consider geographic proximity to API servers

## Bybit API Reference

- [Bybit v5 API Documentation](https://bybit-exchange.github.io/docs/v5/intro)
- [Market Trade Endpoint](https://bybit-exchange.github.io/docs/v5/market/trades)
- [API Rate Limits](https://bybit-exchange.github.io/docs/v5/intro#rate-limit)

## Building and Installation

### Build Extension

```bash
cd py-hftbacktest
maturin develop --features live
```

### Install from Source

```bash
pip install -e py-hftbacktest/
```

### Run Tests

```bash
# Unit tests (no external dependencies)
python -m pytest tests/test_bybit_module.py -v

# Integration tests (requires responses library)
pip install responses
python -m pytest tests/test_bybit_fetch_trades.py -v
```

### Run Examples

```bash
python examples/bybit_fetch_trades.py
```

## Error Scenarios

### ImportError: hftbacktest extension not found

Solution:
```bash
maturin develop --manifest-path py-hftbacktest/Cargo.toml
```

### RuntimeError: Rate limited

Solution:
- Use authenticated API key/secret
- Add delays between requests
- Reduce time range per request

### RuntimeError: HTTP error / Invalid symbol

Solution:
- Verify symbol exists (e.g., BTCUSDT not BTC)
- Check Bybit is accessible
- Verify time range has trading activity

## Future Enhancements

Potential improvements:
1. Async Python interface with asyncio
2. Batch fetching for multiple symbols
3. Streaming trades via WebSocket
4. Local caching layer
5. Conversion to pandas DataFrame
6. Direct NumPy array export for backtesting

## Maintenance Notes

### Dependencies

- tokio: Used for async runtime (required for reqwest)
- reqwest: HTTP client for API requests
- serde: JSON serialization/deserialization
- chrono: Timestamp handling
- hmac/sha2: Request signing

### Thread Safety

- `BybitTradeHistoryFetcher` is thread-safe (Send + Sync)
- Each request creates new tokio runtime for blocking
- No shared mutable state between requests

### Code Quality

- All Rust code follows style guidelines
- Python code uses type hints
- Comprehensive docstrings
- Full test coverage for API contract
- Error handling on all fallible operations

## Architecture Diagram

```
┌─────────────────────────────────────────────┐
│         Python API                          │
│  from hftbacktest.bybit import fetch_trades │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│         Python Wrapper                      │
│   hftbacktest/bybit/__init__.py             │
│   - Type hints                              │
│   - Error handling                          │
│   - Module import checking                  │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│      PyO3 Function Bridge                   │
│   pyfunction(fetch_trades) in lib.rs        │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│         Rust Implementation                 │
│   src/bybit.rs                              │
│   - BybitTradeHistoryFetcher                │
│   - Request signing                         │
│   - Pagination handling                     │
│   - Rate limit backoff                      │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│      External Dependencies                  │
│   - reqwest (HTTP)                          │
│   - tokio (async runtime)                   │
│   - serde (JSON)                            │
│   - hmac/sha2 (signing)                     │
└─────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│     Bybit API v5 Endpoint                   │
│   GET /v5/market/trades                     │
└─────────────────────────────────────────────┘
```

## Contact & Support

For issues or questions:
1. Check Troubleshooting section in README.md
2. Review Bybit API documentation
3. Check test cases for usage patterns
4. Open an issue with error output and MRE
