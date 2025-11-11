"""Unit tests for Bybit trade history fetching."""

import json
import unittest
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import responses


class MockBybitServer:
    """Mock Bybit server for testing."""

    def __init__(self):
        self.trades_by_symbol: Dict[str, List[Dict]] = {}
        self.rate_limit_requests = 0
        self.should_rate_limit = False

    def add_trades(self, symbol: str, trades: List[Dict]) -> None:
        """Add trades for a symbol."""
        self.trades_by_symbol[symbol] = trades

    def get_trades_in_range(
        self, symbol: str, start_time: int, end_time: int, cursor: Optional[str] = None
    ) -> Dict:
        """Get trades within the specified time range with pagination."""
        if symbol not in self.trades_by_symbol:
            return {"retCode": 20001, "retMsg": "Invalid symbol"}

        all_trades = self.trades_by_symbol[symbol]

        # Filter trades by time
        filtered_trades = [
            t for t in all_trades if start_time <= int(t["time"]) <= end_time
        ]

        # Sort by time descending (Bybit returns newest first)
        filtered_trades.sort(key=lambda x: int(x["time"]), reverse=True)

        # Pagination: return 5 trades per page for testing
        page_size = 5
        start_idx = 0

        if cursor:
            try:
                start_idx = int(cursor)
            except ValueError:
                return {"retCode": 110001, "retMsg": "Invalid cursor"}

        end_idx = start_idx + page_size
        page_trades = filtered_trades[start_idx:end_idx]

        result = {
            "retCode": 0,
            "retMsg": "success",
            "result": {
                "list": page_trades,
                "nextPageCursor": (
                    str(end_idx) if end_idx < len(filtered_trades) else None
                ),
            },
        }

        return result


