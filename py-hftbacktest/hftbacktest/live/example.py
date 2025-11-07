#!/usr/bin/env python3
"""
Example usage of the Live Trading Client.

This example requires:
1. Building with the live feature: maturin develop --features live
2. Running a connector binary first: ./target/release/connector binancefutures BTCUSDT config.toml
"""

import time
import asyncio
from hftbacktest import LiveInstrument, HashMapMarketDepthLiveBot
from hftbacktest.live import LiveClient, Side


def sync_example():
    """Synchronous trading example."""
    print("=== Synchronous Example ===")
    
    instrument = LiveInstrument("BTCUSDT")
    instrument.tick_size(0.01)
    instrument.lot_size(0.001)
    
    bot = HashMapMarketDepthLiveBot([instrument])
    
    with LiveClient(bot) as client:
        print(f"Connected with {client.num_assets} asset(s)")
        
        for i in range(10):
            trade = client.get_trade_nowait()
            if trade:
                print(f"Trade: {trade.side.name} {trade.qty} @ {trade.price}")
            
            book = client.get_book_update_nowait()
            if book:
                print(f"Book: {book.bid_price} ({book.bid_qty}) / {book.ask_price} ({book.ask_qty})")
            
            health = client.health
            print(f"Health: connected={health.connected}, feed_latency={health.feed_latency_ns}ns")
            
            time.sleep(1.0)
        
        response = client.submit_order(
            side=Side.BUY,
            price=50000.0,
            qty=0.001,
            asset_no=0
        )
        
        if response.error:
            print(f"Order error: {response.error}")
        else:
            print(f"Order submitted: {response.order_id}")
            
            time.sleep(1.0)
            
            cancel_response = client.cancel_order(response.order_id)
            print(f"Order cancelled: {cancel_response.status}")
        
        position = client.get_position(asset_no=0)
        print(f"Position: {position}")
        
        orders = client.get_orders(asset_no=0)
        print(f"Active orders: {len(orders)}")


async def async_example():
    """Asynchronous trading example."""
    print("\n=== Asynchronous Example ===")
    
    instrument = LiveInstrument("BTCUSDT")
    instrument.tick_size(0.01)
    instrument.lot_size(0.001)
    
    bot = HashMapMarketDepthLiveBot([instrument])
    
    async def trade_handler(client):
        print("Trade handler started")
        for _ in range(5):
            trade = await client.get_trade(timeout=2.0)
            if trade:
                print(f"[TRADE] {trade.side.name} {trade.qty} @ {trade.price}")
    
    async def book_handler(client):
        print("Book handler started")
        for _ in range(5):
            book = await client.get_book_update(timeout=2.0)
            if book:
                spread = book.ask_price - book.bid_price
                print(f"[BOOK] Spread: {spread}, Mid: {(book.bid_price + book.ask_price) / 2}")
    
    async def order_handler(client):
        print("Order handler started")
        await asyncio.sleep(2.0)
        
        response = client.submit_order(
            side=Side.BUY,
            price=50000.0,
            qty=0.001
        )
        
        if response.error:
            print(f"[ORDER] Error: {response.error}")
        else:
            print(f"[ORDER] Submitted: {response.order_id}")
            await asyncio.sleep(1.0)
            cancel = client.cancel_order(response.order_id)
            print(f"[ORDER] Cancelled: {cancel.status}")
    
    with LiveClient(bot) as client:
        await asyncio.gather(
            trade_handler(client),
            book_handler(client),
            order_handler(client)
        )


def callback_example():
    """Example with connection callbacks."""
    print("\n=== Callback Example ===")
    
    def on_connection_lost():
        print("⚠️  Connection lost!")
    
    def on_error(exc):
        print(f"❌ Error: {exc}")
    
    instrument = LiveInstrument("BTCUSDT")
    instrument.tick_size(0.01)
    instrument.lot_size(0.001)
    
    bot = HashMapMarketDepthLiveBot([instrument])
    
    client = LiveClient(
        bot,
        health_check_interval=1.0,
        on_connection_lost=on_connection_lost,
        on_error=on_error
    )
    
    try:
        client.start()
        print("Client started")
        
        for i in range(10):
            health = client.health
            status = "✓" if health.connected else "✗"
            print(f"{status} Health check {i+1}/10: connected={health.connected}")
            time.sleep(1.0)
    
    finally:
        client.close()
        print("Client closed")


if __name__ == '__main__':
    import sys
    
    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'async':
            asyncio.run(async_example())
        elif len(sys.argv) > 1 and sys.argv[1] == 'callback':
            callback_example()
        else:
            sync_example()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
