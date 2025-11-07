import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import threading
import time
import asyncio
from queue import Queue


class MockBot:
    def __init__(self):
        self.num_assets = 1
        self.current_timestamp = 1234567890000000000
        self._position = 0.0
        self._closed = False
        self._feed_count = 0
        self._last_trades = []
        self._orders = {}
        self._depth = None
        
    def wait_next_feed(self, include_order_resp, timeout):
        if self._closed:
            return 1
        
        self._feed_count += 1
        if self._feed_count <= 5:
            return 2
        
        time.sleep(0.01)
        return 0
    
    def last_trades(self, asset_no):
        return self._last_trades
    
    def clear_last_trades(self, asset_no):
        self._last_trades = []
    
    def depth(self, asset_no):
        if self._depth is None:
            self._depth = MockDepth()
        return self._depth
    
    def position(self, asset_no):
        return self._position
    
    def orders(self, asset_no):
        return MockOrderDict(self._orders)
    
    def submit_buy_order(self, asset_no, order_id, price, qty, time_in_force, order_type, wait):
        self._orders[order_id] = {
            'order_id': order_id,
            'side': 1,
            'price': price,
            'qty': qty
        }
        return 0
    
    def submit_sell_order(self, asset_no, order_id, price, qty, time_in_force, order_type, wait):
        self._orders[order_id] = {
            'order_id': order_id,
            'side': -1,
            'price': price,
            'qty': qty
        }
        return 0
    
    def cancel(self, asset_no, order_id, wait):
        if order_id in self._orders:
            del self._orders[order_id]
            return 0
        return 12
    
    def feed_latency(self, asset_no):
        return (1234567890000000000, 1234567890100000000)
    
    def order_latency(self, asset_no):
        return (1234567890000000000, 1234567890050000000, 1234567890100000000)
    
    def close(self):
        self._closed = True
        return 0


class MockDepth:
    def __init__(self):
        self.best_bid = 100.0
        self.best_bid_qty = 10.0
        self.best_ask = 101.0
        self.best_ask_qty = 15.0
        self.snapshot = []


class MockOrderDict:
    def __init__(self, orders):
        self._orders = orders
        self._iter = None
    
    def values(self):
        self._iter = iter(self._orders.values())
        return self
    
    def next(self):
        try:
            order_data = next(self._iter)
            order = Mock()
            order.order_id = order_data['order_id']
            order.side = order_data['side']
            order.price = order_data['price']
            order.qty = order_data['qty']
            order.leaves_qty = order_data['qty']
            order.status = 1
            return order
        except StopIteration:
            return None


class MockEvent:
    def __init__(self, event_type, **kwargs):
        self.data = {
            'ev': event_type,
            'exch_ts': kwargs.get('exch_ts', 1234567890000000000),
            'px': kwargs.get('px', 100.0),
            'qty': kwargs.get('qty', 1.0)
        }
    
    def __getitem__(self, key):
        return self.data[key]


