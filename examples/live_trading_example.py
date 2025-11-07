#!/usr/bin/env python3
"""
Example of live trading with HftBacktest Python connector.
This demonstrates how to set up a simple market making strategy using the live connector.

Prerequisites:
1. Build the connector: cargo build --release --manifest-path connector/Cargo.toml
2. Build Python wheel: maturin develop --manifest-path py-hftbacktest/Cargo.toml --features live
3. Start connector: ./target/release/connector binancefutures test_binance connector/examples/binancefutures.toml
4. Run this script: python examples/live_trading_example.py

Note: Use testnet credentials in the configuration file for testing.
"""

import sys
import time
import numpy as np
from numba import njit
from typing import Optional

try:
    import hftbacktest
    from hftbacktest import (
        LiveInstrument,
        HashMapMarketDepthLiveBot,
        BUY, SELL, LIMIT, GTC
    )
    LIVE_AVAILABLE = True
except ImportError as e:
    print(f"Live features not available: {e}")
    print("Please build with: maturin develop --features live")
    LIVE_AVAILABLE = False

@njit
def simple_market_making(hbt, max_position: float = 0.01, order_qty: float = 0.001):
    """
    Simple market making strategy for live trading.
    
    Args:
        hbt: Live bot instance
        max_position: Maximum position size in base currency
        order_qty: Order quantity in base currency
    """
    asset_no = 0
    
    print(f"Starting market making for asset {asset_no}")
    
    # Strategy parameters
    target_spread_bps = 10  # 10 basis points spread
    min_order_age_ns = 100_000_000  # 100ms minimum order age
    
    order_id = int(time.time() * 1_000_000_000)  # Use timestamp as base
    
    while True:
        try:
            # Clear inactive orders
            hbt.clear_inactive_orders(asset_no)
            
            # Get current position
            position = hbt.position(asset_no)
            
            # Get current market depth
            depth = hbt.depth(asset_no)
            
            if depth.best_bid <= 0 or depth.best_ask <= 0:
                # Market data not ready, wait
                if hbt.wait_next_feed(include_resp=True, timeout=1_000_000_000) != 0:
                    print("Timeout waiting for market data")
                    break
                continue
            
            # Calculate mid price and spread
            mid_price = (depth.best_bid + depth.best_ask) / 2.0
            current_spread = depth.best_ask - depth.best_bid
            tick_size = depth.tick_size
            
            # Calculate target prices based on position
            if abs(position) < max_position:
                # Can place both sides
                spread_offset = max(target_spread_bps * mid_price / 10000, tick_size * 2)
                
                if position > 0:  # Long position, skew ask lower
                    bid_price = mid_price - spread_offset / 2
                    ask_price = mid_price + spread_offset / 2 - tick_size
                elif position < 0:  # Short position, skew bid higher
                    bid_price = mid_price - spread_offset / 2 + tick_size
                    ask_price = mid_price + spread_offset / 2
                else:  # Neutral position
                    bid_price = mid_price - spread_offset / 2
                    ask_price = mid_price + spread_offset / 2
            else:
                # At max position, only place orders that reduce position
                if position > 0:  # Long, only place ask orders
                    bid_price = -1  # Don't place bid
                    ask_price = mid_price + tick_size
                else:  # Short, only place bid orders
                    bid_price = mid_price - tick_size  
                    ask_price = -1  # Don't place ask
            
            # Cancel existing orders and place new ones
            orders = hbt.orders(asset_no)
            
            # Place new orders
            if bid_price > 0:
                order_id += 1
                result = hbt.submit_buy_order(
                    asset_no, order_id, bid_price, order_qty,
                    GTC, LIMIT, wait=False
                )
                if result == 0:
                    print(f"Placed buy order: {order_id} @ {bid_price:.2f}")
                else:
                    print(f"Failed to place buy order: {result}")
            
            if ask_price > 0:
                order_id += 1
                result = hbt.submit_sell_order(
                    asset_no, order_id, ask_price, order_qty,
                    GTC, LIMIT, wait=False
                )
                if result == 0:
                    print(f"Placed sell order: {order_id} @ {ask_price:.2f}")
                else:
                    print(f"Failed to place sell order: {result}")
            
            # Wait for next market data or order response
            wait_result = hbt.wait_next_feed(include_resp=True, timeout=5_000_000_000)
            
            if wait_result == 1:  # End of data
                print("End of data received")
                break
            elif wait_result == 2:  # Market feed
                current_time = hbt.current_timestamp()
                print(f"Market data at {time.strftime('%H:%M:%S', time.localtime(current_time/1_000_000_000))}")
            elif wait_result == 3:  # Order response
                print("Order response received")
            elif wait_result != 0:
                print(f"Unexpected wait result: {wait_result}")
                
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
            break
        except Exception as e:
            print(f"Error in strategy: {e}")
            break
    
    print("Market making stopped")
    return True

def main():
    """Main function to set up and run the live trading example."""
    if not LIVE_AVAILABLE:
        print("Live trading features not available. Please check your build.")
        sys.exit(1)
    
    print("HftBacktest Live Trading Example")
    print("=" * 40)
    
    # Configure live instrument
    print("Configuring live instrument...")
    instrument = (
        LiveInstrument()
        .connector("binancefutures")  # Must match connector type
        .symbol("BTCUSDT")          # Trading symbol
        .tick_size(0.1)             # Minimum price increment
        .lot_size(0.001)            # Minimum quantity
        .last_trades_capacity(100)   # Number of recent trades to keep
    )
    
    print(f"Instrument configuration:")
    print(f"  Connector: {instrument.connector_name}")
    print(f"  Symbol: {instrument.symbol}")
    print(f"  Tick size: {instrument.tick_size}")
    print(f"  Lot size: {instrument.lot_size}")
    
    try:
        # Build live bot
        print("\nBuilding live bot...")
        hbt = HashMapMarketDepthLiveBot([instrument])
        print("✓ Live bot created successfully")
        
        # Run the strategy
        print("\nStarting market making strategy...")
        print("Press Ctrl+C to stop")
        print("-" * 40)
        
        result = simple_market_making(hbt)
        
        if result:
            print("\nStrategy completed successfully")
        else:
            print("\nStrategy encountered errors")
            
        # Clean up
        print("Closing live bot...")
        close_result = hbt.close()
        if close_result == 0:
            print("✓ Live bot closed successfully")
        else:
            print(f"✗ Error closing live bot: {close_result}")
            
    except Exception as e:
        print(f"✗ Error setting up live trading: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()