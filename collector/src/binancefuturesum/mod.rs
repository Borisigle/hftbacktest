mod http;

use std::collections::HashMap;

use chrono::{DateTime, Utc};
pub use http::{fetch_depth_snapshot, keep_connection};
use tokio::sync::mpsc::{UnboundedSender, unbounded_channel};
use tokio_tungstenite::tungstenite::Utf8Bytes;
use tracing::{error, warn};

use crate::{error::ConnectorError, throttler::Throttler};

/// Extract symbol from various Binance event types
/// Returns the symbol and event type if found
fn extract_symbol_and_event(j_data: &serde_json::Value) -> Option<(String, String)> {
    let obj = j_data.as_object()?;

    // Get event type first
    let ev = obj.get("e")?.as_str()?;

    // Handle different event structures
    let symbol = match ev {
        // forceOrder has symbol nested in "o" object
        "forceOrder" => obj.get("o")?.as_object()?.get("s")?.as_str()?,
        // Most events have "s" at top level
        _ => obj.get("s")?.as_str()?,
    };

    Some((symbol.to_string(), ev.to_string()))
}

/// Handle incoming WebSocket messages, routing them to appropriate files
/// and maintaining depth snapshot bookkeeping
pub fn handle(
    prev_u_map: &mut HashMap<String, i64>,
    writer_tx: &UnboundedSender<(DateTime<Utc>, String, String)>,
    recv_time: DateTime<Utc>,
    data: Utf8Bytes,
    throttler: &Throttler,
) -> Result<(), ConnectorError> {
    let j: serde_json::Value = serde_json::from_str(data.as_str())?;

    // Handle combined stream format: {"stream": "...", "data": {...}}
    if let Some(j_data) = j.get("data")
        && let Some((symbol, ev)) = extract_symbol_and_event(j_data)
    {
        // Handle depth update bookkeeping for resync detection
        if ev == "depthUpdate" {
            handle_depth_update(j_data, &symbol, prev_u_map, writer_tx, throttler)?;
        }

        // Forward the event to the writer with original data
        let _ = writer_tx.send((recv_time, symbol, data.to_string()));
    }

    Ok(())
}

/// Handle depth update events and trigger snapshot fetch if needed
fn handle_depth_update(
    j_data: &serde_json::Value,
    symbol: &str,
    prev_u_map: &mut HashMap<String, i64>,
    writer_tx: &UnboundedSender<(DateTime<Utc>, String, String)>,
    throttler: &Throttler,
) -> Result<(), ConnectorError> {
    let u = j_data
        .get("u")
        .ok_or(ConnectorError::FormatError)?
        .as_i64()
        .ok_or(ConnectorError::FormatError)?;
    let pu = j_data
        .get("pu")
        .ok_or(ConnectorError::FormatError)?
        .as_i64()
        .ok_or(ConnectorError::FormatError)?;

    let prev_u = prev_u_map.get(symbol);
    if prev_u.is_none() || pu != *prev_u.unwrap() {
        warn!(%symbol, "missing depth feed has been detected.");
        let symbol_ = symbol.to_string();
        let writer_tx_ = writer_tx.clone();
        let mut throttler_ = throttler.clone();
        tokio::spawn(async move {
            match throttler_.execute(fetch_depth_snapshot(&symbol_)).await {
                Some(Ok(data)) => {
                    let recv_time = Utc::now();
                    let _ = writer_tx_.send((recv_time, symbol_, data));
                }
                Some(Err(error)) => {
                    error!(
                        symbol = symbol_,
                        ?error,
                        "couldn't fetch the depth snapshot."
                    );
                }
                None => {
                    warn!(
                        symbol = symbol_,
                        "Fetching the depth snapshot is rate-limited."
                    )
                }
            }
        });
    }
    *prev_u_map.entry(symbol.to_string()).or_insert(0) = u;

    Ok(())
}

