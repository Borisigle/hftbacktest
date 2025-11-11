use std::time::Duration;

use chrono::Utc;
use pyo3::prelude::*;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;

#[derive(Clone)]
pub struct TradeRow {
    pub timestamp: i64,
    pub symbol: String,
    pub side: String,
    pub size: f64,
    pub price: f64,
}

impl TradeRow {
    pub fn to_dict(&self, py: Python) -> PyObject {
        let dict = pyo3::types::PyDict::new(py);
        dict.set_item("timestamp", self.timestamp)
            .unwrap_or_else(|e| {
                eprintln!("Failed to set timestamp: {}", e);
            });
        dict.set_item("symbol", self.symbol.clone())
            .unwrap_or_else(|e| {
                eprintln!("Failed to set symbol: {}", e);
            });
        dict.set_item("side", self.side.clone())
            .unwrap_or_else(|e| {
                eprintln!("Failed to set side: {}", e);
            });
        dict.set_item("size", self.size)
            .unwrap_or_else(|e| {
                eprintln!("Failed to set size: {}", e);
            });
        dict.set_item("price", self.price)
            .unwrap_or_else(|e| {
                eprintln!("Failed to set price: {}", e);
            });
        dict.into()
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BybitTrade {
    #[serde(rename = "execId")]
    pub exec_id: String,
    #[serde(rename = "symbol")]
    pub symbol: String,
    #[serde(rename = "price")]
    pub price: String,
    #[serde(rename = "size")]
    pub size: String,
    #[serde(rename = "side")]
    pub side: String,
    #[serde(rename = "time")]
    pub time: String,
    #[serde(rename = "isBlockTrade")]
    pub is_block_trade: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BybitTradeResponse {
    #[serde(rename = "retCode")]
    pub ret_code: i32,
    #[serde(rename = "retMsg")]
    pub ret_msg: String,
    pub result: TradeResult,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TradeResult {
    pub list: Vec<BybitTrade>,
    #[serde(rename = "nextPageCursor")]
    pub next_page_cursor: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BybitTradeHistoryFetcher {
    client: Client,
    base_url: String,
    api_key: String,
    secret: String,
}

impl BybitTradeHistoryFetcher {
    pub fn new(base_url: String, api_key: String, secret: String) -> Self {
        Self {
            client: Client::new(),
            base_url,
            api_key,
            secret,
        }
    }

    pub async fn fetch_trades(
        &self,
        symbol: &str,
        start_time: i64,
        end_time: i64,
        limit: i32,
    ) -> Result<Vec<TradeRow>, String> {
        let mut all_trades = Vec::new();
        let mut cursor: Option<String> = None;
        let mut retries = 0;
        const MAX_RETRIES: u32 = 5;
        const RATE_LIMIT_BACKOFF_MS: u64 = 50;

        loop {
            let mut query_params = vec![
                format!("symbol={}", symbol),
                format!("startTime={}", start_time),
                format!("endTime={}", end_time),
                format!("limit={}", limit),
            ];

            if let Some(ref c) = cursor {
                query_params.push(format!("cursor={}", c));
            }

            let query_string = query_params.join("&");
            let url = format!("{}/v5/market/trades?{}", self.base_url, query_string);

            let timestamp = Utc::now().timestamp_millis();
            let signature = self.sign_request(&query_string, timestamp)?;

            let response = self
                .client
                .get(&url)
                .header("X-BAPI-SIGN", signature)
                .header("X-BAPI-API-KEY", &self.api_key)
                .header("X-BAPI-TIMESTAMP", timestamp.to_string())
                .header("X-BAPI-RECV-WINDOW", "5000")
                .timeout(Duration::from_secs(10))
                .send()
                .await
                .map_err(|e| format!("Request failed: {}", e))?;

            if response.status() == 429 {
                // Rate limited
                if retries < MAX_RETRIES {
                    retries += 1;
                    let backoff_ms = RATE_LIMIT_BACKOFF_MS * (2_u64.pow(retries - 1));
                    tokio::time::sleep(Duration::from_millis(backoff_ms)).await;
                    continue;
                } else {
                    return Err("Rate limited: max retries exceeded".to_string());
                }
            }

            if !response.status().is_success() {
                return Err(format!("HTTP error: {}", response.status()));
            }

            let resp_body: BybitTradeResponse = response
                .json()
                .await
                .map_err(|e| format!("Failed to parse response: {}", e))?;

            if resp_body.ret_code != 0 {
                return Err(format!(
                    "API error: {} - {}",
                    resp_body.ret_code, resp_body.ret_msg
                ));
            }

            // Convert trades to TradeRow
            for trade in resp_body.result.list {
                let timestamp: i64 = trade
                    .time
                    .parse()
                    .map_err(|_| format!("Failed to parse timestamp: {}", trade.time))?;

                let size: f64 = trade
                    .size
                    .parse()
                    .map_err(|_| format!("Failed to parse size: {}", trade.size))?;

                let price: f64 = trade
                    .price
                    .parse()
                    .map_err(|_| format!("Failed to parse price: {}", trade.price))?;

                all_trades.push(TradeRow {
                    timestamp,
                    symbol: trade.symbol,
                    side: trade.side,
                    size,
                    price,
                });
            }

            // Check if there's a next page
            match resp_body.result.next_page_cursor {
                Some(next_cursor) => {
                    cursor = Some(next_cursor);
                    retries = 0; // Reset retries on successful request
                    tokio::time::sleep(Duration::from_millis(50)).await; // Small delay between requests
                }
                None => {
                    break; // No more pages
                }
            }
        }

        Ok(all_trades)
    }

    fn sign_request(&self, query_string: &str, timestamp: i64) -> Result<String, String> {
        use hmac::{Hmac, Mac};
        use sha2::Sha256;

        let sign_body = format!("{}GET/v5/market/trades{}5000{}", timestamp, query_string, "");
        let mut mac = Hmac::<Sha256>::new_from_slice(self.secret.as_bytes())
            .map_err(|_| "Failed to create HMAC".to_string())?;
        mac.update(sign_body.as_bytes());
        let result = mac.finalize();
        
        // Convert to hex string manually
        let bytes = result.into_bytes();
        let hex_str = bytes
            .iter()
            .map(|b| format!("{:02x}", b))
            .collect::<String>();
        Ok(hex_str)
    }
}

/// Fetch Bybit trade history between two timestamps.
///
/// Args:
///     symbol: Trading symbol (e.g., "BTCUSDT")
///     start_time: Start timestamp in milliseconds
///     end_time: End timestamp in milliseconds
///     limit: Number of trades per request (default 1000, max 1000)
///     api_key: Bybit API key (optional for public endpoint)
///     secret: Bybit API secret (optional for public endpoint)
///     base_url: Base URL for Bybit API (default "https://api.bybit.com")
///
/// Returns:
///     List of dicts with keys: timestamp, symbol, side, size, price
///
/// Raises:
///     RuntimeError: If the API request fails or rate limit is exceeded
#[pyfunction]
#[pyo3(text_signature = "(symbol, start_time, end_time, *, limit=1000, api_key='', secret='', base_url='https://api.bybit.com')")]
pub fn fetch_trades(
    py: Python,
    symbol: String,
    start_time: i64,
    end_time: i64,
    limit: Option<i32>,
    api_key: Option<String>,
    secret: Option<String>,
    base_url: Option<String>,
) -> PyResult<PyObject> {
    let limit = limit.unwrap_or(1000);
    let api_key = api_key.unwrap_or_default();
    let secret = secret.unwrap_or_default();
    let base_url = base_url.unwrap_or_else(|| "https://api.bybit.com".to_string());

    let fetcher = BybitTradeHistoryFetcher::new(base_url, api_key, secret);

    // Create a tokio runtime
    let rt = tokio::runtime::Runtime::new()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let trades = rt
        .block_on(fetcher.fetch_trades(&symbol, start_time, end_time, limit))
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))?;

    let result = trades
        .iter()
        .map(|t| t.to_dict(py))
        .collect::<Vec<_>>();

    Ok(PyList::new(py, result).into())
}

pub use pyo3::types::PyList;
