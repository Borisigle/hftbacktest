Bybit Trade History Fetching
=============================

Overview
--------

The ``hftbacktest.bybit`` module provides a convenient interface to fetch historical trade data from Bybit's v5 REST API. This allows you to easily retrieve trade history for analysis, backtesting, and research.

Key Features
~~~~~~~~~~~~

- **Automatic Pagination**: Transparently handles pagination to fetch all trades in a time range
- **Rate Limit Handling**: Implements exponential backoff for rate-limited requests
- **Authentication Support**: Optional API key/secret for higher rate limits
- **Simple API**: Straightforward function signature with sensible defaults

Quick Start
-----------

Basic Usage
~~~~~~~~~~~

.. code-block:: python

    from hftbacktest.bybit import fetch_trades
    from datetime import datetime

    # Fetch trades from the past hour
    start = int(datetime(2024, 1, 1, 0, 0, 0).timestamp() * 1000)
    end = int(datetime(2024, 1, 1, 1, 0, 0).timestamp() * 1000)

    trades = fetch_trades("BTCUSDT", start, end)
    print(f"Fetched {len(trades)} trades")

    for trade in trades:
        print(f"{trade['timestamp']} {trade['side']} {trade['size']} @ {trade['price']}")

API Reference
-------------

.. py:function:: fetch_trades(symbol, start_time, end_time, *, limit=1000, api_key="", secret="", base_url="https://api.bybit.com")

    Fetch Bybit trade history between two timestamps.

    :param symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT")
    :type symbol: str
    :param start_time: Start timestamp in milliseconds
    :type start_time: int
    :param end_time: End timestamp in milliseconds
    :type end_time: int
    :param limit: Trades per request (default 1000, max 1000). Note: Bybit API limit is 1000 per request.
    :type limit: int
    :param api_key: API key for authenticated requests (optional)
    :type api_key: str
    :param secret: API secret for authenticated requests (optional)
    :type secret: str
    :param base_url: Base URL for Bybit API (optional)
    :type base_url: str

    :return: List of trade dictionaries
    :rtype: List[Dict]

    :raises RuntimeError: If API request fails or rate limit exceeded

Response Format
~~~~~~~~~~~~~~~

Each trade in the returned list has the following structure:

.. code-block:: python

    {
        "timestamp": 1704067200000,      # Trade timestamp in milliseconds
        "symbol": "BTCUSDT",             # Trading symbol
        "side": "Buy" or "Sell",         # Trade side (taker side)
        "size": 0.123,                   # Trade quantity
        "price": 42345.67                # Trade price
    }

Examples
--------

Fetch Trades for Multiple Symbols
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from hftbacktest.bybit import fetch_trades
    from datetime import datetime, timedelta

    # Define time range
    end = datetime.utcnow()
    start = end - timedelta(hours=1)

    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    # Fetch multiple symbols
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    all_trades = {}

    for symbol in symbols:
        print(f"Fetching {symbol}...")
        trades = fetch_trades(symbol, start_ms, end_ms, limit=500)
        all_trades[symbol] = trades
        print(f"  -> {len(trades)} trades")

Analyze Trade Statistics
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from hftbacktest.bybit import fetch_trades
    from datetime import datetime, timedelta

    end = datetime.utcnow()
    start = end - timedelta(hours=1)

    trades = fetch_trades(
        "BTCUSDT",
        int(start.timestamp() * 1000),
        int(end.timestamp() * 1000)
    )

    # Calculate statistics
    prices = [t["price"] for t in trades]
    sizes = [t["size"] for t in trades]
    buy_trades = [t for t in trades if t["side"] == "Buy"]
    sell_trades = [t for t in trades if t["side"] == "Sell"]

    print(f"Total trades: {len(trades)}")
    print(f"Price range: {min(prices):.2f} - {max(prices):.2f}")
    print(f"Avg price: {sum(prices) / len(prices):.2f}")
    print(f"Total volume: {sum(sizes):.3f}")
    print(f"Buy ratio: {len(buy_trades) / len(trades) * 100:.1f}%")