class TestLiveClientModels(unittest.TestCase):
    def setUp(self):
        try:
            from hftbacktest.live.models import (
                Trade, BookUpdate, DepthSnapshot, Side, EventType,
                OrderRequest, OrderResponse, ConnectionHealth, BookLevel
            )
            self.models = {
                'Trade': Trade,
                'BookUpdate': BookUpdate,
                'DepthSnapshot': DepthSnapshot,
                'Side': Side,
                'EventType': EventType,
                'OrderRequest': OrderRequest,
                'OrderResponse': OrderResponse,
                'ConnectionHealth': ConnectionHealth,
                'BookLevel': BookLevel
            }
            self.models_available = True
        except ImportError:
            self.models_available = False
    
    def test_trade_creation(self):
        if not self.models_available:
            self.skipTest("Live models not available")
        
        Trade = self.models['Trade']
        Side = self.models['Side']
        
        trade = Trade(
            timestamp=1234567890,
            price=100.5,
            qty=1.5,
            side=Side.BUY,
            asset_no=0
        )
        
        self.assertEqual(trade.timestamp, 1234567890)
        self.assertEqual(trade.price, 100.5)
        self.assertEqual(trade.qty, 1.5)
        self.assertEqual(trade.side, Side.BUY)
        self.assertEqual(trade.asset_no, 0)
    
    def test_trade_from_event(self):
        if not self.models_available:
            self.skipTest("Live models not available")
        
        Trade = self.models['Trade']
        Side = self.models['Side']
        
        event = MockEvent(0x03, exch_ts=1234567890, px=100.5, qty=2.0)
        trade = Trade.from_event(event, asset_no=0)
        
        self.assertEqual(trade.timestamp, 1234567890)
        self.assertEqual(trade.price, 100.5)
        self.assertEqual(trade.qty, 2.0)
        self.assertEqual(trade.side, Side.BUY)
    
    def test_book_update_creation(self):
        if not self.models_available:
            self.skipTest("Live models not available")
        
        BookUpdate = self.models['BookUpdate']
        
        update = BookUpdate(
            timestamp=1234567890,
            bid_price=100.0,
            bid_qty=10.0,
            ask_price=101.0,
            ask_qty=15.0,
            asset_no=0
        )
        
        self.assertEqual(update.timestamp, 1234567890)
        self.assertEqual(update.bid_price, 100.0)
        self.assertEqual(update.bid_qty, 10.0)
        self.assertEqual(update.ask_price, 101.0)
        self.assertEqual(update.ask_qty, 15.0)
    
    def test_book_update_from_depth(self):
        if not self.models_available:
            self.skipTest("Live models not available")
        
        BookUpdate = self.models['BookUpdate']
        
        depth = MockDepth()
        update = BookUpdate.from_depth(depth, 1234567890, asset_no=0)
        
        self.assertEqual(update.timestamp, 1234567890)
        self.assertEqual(update.bid_price, 100.0)
        self.assertEqual(update.bid_qty, 10.0)
        self.assertEqual(update.ask_price, 101.0)
        self.assertEqual(update.ask_qty, 15.0)
    
    def test_order_response(self):
        if not self.models_available:
            self.skipTest("Live models not available")
        
        OrderResponse = self.models['OrderResponse']
        
        response = OrderResponse(
            order_id=123,
            status="submitted",
            filled_qty=0.0,
            asset_no=0
        )
        
        self.assertEqual(response.order_id, 123)
        self.assertEqual(response.status, "submitted")
        self.assertEqual(response.filled_qty, 0.0)
        self.assertIsNone(response.error)
    
    def test_connection_health(self):
        if not self.models_available:
            self.skipTest("Live models not available")
        
        ConnectionHealth = self.models['ConnectionHealth']
        
        health = ConnectionHealth(
            connected=True,
            feed_latency_ns=100000,
            order_latency_ns=150000
        )
        
        self.assertTrue(health.connected)
        self.assertEqual(health.feed_latency_ns, 100000)
        self.assertEqual(health.order_latency_ns, 150000)


