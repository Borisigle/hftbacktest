#!/usr/bin/env python3
"""
Example of using the LiveClient wrapper to subscribe to connector feeds and collect statistics.

This example demonstrates:
1. Setting up a LiveInstrument configuration
2. Creating a live bot connected to a connector process
3. Subscribing to trades and depth updates
4. Collecting and reporting aggregated market statistics

Prerequisites for real connector:
1. Build connector: cargo build --release --manifest-path connector/Cargo.toml --features binancefutures
2. Build Python wheel: maturin develop --manifest-path py-hftbacktest/Cargo.toml --features live
3. Start connector: ./target/release/connector binancefutures <symbol> connector/examples/binancefutures.toml
4. Run this script: python examples/python_live_connector.py

For testing with a stub (no connector required):
   python examples/python_live_connector.py --stub

Documentation:
- To swap the stub for a real connector, simply remove the --stub flag and ensure the connector
  process is running. The LiveClient will automatically connect via Iceoryx2 IPC.
- See py-hftbacktest/hftbacktest/live/README.md for more details on the LiveClient API.
"""

import sys
import time
import argparse
from dataclasses import dataclass
from typing import Optional, Dict
from collections import defaultdict


@dataclass
class MarketStatistics:
    """Aggregated market statistics."""
    total_trades: int = 0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    trades_per_second: float = 0.0
    last_bid: Optional[float] = None
    last_ask: Optional[float] = None
    spread: Optional[float] = None
    max_spread: Optional[float] = None
    min_spread: Optional[float] = None
    depth_updates: int = 0
    
    @property
    def total_volume(self) -> float:
        return self.buy_volume + self.sell_volume
    
    def __str__(self) -> str:
        lines = [
            "=" * 60,
            "Market Statistics",
            "=" * 60,
            f"Total Trades:        {self.total_trades:,}",
            f"Total Volume:        {self.total_volume:.4f}",
            f"  Buy Volume:        {self.buy_volume:.4f}",
            f"  Sell Volume:       {self.sell_volume:.4f}",
            f"Trades/Second:       {self.trades_per_second:.2f}",
            f"Last Bid:            {self.last_bid:.2f}" if self.last_bid else "Last Bid:            N/A",
            f"Last Ask:            {self.last_ask:.2f}" if self.last_ask else "Last Ask:            N/A",
            f"Current Spread:      {self.spread:.4f}" if self.spread else "Current Spread:      N/A",
            f"Max Spread:          {self.max_spread:.4f}" if self.max_spread else "Max Spread:          N/A",
            f"Min Spread:          {self.min_spread:.4f}" if self.min_spread else "Min Spread:          N/A",
            f"Depth Updates:       {self.depth_updates:,}",
            "=" * 60,
        ]
        return "\n".join(lines)


def get_stub_bot():
    """Create a stub bot for testing without a real connector."""
    from hftbacktest.live import StubConnectorBot
    return StubConnectorBot()


def get_real_bot():
    """Create a real bot connected to a connector process."""
    try:
        import hftbacktest
        from hftbacktest import LiveInstrument, HashMapMarketDepthLiveBot
        
        # Configure live instrument
        # Note: Symbol should match the connector configuration
        instrument = (
            LiveInstrument()
            .connector("binancefutures")
            .symbol("BTCUSDT")
            .tick_size(0.1)
            .lot_size(0.001)
            .last_trades_capacity(100)
        )
        
        # Create the low-level bot
        bot = HashMapMarketDepthLiveBot([instrument])
        return bot
        
    except Exception as e:
        print(f"Error creating real bot: {e}")
        raise


def run_connector_example(use_stub: bool = False, duration: int = 10):
    """
    Run the connector example.
    
    Args:
        use_stub: If True, use a stub bot instead of a real connector
        duration: How long to run (in seconds)
    """
    print("HftBacktest Live Connector Example")
    print("=" * 60)
    
    if use_stub:
        print("Using STUB connector (no real connector required)")
        bot = get_stub_bot()
    else:
        print("Connecting to REAL connector")
        print("Make sure to start the connector process first:")
        print("  ./target/release/connector binancefutures BTCUSDT config.toml")
        bot = get_real_bot()
    
    print()
    
    try:
        from hftbacktest.live import LiveClient
        
        # Create high-level client wrapper
        with LiveClient(bot) as client:
            print("✓ LiveClient connected")
            print(f"  Timestamp: {client.current_timestamp}")
            print(f"  Assets: {client.num_assets}")
            print()
            
            # Initialize statistics
            stats = MarketStatistics()
            start_time = time.time()
            last_print_time = start_time
            
            print("Collecting market data... Press Ctrl+C to stop")
            print("-" * 60)
            
            while time.time() - start_time < duration:
                # Collect trades
                trade = client.get_trade_nowait()
                if trade:
                    stats.total_trades += 1
                    if trade.side.name == "BUY":
                        stats.buy_volume += trade.qty
                    else:
                        stats.sell_volume += trade.qty
                
                # Collect book updates
                book = client.get_book_update_nowait()
                if book:
                    stats.depth_updates += 1
                    stats.last_bid = book.bid_price
                    stats.last_ask = book.ask_price
                    
                    if book.bid_price > 0 and book.ask_price > 0:
                        spread = book.ask_price - book.bid_price
                        stats.spread = spread
                        
                        if stats.max_spread is None or spread > stats.max_spread:
                            stats.max_spread = spread
                        if stats.min_spread is None or spread < stats.min_spread:
                            stats.min_spread = spread
                
                # Periodically print statistics
                current_time = time.time()
                if current_time - last_print_time >= 2:
                    elapsed = current_time - start_time
                    stats.trades_per_second = stats.total_trades / elapsed if elapsed > 0 else 0
                    
                    print(f"\n[{elapsed:.1f}s] Live market data:")
                    print(f"  Trades: {stats.total_trades}")
                    print(f"  Volume: {stats.total_volume:.4f}")
                    print(f"  Bid: {stats.last_bid:.2f} Ask: {stats.last_ask:.2f}" 
                          if stats.last_bid and stats.last_ask else "  Book: Not ready")
                    
                    last_print_time = current_time
                
                # Check connection health
                health = client.health
                if not health.connected and stats.total_trades > 0:
                    print("\n✗ Connection lost!")
                    break
                
                time.sleep(0.01)  # Small sleep to avoid busy-waiting
            
            print("\n" + "-" * 60)
            
            # Final statistics
            elapsed = time.time() - start_time
            stats.trades_per_second = stats.total_trades / elapsed if elapsed > 0 else 0
            print(stats)
            
            print(f"Example completed successfully (duration: {elapsed:.1f}s)")
            return True
            
    except KeyboardInterrupt:
        print("\n\nKeyboard interrupt received")
        return True
    except Exception as e:
        print(f"\n✗ Error during example: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="HftBacktest Live Connector Example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        help="Use stub connector for testing (default: connect to real connector)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Duration to run in seconds (default: 10)"
    )
    
    args = parser.parse_args()
    
    try:
        success = run_connector_example(use_stub=args.stub, duration=args.duration)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