Authenticated Requests
~~~~~~~~~~~~~~~~~~~~~~

For higher rate limits, use your Bybit API credentials:

.. code-block:: python

    from hftbacktest.bybit import fetch_trades
    import os

    # Load from environment variables (recommended)
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")

    trades = fetch_trades(
        "BTCUSDT",
        start_ms,
        end_ms,
        api_key=api_key,
        secret=api_secret
    )

Features in Detail
------------------

Automatic Pagination
~~~~~~~~~~~~~~~~~~~~

The function automatically handles pagination to retrieve all trades within the specified time range:

.. code-block:: python

    # This automatically fetches all trades, making multiple requests if needed
    trades = fetch_trades("BTCUSDT", start_ms, end_ms)
    print(f"Total trades (paginated): {len(trades)}")  # May be thousands

Rate Limit Handling
~~~~~~~~~~~~~~~~~~~

The function implements exponential backoff for rate-limited requests:

- Initial backoff: 50ms
- Exponential backoff: 50ms, 100ms, 200ms, 400ms, 800ms
- Max retries: 5
- Max total wait: ~1.55 seconds

.. code-block:: python

    try:
        trades = fetch_trades("BTCUSDT", start_ms, end_ms)
    except RuntimeError as e:
        if "rate limited" in str(e):
            print("API rate limit exceeded after retries")
        else:
            print(f"API error: {e}")

Performance Considerations
--------------------------

Data Volume
~~~~~~~~~~~

Bybit has high trading volume. Approximate trade counts:

- **BTCUSDT**: 100-500 trades per minute
- **ETHUSDT**: 100-400 trades per minute  
- **BNBUSDT**: 50-200 trades per minute

Plan your time ranges accordingly:

.. code-block:: python

    from datetime import datetime, timedelta

    # For heavy traffic: fetch smaller time windows
    end = datetime.utcnow()
    start = end - timedelta(hours=1)  # 1-hour window

    trades = fetch_trades(
        "BTCUSDT",
        int(start.timestamp() * 1000),
        int(end.timestamp() * 1000),
        limit=1000
    )

Rate Limits
~~~~~~~~~~~

- **Public endpoint**: ~10 requests/second
- **Authenticated endpoint**: ~50 requests/second (tier-dependent)

Consider adding small delays between requests when fetching large datasets:

.. code-block:: python

    import time
    from hftbacktest.bybit import fetch_trades

    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    
    for symbol in symbols:
        trades = fetch_trades(symbol, start_ms, end_ms)
        time.sleep(0.2)  # Small delay between requests

Troubleshooting
---------------

"Module not found" Error
~~~~~~~~~~~~~~~~~~~~~~~~

If you get an ImportError, ensure py-hftbacktest is installed and built:

.. code-block:: bash

    # Build the Python extension
    maturin develop --manifest-path py-hftbacktest/Cargo.toml

Rate Limit Exceeded
~~~~~~~~~~~~~~~~~~~

If you consistently exceed rate limits:

1. Use authenticated API key/secret
2. Increase delays between requests
3. Reduce time range per request
4. Consider fetching less frequently

Network Timeout
~~~~~~~~~~~~~~~

If requests timeout:

1. Check internet connectivity
2. Try a different base URL (testnet: https://testnet.bybit.com)
3. Ensure your firewall isn't blocking API requests

No Trades Returned
~~~~~~~~~~~~~~~~~~

Possible causes:

1. Symbol doesn't exist or isn't trading
2. Time range is too far in the past
3. No trading activity during the period

Verify with Bybit's official API documentation: https://bybit-exchange.github.io/docs/v5/market/trades

Related Documentation
----------------------

- `Bybit v5 API Documentation <https://bybit-exchange.github.io/docs/v5/intro>`_
- `Bybit Market Trade Endpoint <https://bybit-exchange.github.io/docs/v5/market/trades>`_
- `Bybit Rate Limits <https://bybit-exchange.github.io/docs/v5/intro#rate-limit>`_
