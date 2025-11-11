#!/usr/bin/env python3
"""
Example demonstrating the ConnectorRunner utility for managing connector lifecycle.

This example shows how to use the ConnectorRunner to automatically build, start,
and manage the Rust connector binary that streams market data via Iceoryx2.

The ConnectorRunner handles:
- Building the connector if the binary is missing
- Starting the process with the specified configuration
- Health checks to ensure Iceoryx channels are available
- Graceful shutdown with proper signal handling
- Error reporting and logging

Usage:
    # Automatic (builds and starts connector automatically):
    python examples/connector_runner_example.py
    
    # With custom config:
    python examples/connector_runner_example.py --config path/to/config.toml
    
    # For a different exchange:
    python examples/connector_runner_example.py --connector bybit --config connector/examples/bybit.toml
"""

import sys
import time
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_with_connector_runner(
    connector_name: str = "binancefutures",
    connector_type: str = "binancefutures",
    config_path: Path = None,
    duration: int = 30
):
    """
    Run a trading bot with automated connector management.
    
    Args:
        connector_name: Unique name for the connector instance
        connector_type: Type of connector (binancefutures, binancespot, bybit)
        config_path: Path to the connector configuration file
        duration: How long to run in seconds
    """
    from hftbacktest.live import (
        ConnectorRunner,
        ConnectorConfig,
        ConnectorBuildError,
        ConnectorStartupError,
        ConnectorNotFoundError
    )
    
    # Set default config path if not provided
    if config_path is None:
        config_path = Path(f"connector/examples/{connector_type}.toml")
    
    logger.info("=" * 60)
    logger.info("Connector Runner Example")
    logger.info("=" * 60)
    logger.info(f"Connector Name: {connector_name}")
    logger.info(f"Connector Type: {connector_type}")
    logger.info(f"Config Path: {config_path}")
    logger.info(f"Duration: {duration}s")
    logger.info("=" * 60)
    
    # Configure the connector
    config = ConnectorConfig(
        connector_name=connector_name,
        connector_type=connector_type,
        config_path=config_path,
        auto_build=True,           # Build if binary is missing
        startup_timeout=15.0,      # Wait up to 15s for startup
        shutdown_timeout=5.0,      # Wait up to 5s for shutdown
        capture_output=True,       # Capture logs
        env={"RUST_LOG": "info"}   # Set Rust logging level
    )
    
    try:
        # Use ConnectorRunner as a context manager
        # This automatically:
        # 1. Builds the connector if missing
        # 2. Starts the process
        # 3. Waits for Iceoryx channels to be ready
        # 4. Stops the process on exit
        with ConnectorRunner(config) as runner:
            logger.info(f"✓ Connector is running (PID: {runner.process.pid})")
            logger.info("")
            
            # Now we can create our bot and connect to the running connector
            try:
                import hftbacktest
                from hftbacktest import LiveInstrument, HashMapMarketDepthLiveBot
                from hftbacktest.live import LiveClient
                
                # Configure live instrument (must match connector name)
                instrument = (
                    LiveInstrument()
                    .connector(connector_name)
                    .symbol("BTCUSDT")  # Adjust based on your config
                    .tick_size(0.1)
                    .lot_size(0.001)
                    .last_trades_capacity(100)
                )
                
                # Create the bot
                bot = HashMapMarketDepthLiveBot([instrument])
                
                # Use LiveClient to interact with the bot
                with LiveClient(bot) as client:
                    logger.info("✓ Bot connected to connector")
                    logger.info(f"  Timestamp: {client.current_timestamp}")
                    logger.info(f"  Assets: {client.num_assets}")
                    logger.info("")
                    
                    start_time = time.time()
                    trades_count = 0
                    depth_updates = 0
                    
                    logger.info("Collecting market data...")
                    logger.info("-" * 60)
                    
                    while time.time() - start_time < duration:
                        # Collect trades
                        trade = client.get_trade_nowait()
                        if trade:
                            trades_count += 1
                            if trades_count % 10 == 0:
                                logger.info(
                                    f"Trade #{trades_count}: "
                                    f"{trade.side.name} {trade.qty} @ {trade.price}"
                                )
                        
                        # Collect depth updates
                        book = client.get_book_update_nowait()
                        if book:
                            depth_updates += 1
                        
                        # Check connection health
                        health = client.health
                        if not health.connected:
                            logger.warning("Connection lost!")
                            break
                        
                        time.sleep(0.01)  # Avoid busy waiting
                    
                    elapsed = time.time() - start_time
                    logger.info("-" * 60)
                    logger.info(f"Completed collection after {elapsed:.1f}s")
                    logger.info(f"  Total Trades: {trades_count}")
                    logger.info(f"  Depth Updates: {depth_updates}")
                    logger.info(f"  Trades/sec: {trades_count/elapsed:.2f}")
                    
            except ImportError as e:
                logger.error(
                    f"Live features not available: {e}\n"
                    "Build with: maturin develop --manifest-path py-hftbacktest/Cargo.toml --features live"
                )
                return False
            
            logger.info("")
            logger.info("Stopping connector...")
        
        logger.info("✓ Connector stopped gracefully")
        return True
        
    except ConnectorBuildError as e:
        logger.error(f"✗ Failed to build connector: {e}")
        return False
    except ConnectorStartupError as e:
        logger.error(f"✗ Connector failed to start: {e}")
        return False
    except ConnectorNotFoundError as e:
        logger.error(f"✗ Connector binary not found: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Example of using ConnectorRunner for automated connector management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--connector-name",
        default="binancefutures",
        help="Unique name for the connector instance (default: binancefutures)"
    )
    parser.add_argument(
        "--connector-type",
        default="binancefutures",
        choices=["binancefutures", "binancespot", "bybit"],
        help="Type of connector to launch (default: binancefutures)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to connector configuration file (default: connector/examples/<type>.toml)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration to run in seconds (default: 30)"
    )
    
    args = parser.parse_args()
    
    try:
        success = run_with_connector_runner(
            connector_name=args.connector_name,
            connector_type=args.connector_type,
            config_path=args.config,
            duration=args.duration
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
