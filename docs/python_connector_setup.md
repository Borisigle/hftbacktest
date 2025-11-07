Python Connector Setup Guide
=============================

This guide explains how to set up and use the PyO3 connector bridge for live trading with HftBacktest. The connector allows you to run trading strategies in Python while leveraging high-performance Rust connectors for exchange connectivity.

Overview
--------

The live trading system consists of two main components:

1. **Connector Binary** (Rust): Handles exchange connectivity and publishes market data/order events via shared memory
2. **Python Bot**: Consumes events from shared memory and executes your trading strategy

The bridge uses `Iceoryx2` for zero-copy inter-process communication (IPC) between the connector and Python bot.

Available Features
------------------

When the ``live`` feature is enabled, the following PyO3 bindings become available:

**Live Instruments:**
- ``LiveInstrument`` - Defines a live trading instrument configuration

**Live Bot Builders:**
- ``build_hashmap_livebot`` - Creates a live bot with HashMap-based market depth
- ``build_roivec_livebot`` - Creates a live bot with ROI Vector-based market depth

**Live Bot Classes:**
- ``HashMapMarketDepthLiveBot`` - Live bot using HashMap market depth structure
- ``ROIVectorMarketDepthLiveBot`` - Live bot using ROI Vector market depth structure

Prerequisites
-------------

System Requirements
~~~~~~~~~~~~~~~~~~~

**Linux:**
- Kernel 4.19+ for Iceoryx2 support
- libclang development packages (required by bindgen)

**macOS:**
- macOS 10.15+ for Iceoryx2 support
- Xcode command line tools

**Python:**
- Python 3.11+
- Maturin (for building the wheel)

Installing Dependencies
~~~~~~~~~~~~~~~~~~~~~~~

**Ubuntu/Debian:**

.. code-block:: console

    sudo apt update
    sudo apt install -y \
        build-essential \
        pkg-config \
        libssl-dev \
        clang \
        libclang-dev

**macOS:**

.. code-block:: console

    xcode-select --install

**Python Dependencies:**

.. code-block:: console

    # Create virtual environment (recommended)
    python3 -m venv hftbt-env
    source hftbt-env/bin/activate  # On Windows: hftbt-env\Scripts\activate

    # Install dependencies
    pip install maturin numpy numba

Building the Components
------------------------

1. Build the Connector Binary
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First, build the connector crate with your desired exchange features:

.. code-block:: console

    # Build with all connectors (default)
    cargo build --release --manifest-path connector/Cargo.toml

    # Or build specific connectors
    cargo build --release --manifest-path connector/Cargo.toml --features binancefutures
    cargo build --release --manifest-path connector/Cargo.toml --features bybit

The connector binary will be available at:
``target/release/connector``

2. Build the Python Wheel with Live Features
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Build the ``py-hftbacktest`` wheel with the ``live`` feature enabled:

.. code-block:: console

    # Build with live features
    maturin develop --manifest-path py-hftbacktest/Cargo.toml --features live

    # Or build a release wheel
    maturin build --release --manifest-path py-hftbacktest/Cargo.toml --features live

    # Install the built wheel
    pip install target/wheels/hftbacktest-*.whl

Configuration
-------------

1. Connector Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create configuration files for your desired exchanges. See the examples in ``connector/examples/``:

**Binance Futures (``binancefutures.toml``):**

.. code-block:: toml

    # Testnet: wss://fstream.binancefuture.com/ws
    # Mainnet: wss://fstream.binance.com/ws
    # Private: wss://fstream-auth.binance.com/ws
    # Low-Latency Market Maker: wss://fstream-mm.binance.com/ws
    stream_url = "wss://fstream.binancefuture.com/ws"

    # Testnet: https://testnet.binancefuture.com
    # Mainnet: https://fapi.binance.com
    # Low-Latency Market Maker: https://fapi-mm.binance.com
    api_url = "https://testnet.binancefuture.com"

    order_prefix = "test"
    api_key = "your_api_key"
    secret = "your_secret"