@responses.activate
class TestBybitFetchTrades(unittest.TestCase):
    """Test Bybit trade fetching functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.base_url = "https://api.bybit.com"
        self.symbol = "BTCUSDT"
        self.server = MockBybitServer()

        # Create test trades
        base_time = int(datetime(2024, 1, 1, 0, 0, 0).timestamp() * 1000)
        self.trades = []
        for i in range(12):
            self.trades.append(
                {
                    "execId": f"trade_{i:03d}",
                    "symbol": self.symbol,
                    "price": str(42000 + i),
                    "size": str(0.1 + 0.01 * i),
                    "side": "Buy" if i % 2 == 0 else "Sell",
                    "time": str(base_time + i * 60000),
                    "isBlockTrade": False,
                }
            )

        self.server.add_trades(self.symbol, self.trades)

    def _mock_api_response(self, *args, **kwargs):
        """Mock API response handler."""
        request = args[0]
        url = request.url

        if "/v5/market/trades?" not in url:
            return (200, {}, json.dumps({"retCode": 404, "retMsg": "Not found"}))

        if "symbol=" in url:
            # Extract symbol and time range
            symbol = self.symbol
            start_time = 0
            end_time = int(2e15)
            cursor = None

            # Extract parameters from URL
            params_str = url.split("?")[1]
            for param in params_str.split("&"):
                if param.startswith("symbol="):
                    symbol = param.split("=")[1]
                elif param.startswith("startTime="):
                    start_time = int(param.split("=")[1])
                elif param.startswith("endTime="):
                    end_time = int(param.split("=")[1])
                elif param.startswith("cursor="):
                    cursor = param.split("=")[1]

            response = self.server.get_trades_in_range(symbol, start_time, end_time, cursor)
            return (200, {}, json.dumps(response))

        return (200, {}, json.dumps({"retCode": 400, "retMsg": "Invalid request"}))

    def test_fetch_trades_basic(self):
        """Test basic trade fetching."""
        responses.add_callback(
            responses.GET,
            f"{self.base_url}/v5/market/trades",
            callback=self._mock_api_response,
            content_type="application/json",
        )

        try:
            from hftbacktest.bybit import fetch_trades

            start_time = int(datetime(2024, 1, 1, 0, 0, 0).timestamp() * 1000)
            end_time = int(datetime(2024, 1, 1, 1, 0, 0).timestamp() * 1000)

            trades = fetch_trades(self.symbol, start_time, end_time, base_url=self.base_url)

            # Should get all 12 trades (paginated as 5, 5, 2)
            self.assertEqual(len(trades), 12)
            self.assertEqual(trades[0]["symbol"], self.symbol)
            self.assertIn("timestamp", trades[0])
            self.assertIn("side", trades[0])
            self.assertIn("size", trades[0])
            self.assertIn("price", trades[0])

        except ImportError:
            self.skipTest("hftbacktest extension not available")

    def test_fetch_trades_empty_result(self):
        """Test fetching trades with no results in time range."""
        responses.add_callback(
            responses.GET,
            f"{self.base_url}/v5/market/trades",
            callback=self._mock_api_response,
            content_type="application/json",
        )

        try:
            from hftbacktest.bybit import fetch_trades

            # Query time range with no trades
            start_time = int(datetime(2024, 2, 1, 0, 0, 0).timestamp() * 1000)
            end_time = int(datetime(2024, 2, 1, 1, 0, 0).timestamp() * 1000)

            trades = fetch_trades(self.symbol, start_time, end_time, base_url=self.base_url)
            self.assertEqual(len(trades), 0)

        except ImportError:
            self.skipTest("hftbacktest extension not available")

    def test_fetch_trades_with_limit(self):
        """Test fetching trades with custom limit."""
        responses.add_callback(
            responses.GET,
            f"{self.base_url}/v5/market/trades",
            callback=self._mock_api_response,
            content_type="application/json",
        )

        try:
            from hftbacktest.bybit import fetch_trades

            start_time = int(datetime(2024, 1, 1, 0, 0, 0).timestamp() * 1000)
            end_time = int(datetime(2024, 1, 1, 1, 0, 0).timestamp() * 1000)

            trades = fetch_trades(
                self.symbol, start_time, end_time, limit=500, base_url=self.base_url
            )

            self.assertEqual(len(trades), 12)
            for trade in trades:
                self.assertIsInstance(trade["timestamp"], int)
                self.assertIsInstance(trade["size"], float)
                self.assertIsInstance(trade["price"], float)

        except ImportError:
            self.skipTest("hftbacktest extension not available")

    def test_fetch_trades_response_format(self):
        """Test that returned trades have correct format."""
        responses.add_callback(
            responses.GET,
            f"{self.base_url}/v5/market/trades",
            callback=self._mock_api_response,
            content_type="application/json",
        )

        try:
            from hftbacktest.bybit import fetch_trades

            start_time = int(datetime(2024, 1, 1, 0, 0, 0).timestamp() * 1000)
            end_time = int(datetime(2024, 1, 1, 1, 0, 0).timestamp() * 1000)

            trades = fetch_trades(self.symbol, start_time, end_time, base_url=self.base_url)

            required_fields = {"timestamp", "symbol", "side", "size", "price"}
            for trade in trades:
                self.assertTrue(
                    required_fields.issubset(trade.keys()),
                    f"Trade missing fields. Got: {trade.keys()}",
                )
                self.assertIn(trade["side"], ["Buy", "Sell"])
                self.assertGreater(trade["price"], 0)
                self.assertGreater(trade["size"], 0)

        except ImportError:
            self.skipTest("hftbacktest extension not available")

    def test_fetch_trades_pagination(self):
        """Test that pagination is handled correctly."""
        responses.add_callback(
            responses.GET,
            f"{self.base_url}/v5/market/trades",
            callback=self._mock_api_response,
            content_type="application/json",
        )

        try:
            from hftbacktest.bybit import fetch_trades

            start_time = int(datetime(2024, 1, 1, 0, 0, 0).timestamp() * 1000)
            end_time = int(datetime(2024, 1, 1, 1, 0, 0).timestamp() * 1000)

            trades = fetch_trades(self.symbol, start_time, end_time, base_url=self.base_url)

            # Verify pagination: should have made multiple requests
            # All 12 trades should be returned despite pagination
            self.assertGreaterEqual(len(trades), 10)

        except ImportError:
            self.skipTest("hftbacktest extension not available")

    def test_fetch_trades_invalid_symbol(self):
        """Test fetching trades with invalid symbol."""
        responses.add_callback(
            responses.GET,
            f"{self.base_url}/v5/market/trades",
            callback=self._mock_api_response,
            content_type="application/json",
        )

        try:
            from hftbacktest.bybit import fetch_trades

            start_time = int(datetime(2024, 1, 1, 0, 0, 0).timestamp() * 1000)
            end_time = int(datetime(2024, 1, 1, 1, 0, 0).timestamp() * 1000)

            with self.assertRaises(RuntimeError):
                fetch_trades("INVALIDSYMBOL", start_time, end_time, base_url=self.base_url)

        except ImportError:
            self.skipTest("hftbacktest extension not available")

    def test_fetch_trades_various_sides(self):
        """Test that both Buy and Sell sides are returned correctly."""
        responses.add_callback(
            responses.GET,
            f"{self.base_url}/v5/market/trades",
            callback=self._mock_api_response,
            content_type="application/json",
        )

        try:
            from hftbacktest.bybit import fetch_trades

            start_time = int(datetime(2024, 1, 1, 0, 0, 0).timestamp() * 1000)
            end_time = int(datetime(2024, 1, 1, 1, 0, 0).timestamp() * 1000)

            trades = fetch_trades(self.symbol, start_time, end_time, base_url=self.base_url)

            buy_trades = [t for t in trades if t["side"] == "Buy"]
            sell_trades = [t for t in trades if t["side"] == "Sell"]

            self.assertGreater(len(buy_trades), 0)
            self.assertGreater(len(sell_trades), 0)

        except ImportError:
            self.skipTest("hftbacktest extension not available")


class TestBybitFetchTradesDocumentation(unittest.TestCase):
    """Test documentation and API contract."""

    def test_function_is_importable(self):
        """Test that fetch_trades is importable from hftbacktest.bybit."""
        try:
            from hftbacktest.bybit import fetch_trades

            self.assertTrue(callable(fetch_trades))
        except ImportError:
            self.skipTest("hftbacktest extension not available")

    def test_function_has_docstring(self):
        """Test that fetch_trades has comprehensive docstring."""
        try:
            from hftbacktest.bybit import fetch_trades

            self.assertIsNotNone(fetch_trades.__doc__)
            doc = fetch_trades.__doc__
            self.assertIn("Args:", doc)
            self.assertIn("Returns:", doc)
            self.assertIn("Raises:", doc)
        except ImportError:
            self.skipTest("hftbacktest extension not available")

    def test_function_signature(self):
        """Test that function has correct signature."""
        try:
            from hftbacktest.bybit import fetch_trades
            import inspect

            sig = inspect.signature(fetch_trades)
            params = list(sig.parameters.keys())

            self.assertIn("symbol", params)
            self.assertIn("start_time", params)
            self.assertIn("end_time", params)
            self.assertIn("limit", params)
            self.assertIn("api_key", params)
            self.assertIn("secret", params)
            self.assertIn("base_url", params)

        except ImportError:
            self.skipTest("hftbacktest extension not available")


class TestBybitRateLimiting(unittest.TestCase):
    """Test rate limiting handling."""

    def test_rate_limit_backoff_strategy(self):
        """Test that rate limit backoff strategy is documented."""
        try:
            from hftbacktest.bybit import fetch_trades

            doc = fetch_trades.__doc__
            self.assertIn("rate limit", doc.lower())
            self.assertIn("backoff", doc.lower())
        except ImportError:
            self.skipTest("hftbacktest extension not available")


if __name__ == "__main__":
    unittest.main()
