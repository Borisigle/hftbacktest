from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional


class EventType(IntEnum):
    DEPTH = 1
    TRADE = 2
    DEPTH_CLEAR = 3
    DEPTH_SNAPSHOT = 4
    DEPTH_BBO = 5


class Side(IntEnum):
    BUY = 1
    SELL = -1


@dataclass(frozen=True)
class Trade:
    timestamp: int
    price: float
    qty: float
    side: Side
    asset_no: int = 0

    @classmethod
    def from_event(cls, event, asset_no: int = 0):
        return cls(
            timestamp=int(event['exch_ts']),
            price=float(event['px']),
            qty=float(event['qty']),
            side=Side.BUY if event['ev'] & 0x01 else Side.SELL,
            asset_no=asset_no
        )


@dataclass(frozen=True)
class BookLevel:
    price: float
    qty: float


@dataclass(frozen=True)
class BookUpdate:
    timestamp: int
    bid_price: float
    bid_qty: float
    ask_price: float
    ask_qty: float
    asset_no: int = 0

    @classmethod
    def from_depth(cls, depth, timestamp: int, asset_no: int = 0):
        return cls(
            timestamp=timestamp,
            bid_price=depth.best_bid,
            bid_qty=depth.best_bid_qty,
            ask_price=depth.best_ask,
            ask_qty=depth.best_ask_qty,
            asset_no=asset_no
        )


@dataclass(frozen=True)
class DepthSnapshot:
    timestamp: int
    bids: List[BookLevel]
    asks: List[BookLevel]
    asset_no: int = 0

    @classmethod
    def from_depth(cls, depth, timestamp: int, asset_no: int = 0):
        snapshot = depth.snapshot
        bids = []
        asks = []
        
        for level in snapshot:
            price = float(level['px'])
            qty = float(level['qty'])
            if qty > 0:
                if level['ev'] & 0x01:
                    bids.append(BookLevel(price, qty))
                else:
                    asks.append(BookLevel(price, qty))
        
        bids.sort(key=lambda x: x.price, reverse=True)
        asks.sort(key=lambda x: x.price)
        
        return cls(
            timestamp=timestamp,
            bids=bids,
            asks=asks,
            asset_no=asset_no
        )


@dataclass
class OrderRequest:
    order_id: int
    price: float
    qty: float
    side: Side
    asset_no: int = 0
    time_in_force: int = 0
    order_type: int = 0


@dataclass
class OrderResponse:
    order_id: int
    status: str
    filled_qty: float = 0.0
    avg_price: float = 0.0
    timestamp: Optional[int] = None
    asset_no: int = 0
    error: Optional[str] = None


@dataclass
class ConnectionHealth:
    connected: bool
    feed_latency_ns: Optional[int] = None
    order_latency_ns: Optional[int] = None
    last_feed_time: Optional[int] = None
    last_order_time: Optional[int] = None