**Bybit (``bybit.toml``):**

.. code-block:: toml

    # Testnet URLs
    public_url = "wss://stream-testnet.bybit.com/v5/public/linear"
    private_url = "wss://stream-testnet.bybit.com/v5/private"
    trade_url = "wss://stream-testnet.bybit.com/v5/trade"
    rest_url = "https://api-testnet.bybit.com"

    # Linear futures
    category = "linear"

    order_prefix = "test"
    api_key = "your_api_key"
    secret = "your_secret"

2. Python Strategy Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure your live trading instruments using ``LiveInstrument``:

.. code-block:: python

    from hftbacktest import LiveInstrument, ROIVectorMarketDepthLiveBot

    # Create instrument for Binance Futures
    instrument = (
        LiveInstrument()
        .connector("binancefutures")
        .symbol("BTCUSDT")
        .tick_size(0.1)
        .lot_size(0.001)
        .last_trades_capacity(1000)
        # Optional: Set ROI bounds for ROIVectorMarketDepth
        .roi_lb(20000.0)  # Lower bound price
        .roi_ub(100000.0)  # Upper bound price
    )

    # Build live bot
    hbt = ROIVectorMarketDepthLiveBot([instrument])

Running the System
------------------

Startup Order
~~~~~~~~~~~~~

The connector must be started **before** the Python bot:

1. **Start the Connector Binary:**

.. code-block:: console

    # Binance Futures connector
    ./target/release/connector binancefutures connector_name path/to/binancefutures.toml

    # Bybit connector
    ./target/release/connector bybit connector_name path/to/bybit.toml

    # Binance Spot connector
    ./target/release/connector binancespot connector_name path/to/binancespot.toml

2. **Run your Python Strategy:**

.. code-block:: python

    import numpy as np
    from numba import njit
    from hftbacktest import (
        LiveInstrument, 
        ROIVectorMarketDepthLiveBot,
        BUY, SELL, LIMIT, GTC
    )

    @njit
    def market_making_strategy(hbt):
        """Simple market making strategy"""
        asset_no = 0
        
        while True:
            # Clear inactive orders
            hbt.clear_inactive_orders(asset_no)
            
            # Get current market depth
            depth = hbt.depth(asset_no)
            
            # Place orders at best bid/ask with small spread
            mid_price = (depth.best_bid + depth.best_ask) / 2.0
            spread = 0.1  # 0.1 USD spread
            
            bid_price = mid_price - spread
            ask_price = mid_price + spread
            order_qty = 0.001
            
            # Submit buy order
            order_id = int(hbt.current_timestamp())
            result = hbt.submit_buy_order(
                asset_no, order_id, bid_price, order_qty, 
                GTC, LIMIT, wait=False
            )
            
            # Submit sell order
            order_id += 1
            result = hbt.submit_sell_order(
                asset_no, order_id, ask_price, order_qty,
                GTC, LIMIT, wait=False
            )
            
            # Wait for next market data
            if hbt.wait_next_feed(include_resp=True, timeout=10_000_000_000) != 0:
                break

    def main():
        # Configure live instrument
        instrument = (
            LiveInstrument()
            .connector("binancefutures")
            .symbol("BTCUSDT")
            .tick_size(0.1)
            .lot_size(0.001)
            .last_trades_capacity(1000)
        )
        
        # Build live bot
        hbt = ROIVectorMarketDepthLiveBot([instrument])
        
        # Run strategy
        market_making_strategy(hbt)
        
        # Clean up
        hbt.close()

    if __name__ == "__main__":
        main()

Available Connectors
-------------------

**Supported Exchanges:**
- ``binancefutures`` - Binance USD-m Futures
- ``binancespot`` - Binance Spot  
- ``bybit`` - Bybit Linear Futures

**Connector CLI Arguments:**

.. code-block:: console

    connector <NAME> <CONNECTOR_TYPE> <CONFIG_FILE>

