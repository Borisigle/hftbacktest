"""Bybit exchange utilities for fetching historical trade data."""

from typing import Dict, List, Optional

try:
    from .. import _hftbacktest
except ImportError:
    _hftbacktest = None


def fetch_trades(
    symbol: str,
    start_time: int,
    end_time: int,
    *,
    limit: int = 1000,
    api_key: str = "",
    secret: str = "",
    base_url: str = "https://api.bybit.com",
) -> List[Dict]:
    """
    Fetch Bybit trade history between two timestamps.

    This function calls Bybit's v5 public trade REST endpoint to retrieve historical trade data.
    It supports authentication via API key/secret when provided, automatic pagination, and rate-limit
    backoff.

    Args:
        symbol (str): Trading symbol in Bybit format (e.g., "BTCUSDT", "ETHUSDT").
        start_time (int): Start timestamp in milliseconds.
        end_time (int): End timestamp in milliseconds.
        limit (int, optional): Number of trades per request (default 1000, max 1000).
            Bybit API limit is 1000 per request.
        api_key (str, optional): Bybit API key for authenticated requests.
            If empty string, requests are made to the public endpoint. Default: "".
        secret (str, optional): Bybit API secret for authenticated requests.
            Required if api_key is provided. Default: "".
        base_url (str, optional): Base URL for Bybit API.
            Default: "https://api.bybit.com".

    Returns:
        List[Dict]: List of dictionaries representing trades. Each dict contains:
            - timestamp (int): Trade timestamp in milliseconds
            - symbol (str): Trading symbol
            - side (str): Trade side ("Buy" or "Sell"), represents the taker side
            - size (float): Trade quantity
            - price (float): Trade price

    Raises:
        RuntimeError: If the API request fails, returns non-zero status code,
            or rate limit is exceeded after max retries.

    Examples:
        >>> # Fetch trades for BTCUSDT from 2024-01-01 00:00:00 to 2024-01-01 01:00:00
        >>> import datetime
        >>> from hftbacktest.bybit import fetch_trades
        >>>
        >>> start = int(datetime.datetime(2024, 1, 1, 0, 0, 0).timestamp() * 1000)
        >>> end = int(datetime.datetime(2024, 1, 1, 1, 0, 0).timestamp() * 1000)
        >>> trades = fetch_trades("BTCUSDT", start, end, limit=500)
        >>> for trade in trades:
        ...     print(f"{trade['symbol']} {trade['side']} {trade['size']} @ {trade['price']}")

    Notes:
        - Automatic pagination: The function automatically handles pagination to retrieve
          all trades within the time range.
        - Rate limiting: If Bybit returns a 429 status code (rate limited), the function
          automatically backs off with exponential backoff (50ms, 100ms, 200ms, 400ms, 800ms)
          up to 5 retries before raising an error.
        - Feed latency: Returned timestamps are from Bybit's server and may need latency
          adjustment for realistic backtesting. Consider adding feed latency if using this
          data for backtesting.
        - Public vs. Authenticated: The public endpoint is rate-limited differently than
          authenticated endpoints. Use API key/secret for higher rate limits if needed.

    See Also:
        - Bybit v5 Market Trade API: https://bybit-exchange.github.io/docs/v5/market/trades
    """
    if _hftbacktest is None:
        raise ImportError(
            "hftbacktest extension module not found. "
            "Please ensure py-hftbacktest is properly installed."
        )

    return _hftbacktest.fetch_trades(
        symbol,
        start_time,
        end_time,
        limit=limit,
        api_key=api_key,
        secret=secret,
        base_url=base_url,
    )


__all__ = ["fetch_trades"]