class TestLiveClient(unittest.TestCase):
    def setUp(self):
        try:
            from hftbacktest.live.client import LiveClient, LiveClientError
            from hftbacktest.live.models import Side
            self.LiveClient = LiveClient
            self.LiveClientError = LiveClientError
            self.Side = Side
            self.client_available = True
        except ImportError:
            self.client_available = False
    
    def test_client_initialization(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        client = self.LiveClient(bot)
        
        self.assertFalse(client._running)
        self.assertIsNotNone(client._trade_queue)
        self.assertIsNotNone(client._book_queue)
        self.assertIsNotNone(client._snapshot_queue)
    
    def test_client_start_stop(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        client = self.LiveClient(bot)
        
        client.start()
        self.assertTrue(client._running)
        self.assertIsNotNone(client._feed_thread)
        self.assertTrue(client._feed_thread.is_alive())
        
        time.sleep(0.1)
        
        client.stop()
        self.assertFalse(client._running)
    
    def test_client_context_manager(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        
        with self.LiveClient(bot) as client:
            self.assertTrue(client._running)
        
        self.assertFalse(client._running)
        self.assertTrue(bot._closed)
    
    def test_submit_buy_order(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        client = self.LiveClient(bot)
        
        response = client.submit_order(
            side=self.Side.BUY,
            price=100.0,
            qty=1.0,
            asset_no=0
        )
        
        self.assertEqual(response.status, "submitted")
        self.assertIsNotNone(response.order_id)
        self.assertIsNone(response.error)
    
    def test_submit_sell_order(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        client = self.LiveClient(bot)
        
        response = client.submit_order(
            side=self.Side.SELL,
            price=101.0,
            qty=2.0,
            asset_no=0
        )
        
        self.assertEqual(response.status, "submitted")
        self.assertIsNotNone(response.order_id)
        self.assertIsNone(response.error)
    
    def test_cancel_order(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        client = self.LiveClient(bot)
        
        submit_response = client.submit_order(
            side=self.Side.BUY,
            price=100.0,
            qty=1.0,
            asset_no=0
        )
        
        cancel_response = client.cancel_order(
            order_id=submit_response.order_id,
            asset_no=0
        )
        
        self.assertEqual(cancel_response.status, "cancelled")
        self.assertIsNone(cancel_response.error)
    
    def test_cancel_nonexistent_order(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        client = self.LiveClient(bot)
        
        response = client.cancel_order(
            order_id=99999,
            asset_no=0
        )
        
        self.assertEqual(response.status, "error")
        self.assertIsNotNone(response.error)
        self.assertIn("Order not found", response.error)
    
    def test_get_position(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        bot._position = 5.0
        client = self.LiveClient(bot)
        
        position = client.get_position(asset_no=0)
        self.assertEqual(position, 5.0)
    
    def test_get_orders(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        client = self.LiveClient(bot)
        
        client.submit_order(
            side=self.Side.BUY,
            price=100.0,
            qty=1.0,
            order_id=123
        )
        
        orders = client.get_orders(asset_no=0)
        self.assertIn(123, orders)
        self.assertEqual(orders[123]['side'], 'buy')
        self.assertEqual(orders[123]['price'], 100.0)
    
    def test_health_tracking(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        client = self.LiveClient(bot, health_check_interval=0.1)
        
        client.start()
        time.sleep(0.3)
        
        health = client.health
        self.assertTrue(health.connected)
        self.assertIsNotNone(health.feed_latency_ns)
        self.assertIsNotNone(health.order_latency_ns)
        
        client.stop()
    
    def test_order_id_generation(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        client = self.LiveClient(bot)
        
        id1 = client._generate_order_id()
        id2 = client._generate_order_id()
        id3 = client._generate_order_id()
        
        self.assertEqual(id1, 1)
        self.assertEqual(id2, 2)
        self.assertEqual(id3, 3)
    
    def test_feed_processing(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        bot._last_trades = [
            MockEvent(0x03, exch_ts=1234567890, px=100.0, qty=1.0)
        ]
        
        client = self.LiveClient(bot)
        client.start()
        
        time.sleep(0.2)
        
        trade = client.get_trade_nowait()
        self.assertIsNotNone(trade)
        
        client.stop()
    
    def test_thread_cleanup(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        client = self.LiveClient(bot)
        
        client.start()
        self.assertTrue(client._feed_thread.is_alive())
        self.assertTrue(client._health_thread.is_alive())
        
        client.stop()
        time.sleep(0.5)
        
        self.assertFalse(client._feed_thread.is_alive())
        self.assertFalse(client._health_thread.is_alive())
    
    def test_async_get_trade(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        bot = MockBot()
        bot._last_trades = [
            MockEvent(0x03, exch_ts=1234567890, px=100.0, qty=1.0)
        ]
        
        client = self.LiveClient(bot)
        client.start()
        
        time.sleep(0.2)
        
        async def test():
            trade = await client.get_trade(timeout=1.0)
            return trade
        
        trade = asyncio.run(test())
        self.assertIsNotNone(trade)
        
        client.stop()
    
    def test_error_decoding(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        self.assertEqual(self.LiveClient._decode_error(10), "Order ID already exists")
        self.assertEqual(self.LiveClient._decode_error(12), "Order not found")
        self.assertEqual(self.LiveClient._decode_error(17), "Timeout")
        self.assertEqual(self.LiveClient._decode_error(999), "Unknown error code: 999")


class TestLiveClientCallbacks(unittest.TestCase):
    def setUp(self):
        try:
            from hftbacktest.live.client import LiveClient
            self.LiveClient = LiveClient
            self.client_available = True
        except ImportError:
            self.client_available = False
    
    def test_on_connection_lost_callback(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        callback_called = threading.Event()
        
        def on_connection_lost():
            callback_called.set()
        
        bot = MockBot()
        client = self.LiveClient(
            bot,
            health_check_interval=0.1,
            on_connection_lost=on_connection_lost
        )
        
        client.start()
        client._health.connected = True
        time.sleep(0.15)
        
        bot.feed_latency = lambda asset_no: None
        time.sleep(0.15)
        
        client.stop()
    
    def test_on_error_callback(self):
        if not self.client_available:
            self.skipTest("Live client not available")
        
        error_received = []
        
        def on_error(exc):
            error_received.append(exc)
        
        bot = MockBot()
        
        def bad_wait_next_feed(include_order_resp, timeout):
            return 99
        
        bot.wait_next_feed = bad_wait_next_feed
        
        client = self.LiveClient(bot, on_error=on_error)
        client.start()
        
        time.sleep(0.2)
        
        client.stop()


if __name__ == '__main__':
    unittest.main()
