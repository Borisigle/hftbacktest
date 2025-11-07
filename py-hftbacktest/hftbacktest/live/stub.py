"""
Lightweight stub connector bot for testing without a real connector process.

This module provides a mock bot that simulates a real connector's behavior,
including generating synthetic market data (trades, depth updates) and order
responses. It's useful for:
- Unit testing strategies without running a connector
- CI/CD testing where Iceoryx2 IPC is not available
- Development and documentation examples

Usage:
    from hftbacktest.live.stub import StubConnectorBot
    bot = StubConnectorBot()
    # Use bot like a real connector bot
"""

import time
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class StubDepth:
    """Mock market depth snapshot."""
    best_bid: float = 50000.0
    best_bid_qty: float = 1.0
    best_ask: float = 50001.0
    best_ask_qty: float = 1.0
    tick_size: float = 0.1
    snapshot: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class StubOrder:
    """Mock order object."""
    order_id: int
    side: int  # BUY = 1, SELL = -1
    price: float
    qty: float
    leaves_qty: float = 0.0
    status: str = "accepted"


class StubOrderDict:
    """Mock order dictionary iterator."""
    
    def __init__(self, orders: Dict[int, StubOrder]):
        self._orders = orders
        self._iterator = None
    
    def values(self):
        self._iterator = iter(self._orders.values())
        return self
    
    def next(self) -> Optional[StubOrder]:
        try:
            return next(self._iterator)
        except StopIteration:
            return None


