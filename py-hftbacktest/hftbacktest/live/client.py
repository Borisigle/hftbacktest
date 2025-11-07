import asyncio
import logging
import threading
from queue import Queue, Empty
from typing import Optional, Callable, List, Union
from contextlib import contextmanager

try:
    from ..binding import HashMapMarketDepthLiveBot_, ROIVectorMarketDepthLiveBot_
    from .models import (
        Trade, BookUpdate, DepthSnapshot, OrderRequest, OrderResponse,
        ConnectionHealth, Side, EventType
    )
    from .. import (
        BUY, SELL, GTC, GTX, LIMIT, MARKET,
        TRADE_EVENT, DEPTH_EVENT, DEPTH_SNAPSHOT_EVENT, DEPTH_BBO_EVENT,
        BUY_EVENT, SELL_EVENT
    )
    LIVE_AVAILABLE = True
except ImportError:
    LIVE_AVAILABLE = False


logger = logging.getLogger(__name__)


class LiveClientError(Exception):
    pass


class LiveClient:
    def __init__(
        self,
        bot: Union['HashMapMarketDepthLiveBot_', 'ROIVectorMarketDepthLiveBot_'],
        *,
        trade_queue_size: int = 1000,
        book_queue_size: int = 1000,
        snapshot_queue_size: int = 100,
        health_check_interval: float = 5.0,
        feed_timeout_ns: int = 10_000_000_000,
        on_connection_lost: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ):
        if not LIVE_AVAILABLE:
            raise LiveClientError(
                "Live features not available. Please build with 'live' feature enabled: "
                "maturin develop --features live"
            )
        
        self._bot = bot
        self._trade_queue = Queue(maxsize=trade_queue_size)
        self._book_queue = Queue(maxsize=book_queue_size)
        self._snapshot_queue = Queue(maxsize=snapshot_queue_size)
        self._health_check_interval = health_check_interval
        self._feed_timeout_ns = feed_timeout_ns
        self._on_connection_lost = on_connection_lost
        self._on_error = on_error
        
        self._feed_thread: Optional[threading.Thread] = None
        self._health_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._health = ConnectionHealth(connected=False)
        self._lock = threading.Lock()
        
        self._next_order_id = 1
        self._order_id_lock = threading.Lock()

    def start(self):
        if self._running:
            raise LiveClientError("Client already running")
        
        self._stop_event.clear()
        self._running = True
        
        self._feed_thread = threading.Thread(
            target=self._feed_worker,
            daemon=True,
            name="LiveClient-FeedWorker"
        )
        self._feed_thread.start()
        
        self._health_thread = threading.Thread(
            target=self._health_worker,
            daemon=True,
            name="LiveClient-HealthWorker"
        )
        self._health_thread.start()
        
        logger.info("LiveClient started")

    def stop(self):
        if not self._running:
            return
        
        self._stop_event.set()
        self._running = False
        
        if self._feed_thread and self._feed_thread.is_alive():
            self._feed_thread.join(timeout=5.0)
        
        if self._health_thread and self._health_thread.is_alive():
            self._health_thread.join(timeout=2.0)
        
        logger.info("LiveClient stopped")

    def close(self):
        self.stop()
        
        try:
            result = self._bot.close()
            if result != 0:
                logger.error(f"Bot close returned error code: {result}")
        except Exception as e:
            logger.error(f"Error closing bot: {e}")
        
        logger.info("LiveClient closed")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _feed_worker(self):
        logger.debug("Feed worker started")
        
        while not self._stop_event.is_set():
            try:
                result = self._bot.wait_next_feed(
                    include_order_resp=False,
                    timeout=self._feed_timeout_ns
                )
                
                if result == 0:
                    continue
                elif result == 1:
                    logger.warning("End of data reached")
                    break
                elif result == 2:
                    self._process_market_feed()
                elif result == 3:
                    self._process_order_response()
                else:
                    logger.error(f"wait_next_feed returned error code: {result}")
                    if self._on_error:
                        self._on_error(LiveClientError(f"Feed error: {result}"))
                    
            except Exception as e:
                logger.exception("Exception in feed worker")
                if self._on_error:
                    self._on_error(e)
        
        logger.debug("Feed worker stopped")

    def _process_market_feed(self):
        num_assets = self._bot.num_assets
        
        for asset_no in range(num_assets):
            try:
                trades = self._bot.last_trades(asset_no)
                
                for i in range(len(trades)):
                    event = trades[i]
                    
                    if event['ev'] & TRADE_EVENT:
                        trade = Trade.from_event(event, asset_no)
                        try:
                            self._trade_queue.put_nowait(trade)
                        except:
                            logger.warning("Trade queue full, dropping event")
                    
                    elif event['ev'] & (DEPTH_EVENT | DEPTH_BBO_EVENT):
                        depth = self._bot.depth(asset_no)
                        timestamp = int(event['exch_ts'])
                        book_update = BookUpdate.from_depth(depth, timestamp, asset_no)
                        try:
                            self._book_queue.put_nowait(book_update)
                        except:
                            logger.warning("Book queue full, dropping event")
                    
                    elif event['ev'] & DEPTH_SNAPSHOT_EVENT:
                        depth = self._bot.depth(asset_no)
                        timestamp = int(event['exch_ts'])
                        snapshot = DepthSnapshot.from_depth(depth, timestamp, asset_no)
                        try:
                            self._snapshot_queue.put_nowait(snapshot)
                        except:
                            logger.warning("Snapshot queue full, dropping event")
                
                self._bot.clear_last_trades(asset_no)
                
            except Exception as e:
                logger.exception(f"Error processing feed for asset {asset_no}")

    def _process_order_response(self):
        pass

    def _health_worker(self):
        logger.debug("Health worker started")
        
        while not self._stop_event.is_set():
            try:
                self._update_health()
            except Exception as e:
                logger.exception("Exception in health worker")
            
            self._stop_event.wait(self._health_check_interval)
        
        logger.debug("Health worker stopped")

    def _update_health(self):
        num_assets = self._bot.num_assets
        
        connected = False
        feed_latency = None
        order_latency = None
        last_feed_time = None
        last_order_time = None
        
        for asset_no in range(num_assets):
            try:
                latency = self._bot.feed_latency(asset_no)
                if latency:
                    exch_ts, local_ts = latency
                    feed_latency = local_ts - exch_ts
                    last_feed_time = local_ts
                    connected = True
                
                latency = self._bot.order_latency(asset_no)
                if latency:
                    req_ts, exch_ts, resp_ts = latency
                    order_latency = resp_ts - req_ts
                    last_order_time = resp_ts
                    
            except Exception as e:
                logger.debug(f"Error checking health for asset {asset_no}: {e}")
        
        with self._lock:
            old_connected = self._health.connected
            self._health = ConnectionHealth(
                connected=connected,
                feed_latency_ns=feed_latency,
                order_latency_ns=order_latency,
                last_feed_time=last_feed_time,
                last_order_time=last_order_time
            )
            
            if old_connected and not connected:
                logger.warning("Connection lost")
                if self._on_connection_lost:
                    self._on_connection_lost()

    async def get_trade(self, timeout: Optional[float] = None) -> Optional[Trade]:
        loop = asyncio.get_event_loop()
        try:
            trade = await loop.run_in_executor(
                None,
                self._trade_queue.get,
                True,
                timeout or 0.1
            )
            return trade
        except Empty:
            return None

    async def get_book_update(self, timeout: Optional[float] = None) -> Optional[BookUpdate]:
        loop = asyncio.get_event_loop()
        try:
            update = await loop.run_in_executor(
                None,
                self._book_queue.get,
                True,
                timeout or 0.1
            )
            return update
        except Empty:
            return None

    async def get_snapshot(self, timeout: Optional[float] = None) -> Optional[DepthSnapshot]:
        loop = asyncio.get_event_loop()
        try:
            snapshot = await loop.run_in_executor(
                None,
                self._snapshot_queue.get,
                True,
                timeout or 0.1
            )
            return snapshot
        except Empty:
            return None

    def get_trade_nowait(self) -> Optional[Trade]:
        try:
            return self._trade_queue.get_nowait()
        except Empty:
            return None

    def get_book_update_nowait(self) -> Optional[BookUpdate]:
        try:
            return self._book_queue.get_nowait()
        except Empty:
            return None

    def get_snapshot_nowait(self) -> Optional[DepthSnapshot]:
        try:
            return self._snapshot_queue.get_nowait()
        except Empty:
            return None

    @property
    def health(self) -> ConnectionHealth:
        with self._lock:
            return self._health

    def _generate_order_id(self) -> int:
        with self._order_id_lock:
            order_id = self._next_order_id
            self._next_order_id += 1
            return order_id

    def submit_order(
        self,
        side: Side,
        price: float,
        qty: float,
        asset_no: int = 0,
        order_id: Optional[int] = None,
        time_in_force: int = GTC,
        order_type: int = LIMIT,
        wait: bool = False
    ) -> OrderResponse:
        if order_id is None:
            order_id = self._generate_order_id()
        
        try:
            if side == Side.BUY:
                result = self._bot.submit_buy_order(
                    asset_no, order_id, price, qty, time_in_force, order_type, wait
                )
            else:
                result = self._bot.submit_sell_order(
                    asset_no, order_id, price, qty, time_in_force, order_type, wait
                )
            
            if result == 0:
                return OrderResponse(
                    order_id=order_id,
                    status="submitted",
                    asset_no=asset_no
                )
            else:
                error_msg = self._decode_error(result)
                return OrderResponse(
                    order_id=order_id,
                    status="error",
                    asset_no=asset_no,
                    error=error_msg
                )
                
        except Exception as e:
            logger.exception("Error submitting order")
            return OrderResponse(
                order_id=order_id,
                status="error",
                asset_no=asset_no,
                error=str(e)
            )

    def cancel_order(
        self,
        order_id: int,
        asset_no: int = 0,
        wait: bool = False
    ) -> OrderResponse:
        try:
            result = self._bot.cancel(asset_no, order_id, wait)
            
            if result == 0:
                return OrderResponse(
                    order_id=order_id,
                    status="cancelled",
                    asset_no=asset_no
                )
            else:
                error_msg = self._decode_error(result)
                return OrderResponse(
                    order_id=order_id,
                    status="error",
                    asset_no=asset_no,
                    error=error_msg
                )
                
        except Exception as e:
            logger.exception("Error cancelling order")
            return OrderResponse(
                order_id=order_id,
                status="error",
                asset_no=asset_no,
                error=str(e)
            )

    def get_position(self, asset_no: int = 0) -> float:
        try:
            return self._bot.position(asset_no)
        except Exception as e:
            logger.exception(f"Error getting position for asset {asset_no}")
            return 0.0

    def get_orders(self, asset_no: int = 0) -> dict:
        try:
            orders_dict = self._bot.orders(asset_no)
            result = {}
            values = orders_dict.values()
            while True:
                order = values.next()
                if order is None:
                    break
                result[order.order_id] = {
                    'order_id': order.order_id,
                    'side': 'buy' if order.side == BUY else 'sell',
                    'price': order.price,
                    'qty': order.qty,
                    'leaves_qty': order.leaves_qty,
                    'status': order.status
                }
            return result
        except Exception as e:
            logger.exception(f"Error getting orders for asset {asset_no}")
            return {}

    @staticmethod
    def _decode_error(code: int) -> str:
        error_map = {
            1: "End of data",
            10: "Order ID already exists",
            12: "Order not found",
            14: "Invalid order status",
            16: "Instrument not found",
            17: "Timeout",
            18: "Interrupted",
            19: "Custom error"
        }
        return error_map.get(code, f"Unknown error code: {code}")

    @property
    def current_timestamp(self) -> int:
        return self._bot.current_timestamp

    @property
    def num_assets(self) -> int:
        return self._bot.num_assets
