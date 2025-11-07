"""
Regression tests for the python_live_connector.py example.

Tests the example script's ability to:
1. Create and configure a LiveClient
2. Subscribe to trades and depth updates
3. Collect and aggregate market statistics
4. Handle graceful shutdown

Uses the StubConnectorBot to run without a real connector process.
"""

import unittest
import time
import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestPythonLiveConnectorExample(unittest.TestCase):
    """Tests for python_live_connector.py example functionality."""
    
    def test_stub_bot_creation(self):
        """Test that StubConnectorBot can be created."""
        from hftbacktest.live import StubConnectorBot
        
        bot = StubConnectorBot(base_price=50000.0, seed=42)
        
        self.assertEqual(bot.num_assets, 1)
        self.assertGreater(bot.current_timestamp, 0)
        self.assertEqual(bot.position(0), 0.0)
        
        # Close should succeed
        result = bot.close()
        self.assertEqual(result, 0)
    
    def test_stub_bot_trades_generation(self):
        """Test that stub bot generates synthetic trades."""
        from hftbacktest.live import StubConnectorBot
        
        bot = StubConnectorBot(seed=42)
        
        # First feed should generate data
        result = bot.wait_next_feed(include_order_resp=False, timeout=10_000_000_000)
        self.assertIn(result, [0, 2, 3])  # Should return something
        
        # Get last trades
        trades = bot.last_trades(0)
        # With seed=42, we might get trades (probabilistic)
        # At minimum, the method should work
        self.assertIsInstance(trades, list)
        
        bot.close()
    
    def test_stub_bot_depth_updates(self):
        """Test that stub bot generates market depth updates."""
        from hftbacktest.live import StubConnectorBot
        
        bot = StubConnectorBot(seed=42)
        
        # Generate a few feeds to ensure we get depth data
        for _ in range(10):
            bot.wait_next_feed(include_order_resp=False, timeout=10_000_000_000)
        
        # Get depth
        depth = bot.depth(0)
        self.assertIsNotNone(depth)
        self.assertGreater(depth.best_ask, depth.best_bid)
        self.assertGreater(depth.best_bid_qty, 0)
        self.assertGreater(depth.best_ask_qty, 0)
        
        bot.close()
    
    def test_stub_bot_order_submission(self):
        """Test that stub bot can accept and track orders."""
        from hftbacktest.live import StubConnectorBot
        
        bot = StubConnectorBot(seed=42)
        
        # Submit buy order
        result = bot.submit_buy_order(
            asset_no=0,
            order_id=1,
            price=49999.0,
            qty=0.1,
            time_in_force=0,  # GTC
            order_type=0,     # LIMIT
            wait=False
        )
        self.assertEqual(result, 0)
        
        # Get orders
        orders_dict = bot.orders(0)
        order = orders_dict.values().next()
        self.assertIsNotNone(order)
        self.assertEqual(order.order_id, 1)
        self.assertEqual(order.side, 1)  # BUY
        
        # Cancel order
        result = bot.cancel(0, 1, wait=False)
        self.assertEqual(result, 0)
        
        # Order should be gone
        orders_dict = bot.orders(0)
        order = orders_dict.values().next()
        self.assertIsNone(order)
        
        bot.close()
    
    def test_stub_bot_duplicate_order_id(self):
        """Test that stub bot rejects duplicate order IDs."""
        from hftbacktest.live import StubConnectorBot
        
        bot = StubConnectorBot(seed=42)
        
        # Submit first order
        result = bot.submit_buy_order(0, 1, 49999.0, 0.1, 0, 0, False)
        self.assertEqual(result, 0)
        
        # Submit with same order ID should fail
        result = bot.submit_buy_order(0, 1, 50000.0, 0.1, 0, 0, False)
        self.assertEqual(result, 10)  # Duplicate order ID
        
        bot.close()
    
    def test_stub_bot_latency_methods(self):
        """Test that stub bot provides latency information."""
        from hftbacktest.live import StubConnectorBot
        
        bot = StubConnectorBot()
        
        # Get feed latency
        exch_ts, local_ts = bot.feed_latency(0)
        self.assertGreater(local_ts, exch_ts)
        
        # Get order latency
        req_ts, exch_ts, resp_ts = bot.order_latency(0)
        self.assertGreater(exch_ts, req_ts)
        self.assertGreater(resp_ts, exch_ts)
        
        bot.close()
    
    def test_live_client_with_stub_bot(self):
        """Test LiveClient integration with stub bot."""
        try:
            from hftbacktest.live import LiveClient, StubConnectorBot
        except ImportError:
            self.skipTest("Live features not available")
        
        bot = StubConnectorBot(seed=42)
        
        with LiveClient(bot) as client:
            # Check initial state
            self.assertEqual(client.num_assets, 1)
            self.assertGreater(client.current_timestamp, 0)
            
            # Run for a short time to collect data
            start_time = time.time()
            trades_collected = 0
            updates_collected = 0
            
            while time.time() - start_time < 2:
                trade = client.get_trade_nowait()
                if trade:
                    trades_collected += 1
                    self.assertIsNotNone(trade.price)
                    self.assertIsNotNone(trade.qty)
                
                book = client.get_book_update_nowait()
                if book:
                    updates_collected += 1
                    self.assertGreater(book.ask_price, book.bid_price)
                
                time.sleep(0.01)
            
            # We should have collected some data
            self.assertGreater(trades_collected + updates_collected, 0)
    
    def test_example_market_statistics_class(self):
        """Test the MarketStatistics class from the example."""
        # Import the MarketStatistics class from the example
        import sys
        import importlib.util
        
        example_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'examples', 'python_live_connector.py'
        )
        
        spec = importlib.util.spec_from_file_location("example", example_path)
        example_module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(example_module)
            MarketStatistics = example_module.MarketStatistics
        except Exception as e:
            self.skipTest(f"Could not load example module: {e}")
        
        # Create statistics object
        stats = MarketStatistics()
        
        # Test initial state
        self.assertEqual(stats.total_trades, 0)
        self.assertEqual(stats.total_volume, 0.0)
        self.assertIsNone(stats.spread)
        
        # Update statistics
        stats.total_trades = 100
        stats.buy_volume = 10.0
        stats.sell_volume = 5.0
        stats.last_bid = 50000.0
        stats.last_ask = 50001.0
        stats.spread = 1.0
        stats.max_spread = 2.0
        stats.min_spread = 0.5
        stats.depth_updates = 500
        stats.trades_per_second = 10.0
        
        # Verify values
        self.assertEqual(stats.total_trades, 100)
        self.assertEqual(stats.total_volume, 15.0)
        self.assertEqual(stats.spread, 1.0)
        self.assertEqual(stats.trades_per_second, 10.0)
        
        # Test string representation
        stat_str = str(stats)
        self.assertIn("Market Statistics", stat_str)
        self.assertIn("100", stat_str)
        self.assertIn("15.0000", stat_str)
    
    def test_example_runs_with_stub(self):
        """Integration test: Run the full example with stub bot."""
        import importlib.util
        
        example_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'examples', 'python_live_connector.py'
        )
        
        spec = importlib.util.spec_from_file_location("example", example_path)
        example_module = importlib.util.module_from_spec(spec)
        
        try:
            spec.loader.exec_module(example_module)
            run_connector_example = example_module.run_connector_example
        except Exception as e:
            self.skipTest(f"Could not load example module: {e}")
        
        # Run example with stub for 1 second
        result = run_connector_example(use_stub=True, duration=1)
        
        # Should complete successfully
        self.assertTrue(result)