class StubConnectorBot:
    """
    Lightweight mock bot that simulates a real connector.
    
    Features:
    - Generates synthetic trades and depth updates
    - Maintains order book state
    - Simulates latencies
    - Thread-safe (uses same interface as real bot)
    
    Attributes:
        num_assets: Number of assets (always 1 for stub)
        current_timestamp: Current simulation time in nanoseconds
    """
    
    def __init__(self, base_price: float = 50000.0, seed: Optional[int] = None):
        """
        Initialize stub bot.
        
        Args:
            base_price: Starting mid-price for synthetic data
            seed: Random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)
        
        self.num_assets = 1
        self._base_price = base_price
        self._current_ns = int(time.time() * 1_000_000_000)
        self._closed = False
        self._position = 0.0
        self._orders: Dict[int, StubOrder] = {}
        self._depth = StubDepth()
        self._last_trades: List[Dict[str, Any]] = []
        self._feed_count = 0
        self._order_count = 0
        self._start_time = self._current_ns
        
        # Volatility parameters for synthetic data
        self._price_volatility = 0.0001  # 0.01% per update
        self._spread_base = 1.0  # Base spread
    
    def close(self) -> int:
        """Close the bot connection. Returns 0 on success."""
        self._closed = True
        return 0
    
    def wait_next_feed(
        self,
        include_order_resp: bool = False,
        timeout: int = 10_000_000_000
    ) -> int:
        """
        Wait for the next feed event.
        
        Returns:
            0: Timeout
            1: End of data
            2: Market feed available
            3: Order response available
        """
        if self._closed:
            return 1
        
        # Generate synthetic data
        self._feed_count += 1
        
        # Limit to 1000 feeds to prevent infinite loops in tests
        if self._feed_count > 1000:
            return 1
        
        # Periodically generate trades (70% of events)
        if random.random() < 0.7:
            self._generate_synthetic_trade()
        
        # Periodically update depth (80% of events)
        if random.random() < 0.8:
            self._update_synthetic_depth()
        
        # Advance time
        self._current_ns += random.randint(1_000_000, 10_000_000)  # 1-10ms
        
        # Return market feed if we have data
        if self._last_trades or self._feed_count % 5 == 0:
            return 2  # Market feed
        
        return 0  # Timeout
    
    def last_trades(self, asset_no: int) -> List[Dict[str, Any]]:
        """Get last trades for asset."""
        return self._last_trades
    
    def clear_last_trades(self, asset_no: int) -> None:
        """Clear last trades buffer."""
        self._last_trades = []
    
    def depth(self, asset_no: int) -> StubDepth:
        """Get current market depth."""
        return self._depth
    
    def position(self, asset_no: int) -> float:
        """Get current position."""
        return self._position
    
    def orders(self, asset_no: int) -> StubOrderDict:
        """Get active orders."""
        return StubOrderDict(self._orders)
    
    def submit_buy_order(
        self,
        asset_no: int,
        order_id: int,
        price: float,
        qty: float,
        time_in_force: int,
        order_type: int,
        wait: bool = False
    ) -> int:
        """
        Submit a buy order.
        
        Returns:
            0: Success
            10: Order ID already exists
            16: Instrument not found
        """
        if order_id in self._orders:
            return 10  # Order already exists
        
        self._orders[order_id] = StubOrder(
            order_id=order_id,
            side=1,  # BUY
            price=price,
            qty=qty,
            leaves_qty=qty,
            status="accepted"
        )
        
        # Simulate occasional fills
        if random.random() < 0.3:
            self._orders[order_id].leaves_qty = 0
            self._orders[order_id].status = "filled"
            self._position += qty
        
        return 0
    
    def submit_sell_order(
        self,
        asset_no: int,
        order_id: int,
        price: float,
        qty: float,
        time_in_force: int,
        order_type: int,
        wait: bool = False
    ) -> int:
        """
        Submit a sell order.
        
        Returns:
            0: Success
            10: Order ID already exists
            16: Instrument not found
        """
        if order_id in self._orders:
            return 10  # Order already exists
        
        self._orders[order_id] = StubOrder(
            order_id=order_id,
            side=-1,  # SELL
            price=price,
            qty=qty,
            leaves_qty=qty,
            status="accepted"
        )
        
        # Simulate occasional fills
        if random.random() < 0.3:
            self._orders[order_id].leaves_qty = 0
            self._orders[order_id].status = "filled"
            self._position -= qty
        
        return 0
    
    def cancel(
        self,
        asset_no: int,
        order_id: int,
        wait: bool = False
    ) -> int:
        """
        Cancel an order.
        
        Returns:
            0: Success
            12: Order not found
        """
        if order_id not in self._orders:
            return 12  # Not found
        
        del self._orders[order_id]
        return 0
    
    def feed_latency(self, asset_no: int) -> Tuple[int, int]:
        """
        Get feed latency.
        
        Returns:
            (exchange_ts, local_ts) tuple in nanoseconds
        """
        # Simulate ~100ns latency
        latency = 100_000  # 100 microseconds
        return (self._current_ns - latency, self._current_ns)
    
    def order_latency(self, asset_no: int) -> Tuple[int, int, int]:
        """
        Get order latency.
        
        Returns:
            (request_ts, exchange_ts, response_ts) tuple in nanoseconds
        """
        # Simulate roundtrip latency: request -> exchange -> response
        rtt = 1_000_000  # 1ms roundtrip
        return (
            self._current_ns - 2 * rtt,      # request time
            self._current_ns - rtt,          # exchange receipt
            self._current_ns                 # response time
        )
    
    @property
    def current_timestamp(self) -> int:
        """Current simulation timestamp in nanoseconds."""
        return self._current_ns
    
    def _generate_synthetic_trade(self) -> None:
        """Generate a synthetic trade."""
        # Random walk for price
        mid = (self._depth.best_bid + self._depth.best_ask) / 2.0
        price_change = random.gauss(0, mid * self._price_volatility)
        trade_price = mid + price_change
        
        # Random trade direction
        is_buy = random.random() < 0.5
        trade_qty = random.uniform(0.1, 2.0)
        
        # Create trade event
        trade = {
            'exch_ts': self._current_ns,
            'px': trade_price,
            'qty': trade_qty,
            'ev': 0x01 if is_buy else 0x02,  # Buy or Sell event
            'side': 1 if is_buy else -1
        }
        
        self._last_trades.append(trade)
    
    def _update_synthetic_depth(self) -> None:
        """Update synthetic market depth."""
        # Random walk for mid price
        mid = (self._depth.best_bid + self._depth.best_ask) / 2.0
        price_change = random.gauss(0, mid * self._price_volatility * 2)
        new_mid = mid + price_change
        
        # Random spread
        spread = self._spread_base * random.uniform(0.5, 1.5)
        
        # Update depth
        self._depth.best_bid = new_mid - spread / 2.0
        self._depth.best_bid_qty = random.uniform(0.5, 5.0)
        self._depth.best_ask = new_mid + spread / 2.0
        self._depth.best_ask_qty = random.uniform(0.5, 5.0)
        
        # Create snapshot event
        snapshot_event = {
            'exch_ts': self._current_ns,
            'ev': 0x04,  # Depth snapshot event
        }
        
        self._last_trades.append(snapshot_event)