Arguments:
- ``NAME``: Unique identifier for the connector instance (used by Python bot to connect)
- ``CONNECTOR_TYPE``: One of ``binancefutures``, ``binancespot``, ``bybit``
- ``CONFIG_FILE``: Path to the connector configuration file

Shared Memory Constraints
------------------------

**Iceoryx2 Configuration:**

The system uses Iceoryx2 for high-performance IPC. Key constraints:

- **Memory Usage**: Iceoryx2 allocates shared memory segments for communication
- **Process Lifetime**: Both connector and bot must run concurrently
- **Permissions**: Sufficient shared memory permissions (typically no issue on modern Linux/macOS)

**Monitoring Shared Memory:**

.. code-block:: console

    # List Iceoryx2 services (Linux)
    ipcs -m

    # Check for Iceoryx2 processes
    ps aux | grep connector

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**1. Live Features Not Available:**

.. code-block:: python

    # Check if live features are available
    import hftbacktest
    print(hasattr(hftbacktest, 'build_hashmap_livebot'))  # Should be True

**Solution:** Rebuild the wheel with ``--features live``

**2. Iceoryx2 Connection Issues:**

.. code-block:: console

    # Error: "Failed to create Iceoryx service"
    # Solution: Check if connector is running and using correct name

    # Error: "Permission denied" 
    # Solution: Check shared memory permissions

**3. Connector Fails to Start:**

.. code-block:: console

    # Check configuration file syntax
    ./target/release/connector --help

    # Verify API credentials and URLs
    # Check network connectivity to exchange endpoints

**4. Python Bot Can't Connect:**

- Ensure connector is running **before** starting the Python bot
- Verify the connector name matches between CLI and Python configuration
- Check that both processes are running on the same machine

**5. Memory Issues:**

.. code-block:: console

    # Monitor shared memory usage
    watch -n 1 'ipcs -m'

    # Clean up Iceoryx2 resources if needed
    # (Usually automatic on process termination)

Debugging Tips
~~~~~~~~~~~~~~

**Enable Debug Logging:**

.. code-block:: console

    # Set log level for connector
    RUST_LOG=debug ./target/release/connector binancefutures test_name config.toml

**Python Debugging:**

.. code-block:: python

    # Check live feature availability
    import hftbacktest
    print("Live feature available:", hftbacktest.LIVE_FEATURE)

    # Verify instrument configuration
    instrument = LiveInstrument().connector("binancefutures").symbol("BTCUSDT")
    print("Instrument configured:", instrument.connector_name, instrument.symbol)

**Verification Steps:**

1. Build connector binary successfully
2. Build Python wheel with live features
3. Start connector with valid configuration
4. Run simple Python connection test
5. Verify market data reception
6. Test order submission (use testnet first!)

Performance Considerations
--------------------------

**Shared Memory IPC:**
- Zero-copy data transfer between connector and Python bot
- Latency typically < 100μs for market data delivery
- Suitable for high-frequency trading strategies

**Python Numba JIT:**
- Compile trading strategy with ``@njit`` for optimal performance
- Avoid Python objects in hot paths
- Use NumPy arrays for data processing

**Resource Usage:**
- Monitor shared memory usage with multiple instruments
- Consider using ROI Vector market depth for price-bounded strategies
- Adjust ``last_trades_capacity`` based on strategy needs

Security Considerations
----------------------

**API Credentials:**
- Store API keys and secrets securely (environment variables, key management)
- Use testnet APIs for development and testing
- Implement proper IP allowlisting if required by exchange

**Network Security:**
- Use WSS (WebSocket Secure) endpoints in production
- Consider VPN or dedicated connections for low-latency requirements
- Monitor for unauthorized API usage

Examples
--------

See the ``examples/`` directory for complete working examples:

- ``examples/example.py`` - Basic backtesting example
- ``examples/example_bybit.py`` - Bybit data processing example
- ``hftbacktest/examples/gridtrading_live.rs`` - Rust live trading example

For more detailed tutorials and advanced usage, see the main documentation at:
https://hftbacktest.readthedocs.io/