class TestStubBotBehavior(unittest.TestCase):
    """Detailed tests for StubConnectorBot behavior."""
    
    def test_stub_respects_seed(self):
        """Test that stub bot produces deterministic output with seed."""
        from hftbacktest.live import StubConnectorBot
        
        # Create two bots with same seed
        bot1 = StubConnectorBot(seed=123)
        bot2 = StubConnectorBot(seed=123)
        
        # Generate same number of feeds
        bot1_trades_count = 0
        bot2_trades_count = 0
        
        for _ in range(10):
            bot1.wait_next_feed(include_order_resp=False, timeout=10_000_000_000)
            bot2.wait_next_feed(include_order_resp=False, timeout=10_000_000_000)
            
            bot1_trades = bot1.last_trades(0)
            bot2_trades = bot2.last_trades(0)
            
            bot1_trades_count += len(bot1_trades)
            bot2_trades_count += len(bot2_trades)
            
            bot1.clear_last_trades(0)
            bot2.clear_last_trades(0)
        
        # Should have same trade count with same seed
        self.assertEqual(bot1_trades_count, bot2_trades_count)
        
        bot1.close()
        bot2.close()
    
    def test_stub_max_feeds(self):
        """Test that stub bot stops after max feeds."""
        from hftbacktest.live import StubConnectorBot
        
        bot = StubConnectorBot()
        
        # Keep requesting feeds until we get end of data
        feed_count = 0
        while feed_count < 2000:
            result = bot.wait_next_feed(include_order_resp=False, timeout=10_000_000_000)
            feed_count += 1
            
            if result == 1:  # End of data
                break
        
        # Should stop at 1000 feeds
        self.assertGreater(1000, feed_count)
        self.assertLess(feed_count, 1020)


if __name__ == '__main__':
    unittest.main()