pub async fn run_collection(
    streams: Vec<String>,
    symbols: Vec<String>,
    writer_tx: UnboundedSender<(DateTime<Utc>, String, String)>,
) -> Result<(), anyhow::Error> {
    let mut prev_u_map = HashMap::new();
    let (ws_tx, mut ws_rx) = unbounded_channel();
    let h = tokio::spawn(keep_connection(streams, symbols, ws_tx.clone()));
    // https://www.binance.com/en/support/faq/rate-limits-on-binance-futures-281596e222414cdd9051664ea621cdc3
    // The default rate limit per IP is 2,400/min and the weight is 20 at a depth of 1000.
    // The maximum request rate for fetching snapshots is 120 per minute.
    // Sets the rate limit with a margin to account for connection requests.
    let throttler = Throttler::new(100);
    while let Some((recv_time, data)) = ws_rx.recv().await {
        if let Err(error) = handle(&mut prev_u_map, &writer_tx, recv_time, data, &throttler) {
            error!(?error, "couldn't handle the received data.");
        }
    }
    let _ = h.await;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::sync::mpsc::unbounded_channel;

    fn make_utf8_bytes(s: &str) -> Utf8Bytes {
        Utf8Bytes::from(s.to_string())
    }

    #[tokio::test]
    async fn test_handle_trade_event() {
        let mut prev_u_map = HashMap::new();
        let (writer_tx, mut writer_rx) = unbounded_channel();
        let throttler = Throttler::new(100);
        let recv_time = Utc::now();

        let trade_data = r#"{"stream":"btcusdt@trade","data":{"e":"trade","E":1234567890123,"s":"BTCUSDT","t":12345,"p":"50000.00","q":"0.001","T":1234567890123,"m":true}}"#;

        handle(
            &mut prev_u_map,
            &writer_tx,
            recv_time,
            make_utf8_bytes(trade_data),
            &throttler,
        )
        .unwrap();

        let (_, symbol, data) = writer_rx.recv().await.unwrap();
        assert_eq!(symbol, "BTCUSDT");
        assert!(data.contains("trade"));
    }

    #[tokio::test]
    async fn test_handle_depth_update_event() {
        let mut prev_u_map = HashMap::new();
        let (writer_tx, mut writer_rx) = unbounded_channel();
        let throttler = Throttler::new(100);
        let recv_time = Utc::now();

        // First depth update should trigger snapshot fetch (prev_u not set)
        let depth_data = r#"{"stream":"btcusdt@depth@0ms","data":{"e":"depthUpdate","E":1234567890123,"s":"BTCUSDT","U":100,"u":110,"pu":99,"b":[["50000.00","1.0"]],"a":[["50001.00","1.0"]]}}"#;

        handle(
            &mut prev_u_map,
            &writer_tx,
            recv_time,
            make_utf8_bytes(depth_data),
            &throttler,
        )
        .unwrap();

        // Verify event was forwarded
        let (_, symbol, data) = writer_rx.recv().await.unwrap();
        assert_eq!(symbol, "BTCUSDT");
        assert!(data.contains("depthUpdate"));

        // Verify prev_u was updated
        assert_eq!(prev_u_map.get("BTCUSDT"), Some(&110));
    }

    #[tokio::test]
    async fn test_handle_depth_update_continuous() {
        let mut prev_u_map = HashMap::new();
        let (writer_tx, mut writer_rx) = unbounded_channel();
        let throttler = Throttler::new(100);
        let recv_time = Utc::now();

        // Set initial u value
        prev_u_map.insert("BTCUSDT".to_string(), 100);

        // Continuous update (pu matches prev_u)
        let depth_data = r#"{"stream":"btcusdt@depth@0ms","data":{"e":"depthUpdate","E":1234567890123,"s":"BTCUSDT","U":101,"u":110,"pu":100,"b":[],"a":[]}}"#;

        handle(
            &mut prev_u_map,
            &writer_tx,
            recv_time,
            make_utf8_bytes(depth_data),
            &throttler,
        )
        .unwrap();

        // Should receive only the depth update (no snapshot since continuous)
        let (_, symbol, _) = writer_rx.recv().await.unwrap();
        assert_eq!(symbol, "BTCUSDT");

        // Verify prev_u was updated
        assert_eq!(prev_u_map.get("BTCUSDT"), Some(&110));
    }

    #[tokio::test]
    async fn test_handle_liquidation_event() {
        let mut prev_u_map = HashMap::new();
        let (writer_tx, mut writer_rx) = unbounded_channel();
        let throttler = Throttler::new(100);
        let recv_time = Utc::now();

        let liq_data = r#"{"stream":"btcusdt@forceOrder","data":{"e":"forceOrder","E":1234567890123,"o":{"s":"BTCUSDT","S":"SELL","o":"LIMIT","f":"IOC","q":"0.014","p":"50000.00","ap":"50010.00","X":"FILLED","l":"0.014","z":"0.014","T":1234567890123}}}"#;

        handle(
            &mut prev_u_map,
            &writer_tx,
            recv_time,
            make_utf8_bytes(liq_data),
            &throttler,
        )
        .unwrap();

        let (_, symbol, data) = writer_rx.recv().await.unwrap();
        assert_eq!(symbol, "BTCUSDT");
        assert!(data.contains("forceOrder"));
    }

    #[tokio::test]
    async fn test_handle_mark_price_event() {
        let mut prev_u_map = HashMap::new();
        let (writer_tx, mut writer_rx) = unbounded_channel();
        let throttler = Throttler::new(100);
        let recv_time = Utc::now();

        let mark_data = r#"{"stream":"btcusdt@markPrice@1s","data":{"e":"markPriceUpdate","E":1234567890123,"s":"BTCUSDT","p":"50000.00","i":"50001.00","P":"50000.50","r":"0.00010000","T":1234567890123}}"#;

        handle(
            &mut prev_u_map,
            &writer_tx,
            recv_time,
            make_utf8_bytes(mark_data),
            &throttler,
        )
        .unwrap();

        let (_, symbol, data) = writer_rx.recv().await.unwrap();
        assert_eq!(symbol, "BTCUSDT");
        assert!(data.contains("markPriceUpdate"));
    }

    #[tokio::test]
    async fn test_handle_book_ticker_event() {
        let mut prev_u_map = HashMap::new();
        let (writer_tx, mut writer_rx) = unbounded_channel();
        let throttler = Throttler::new(100);
        let recv_time = Utc::now();

        let book_data = r#"{"stream":"btcusdt@bookTicker","data":{"e":"bookTicker","u":12345678,"s":"BTCUSDT","b":"50000.00","B":"1.5","a":"50001.00","A":"2.0","T":1234567890123,"E":1234567890123}}"#;

        handle(
            &mut prev_u_map,
            &writer_tx,
            recv_time,
            make_utf8_bytes(book_data),
            &throttler,
        )
        .unwrap();

        let (_, symbol, data) = writer_rx.recv().await.unwrap();
        assert_eq!(symbol, "BTCUSDT");
        assert!(data.contains("bookTicker"));
    }

    #[tokio::test]
    async fn test_handle_multiple_symbols() {
        let mut prev_u_map = HashMap::new();
        let (writer_tx, mut writer_rx) = unbounded_channel();
        let throttler = Throttler::new(100);
        let recv_time = Utc::now();

        // BTC trade
        let btc_data = r#"{"stream":"btcusdt@trade","data":{"e":"trade","E":1234567890123,"s":"BTCUSDT","t":1,"p":"50000.00","q":"0.001"}}"#;
        handle(
            &mut prev_u_map,
            &writer_tx,
            recv_time,
            make_utf8_bytes(btc_data),
            &throttler,
        )
        .unwrap();

        // ETH trade
        let eth_data = r#"{"stream":"ethusdt@trade","data":{"e":"trade","E":1234567890123,"s":"ETHUSDT","t":1,"p":"3000.00","q":"0.01"}}"#;
        handle(
            &mut prev_u_map,
            &writer_tx,
            recv_time,
            make_utf8_bytes(eth_data),
            &throttler,
        )
        .unwrap();

        let (_, symbol1, _) = writer_rx.recv().await.unwrap();
        let (_, symbol2, _) = writer_rx.recv().await.unwrap();

        assert_eq!(symbol1, "BTCUSDT");
        assert_eq!(symbol2, "ETHUSDT");
    }

    #[test]
    fn test_extract_symbol_and_event_trade() {
        let data: serde_json::Value =
            serde_json::from_str(r#"{"e":"trade","s":"BTCUSDT","t":1}"#).unwrap();
        let result = extract_symbol_and_event(&data);
        assert_eq!(result, Some(("BTCUSDT".to_string(), "trade".to_string())));
    }

    #[test]
    fn test_extract_symbol_and_event_force_order() {
        let data: serde_json::Value = serde_json::from_str(
            r#"{"e":"forceOrder","E":1234,"o":{"s":"BTCUSDT","S":"SELL","q":"0.01"}}"#,
        )
        .unwrap();
        let result = extract_symbol_and_event(&data);
        assert_eq!(
            result,
            Some(("BTCUSDT".to_string(), "forceOrder".to_string()))
        );
    }

    #[test]
    fn test_extract_symbol_and_event_invalid() {
        let data: serde_json::Value = serde_json::from_str(r#"{"invalid":"data"}"#).unwrap();
        let result = extract_symbol_and_event(&data);
        assert_eq!(result, None);
    }
}
