"""
Example: Fetch Bybit trade history using hftbacktest.bybit.fetch_trades

This example demonstrates how to fetch trade history from Bybit using the
hftbacktest library and use it for analysis or backtesting.
"""

from datetime import datetime, timedelta
from hftbacktest.bybit import fetch_trades


def example_basic_fetch():
    """Fetch trades for a recent 1-hour window."""
    print("=" * 60)
    print("Example 1: Basic Trade Fetching")
    print("=" * 60)

    # Define time range: last hour
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)

    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)

    print(f"Fetching BTCUSDT trades from {start_time} to {end_time}")

    try:
        trades = fetch_trades("BTCUSDT", start_ms, end_ms, limit=500)
        print(f"✓ Fetched {len(trades)} trades")

        if trades:
            # Show sample trades
            print("\nFirst 5 trades:")
            for i, trade in enumerate(trades[:5]):
                ts = datetime.fromtimestamp(trade["timestamp"] / 1000)
                print(
                    f"  {i+1}. {ts} | {trade['side']:4s} {trade['size']:>8.3f} @ {trade['price']:>10.2f}"
                )

    except RuntimeError as e:
        print(f"✗ Error: {e}")


def example_multiple_symbols():
    """Fetch trades for multiple symbols in a time range."""
    print("\n" + "=" * 60)
    print("Example 2: Fetching Multiple Symbols")
    print("=" * 60)

    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)

    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)

    all_trades = {}

    for symbol in symbols:
        print(f"\nFetching {symbol}...")
        try:
            trades = fetch_trades(symbol, start_ms, end_ms, limit=500)
            all_trades[symbol] = trades
            print(f"  ✓ {len(trades)} trades")
        except RuntimeError as e:
            print(f"  ✗ Error: {e}")

    # Summary
    print("\nSummary:")
    for symbol, trades in all_trades.items():
        if trades:
            total_volume = sum(t["size"] for t in trades)
            buy_count = sum(1 for t in trades if t["side"] == "Buy")
            sell_count = sum(1 for t in trades if t["side"] == "Sell")
            print(f"  {symbol}: {len(trades)} trades | Volume: {total_volume:.3f} | Buy: {buy_count}, Sell: {sell_count}")


def example_analyze_trades():
    """Fetch and analyze trade statistics."""
    print("\n" + "=" * 60)
    print("Example 3: Trade Analysis")
    print("=" * 60)

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)

    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)

    try:
        trades = fetch_trades("BTCUSDT", start_ms, end_ms, limit=500)

        if not trades:
            print("No trades found in the time range.")
            return

        # Analyze trades
        print(f"\nAnalyzing {len(trades)} trades...")

        # Calculate statistics
        prices = [t["price"] for t in trades]
        sizes = [t["size"] for t in trades]

        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        total_volume = sum(sizes)

        buy_trades = [t for t in trades if t["side"] == "Buy"]
        sell_trades = [t for t in trades if t["side"] == "Sell"]

        print(f"\n  Price Range: {min_price:.2f} - {max_price:.2f}")
        print(f"  Average Price: {avg_price:.2f}")
        print(f"  Total Volume: {total_volume:.3f}")
        print(f"  Buy Orders: {len(buy_trades)} ({len(buy_trades)/len(trades)*100:.1f}%)")
        print(f"  Sell Orders: {len(sell_trades)} ({len(sell_trades)/len(trades)*100:.1f}%)")

        # Identify large trades
        large_trades = [t for t in trades if t["size"] > sorted(sizes, reverse=True)[len(sizes) // 10]]
        print(f"\n  Large Trades (top 10%): {len(large_trades)}")
        for i, trade in enumerate(large_trades[:3]):
            ts = datetime.fromtimestamp(trade["timestamp"] / 1000)
            print(f"    {i+1}. {ts} {trade['side']:4s} {trade['size']:>8.3f} @ {trade['price']:>10.2f}")

    except RuntimeError as e:
        print(f"✗ Error: {e}")


def example_with_api_keys():
    """Fetch trades using authenticated API (if you have credentials)."""
    print("\n" + "=" * 60)
    print("Example 4: Authenticated Request")
    print("=" * 60)

    # NOTE: In production, load from environment variables or config file
    API_KEY = ""  # Set your API key
    API_SECRET = ""  # Set your API secret

    if not API_KEY or not API_SECRET:
        print("Skipping authenticated request (no credentials provided)")
        print("To use authenticated requests, set API_KEY and API_SECRET")
        return

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)

    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)

    try:
        trades = fetch_trades(
            "BTCUSDT",
            start_ms,
            end_ms,
            limit=500,
            api_key=API_KEY,
            secret=API_SECRET,
        )
        print(f"✓ Authenticated request successful: {len(trades)} trades")
    except RuntimeError as e:
        print(f"✗ Error: {e}")


def example_save_for_backtesting():
    """Fetch trades and save for backtesting."""
    print("\n" + "=" * 60)
    print("Example 5: Save for Backtesting")
    print("=" * 60)

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)

    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)

    try:
        print("Fetching BTCUSDT trades...")
        trades = fetch_trades("BTCUSDT", start_ms, end_ms, limit=500)

        if trades:
            # Note: This is pseudocode - actual usage would depend on your backtest framework
            print(f"\n✓ Fetched {len(trades)} trades")
            print("\nTrade data ready for backtesting:")
            print(f"  - Time range: {start_time} to {end_time}")
            print(f"  - Total trades: {len(trades)}")
            print(f"  - Total volume: {sum(t['size'] for t in trades):.3f}")

    except RuntimeError as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    print("\nBybit Trade Fetching Examples")
    print("=" * 60)

    try:
        # Run examples
        example_basic_fetch()
        example_multiple_symbols()
        example_analyze_trades()
        example_with_api_keys()
        example_save_for_backtesting()

        print("\n" + "=" * 60)
        print("Examples completed!")
        print("=" * 60)

    except ImportError as e:
        print(f"Error: {e}")
        print("\nPlease ensure hftbacktest is properly installed:")
        print("  maturin develop --manifest-path py-hftbacktest/Cargo.toml")
