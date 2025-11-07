Python Live Connector Example
==============================

This guide explains how to use the ``python_live_connector.py`` example, which demonstrates the key patterns for building live trading strategies with HftBacktest.

What This Example Shows
-----------------------

The example demonstrates:

1. **LiveClient Setup** - How to configure and instantiate the high-level LiveClient wrapper
2. **Market Data Subscription** - Subscribing to trades and depth updates
3. **Statistics Collection** - Aggregating market data into useful statistics
4. **Graceful Shutdown** - Proper cleanup using context managers

Quick Start with Stub
---------------------

To run the example immediately without setting up a real connector:

.. code-block:: console

    python examples/python_live_connector.py --stub --duration 5

This uses the ``StubConnectorBot``, a lightweight mock that generates synthetic market data. It's perfect for:

- Testing your code without a real connector
- CI/CD pipelines where Iceoryx2 IPC isn't available
- Development and debugging

Expected Output
~~~~~~~~~~~~~~~

.. code-block:: text

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

Running with a Real Connector
------------------------------

To swap the stub for a real connector:

1. **Build the connector binary:**

   .. code-block:: console

       cargo build --release --manifest-path connector/Cargo.toml --features binancefutures

2. **Build the Python wheel with live feature:**

   .. code-block:: console

       maturin develop --manifest-path py-hftbacktest/Cargo.toml --features live

3. **Create a configuration file** (e.g., ``binancefutures.toml``):

   .. code-block:: toml

       # Testnet: wss://fstream.binancefuture.com/ws
       stream_url = "wss://fstream.binancefuture.com/ws"

       # Testnet: https://testnet.binancefuture.com
       api_url = "https://testnet.binancefuture.com"

       order_prefix = "test"
       api_key = "your_api_key"
       secret = "your_secret"

4. **Start the connector:**

   .. code-block:: console

       ./target/release/connector binancefutures BTCUSDT binancefutures.toml

5. **Run the example** (without the ``--stub`` flag):

   .. code-block:: console

       python examples/python_live_connector.py --duration 30

Code Walkthrough
----------------

Market Data Collection
~~~~~~~~~~~~~~~~~~~~~~

The example shows how to collect trades and depth updates:

.. code-block:: python

    from hftbacktest.live import LiveClient, StubConnectorBot

    # Create a stub bot (or real bot connected to connector)
    bot = StubConnectorBot()

    # Wrap with high-level client
    with LiveClient(bot) as client:
        # Process trades
        trade = client.get_trade_nowait()
        if trade:
            print(f"Trade: {trade.price} @ {trade.qty}")

        # Process book updates
        book = client.get_book_update_nowait()
        if book:
            print(f"Book: {book.bid_price} / {book.ask_price}")

Statistics Collection
~~~~~~~~~~~~~~~~~~~~~

The example aggregates statistics from market data:

.. code-block:: python

    from dataclasses import dataclass

    @dataclass
    class MarketStatistics:
        total_trades: int = 0
        buy_volume: float = 0.0
        sell_volume: float = 0.0
        total_volume: float = 0.0
        last_bid: Optional[float] = None
        last_ask: Optional[float] = None
        spread: Optional[float] = None

    stats = MarketStatistics()

    trade = client.get_trade_nowait()
    if trade:
        stats.total_trades += 1
        if trade.side.name == "BUY":
            stats.buy_volume += trade.qty
        else:
            stats.sell_volume += trade.qty

Order Management Example
~~~~~~~~~~~~~~~~~~~~~~~

While the basic example shows subscription only, here's how to add orders:

.. code-block:: python

    from hftbacktest.live import Side

    # Submit an order
    response = client.submit_order(
        side=Side.BUY,
        price=50000.0,
        qty=0.1,
        asset_no=0
    )

    if response.error:
        print(f"Order error: {response.error}")
    else:
        print(f"Order submitted: {response.order_id}")

        # Cancel the order
        cancel_response = client.cancel_order(response.order_id)
        print(f"Cancel status: {cancel_response.status}")

Connection Health Monitoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The example checks connection health:

.. code-block:: python

    health = client.health
    if not health.connected:
        print("Connection lost!")
    else:
        print(f"Feed latency: {health.feed_latency_ns}ns")
        print(f"Order latency: {health.order_latency_ns}ns")

StubConnectorBot Reference
--------------------------

The ``StubConnectorBot`` is useful for testing because it:

- **Doesn't require Iceoryx2 IPC** - Works anywhere Python works
- **Generates realistic market data** - Synthetic trades and depth updates with configurable volatility
- **Simulates latencies** - Includes realistic feed and order latencies
- **Is deterministic** - Can seed the random generator for reproducible tests

Basic Usage:

.. code-block:: python

    from hftbacktest.live import StubConnectorBot

    # Create stub bot with seed for reproducibility
    bot = StubConnectorBot(base_price=50000.0, seed=42)

    # Use exactly like a real bot
    bot.wait_next_feed(include_order_resp=False, timeout=10_000_000_000)

    # Get synthetic data
    depth = bot.depth(0)
    trades = bot.last_trades(0)

    bot.close()

Testing Your Strategy with Stub
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can easily write tests for your strategy using the stub:

.. code-block:: python

    import unittest
    from hftbacktest.live import LiveClient, StubConnectorBot

    class TestMyStrategy(unittest.TestCase):
        def test_strategy_logic(self):
            bot = StubConnectorBot(seed=42)
            
            with LiveClient(bot) as client:
                # Run your strategy
                for _ in range(100):
                    trade = client.get_trade_nowait()
                    if trade:
                        # Test your logic
                        assert trade.price > 0
            
            # Assertions
            self.assertTrue(True)  # Replace with actual test

Customizing the Example
-----------------------

Command-Line Options
~~~~~~~~~~~~~~~~~~~~

.. code-block:: console

    python examples/python_live_connector.py --help

Options:

- ``--stub`` - Use stub connector instead of real connector (default: False)
- ``--duration <seconds>`` - How long to run (default: 10)

Extending for Your Strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To build on this example:

1. **Add order submission logic** in the main loop
2. **Add strategy calculations** based on market data
3. **Add risk management** (position limits, max loss, etc.)
4. **Add performance tracking** (P&L, Sharpe ratio, etc.)

See ``examples/live_trading_example.py`` for a more complex strategy implementation.

Troubleshooting
---------------

**"Live features not available" error:**

Make sure to build with the ``live`` feature:

.. code-block:: console

    maturin develop --manifest-path py-hftbacktest/Cargo.toml --features live

**Stub bot generates no data:**

This is normal behavior - the stub generates data probabilistically. Run for longer or check that you're polling with ``get_trade_nowait()`` etc.

**Connection timeout with real connector:**

1. Verify the connector is running: ``./target/release/connector binancefutures BTCUSDT config.toml``
2. Check configuration file is correct
3. Verify Iceoryx2 is properly installed
4. Check system requirements (Linux 4.19+, macOS 10.15+)

Related Documentation
---------------------

- :doc:`python_connector_setup` - Complete connector setup guide
- `LiveClient API Reference <../py-hftbacktest/hftbacktest/live/README.md>`_
- `StubConnectorBot Module <../py-hftbacktest/hftbacktest/live/stub.py>`_

See Also
--------

- ``examples/live_trading_example.py`` - More complex market making strategy
- ``py-hftbacktest/tests/test_python_live_connector_example.py`` - Example tests
- ``py-hftbacktest/tests/test_live_client.py`` - LiveClient unit tests
