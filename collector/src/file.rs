use std::{
    collections::{HashMap, hash_map::Entry},
    fs::{self, File},
    io,
    io::Write,
    path::Path,
};

use chrono::{DateTime, NaiveDate, Utc};
use flate2::{Compression, write::GzEncoder};
use tracing::info;

pub struct RotatingFile {
    date: NaiveDate,
    path: String,
    file: Option<GzEncoder<File>>,
}

impl RotatingFile {
    fn create(datetime: DateTime<Utc>, path: &str) -> Result<GzEncoder<File>, io::Error> {
        // Ensure parent directory exists
        if let Some(parent) = Path::new(path).parent() {
            fs::create_dir_all(parent)?;
        }
        let date = datetime.date_naive().format("%Y%m%d");
        let file = File::options()
            .create(true)
            .write(true)
            .open(format!("{path}_{date}.gz"))?;
        Ok(GzEncoder::new(file, Compression::default()))
    }

    pub fn new(datetime: DateTime<Utc>, path: String) -> Result<Self, io::Error> {
        Ok(Self {
            date: datetime.date_naive(),
            file: Some(Self::create(datetime, &path)?),
            path,
        })
    }

    pub fn write(&mut self, datetime: DateTime<Utc>, data: String) -> Result<(), io::Error> {
        let date = datetime.date_naive();
        if date != self.date {
            let file = self.file.take().unwrap();
            let _ = file.finish();
            self.file = Some(Self::create(datetime, &self.path)?);
            self.date = date;
            info!(%date, %self.path, "date is changed");
        }
        let timestamp = datetime.timestamp_nanos_opt().unwrap();
        self.file
            .as_mut()
            .unwrap()
            .write_all(format!("{timestamp} {data}\n").as_bytes())
    }
}

impl Drop for RotatingFile {
    fn drop(&mut self) {
        if let Some(file) = self.file.take() {
            let _ = file.finish();
        }
    }
}

/// Maps Binance event types to file-friendly names
pub fn event_type_to_file_key(event_type: &str) -> &str {
    match event_type {
        "trade" => "trade",
        "aggTrade" => "aggtrade",
        "bookTicker" => "bookticker",
        "depthUpdate" => "depth",
        "forceOrder" => "liquidation",
        "markPriceUpdate" => "markprice",
        "kline" => "kline",
        "24hrTicker" => "ticker24h",
        "24hrMiniTicker" => "miniticker24h",
        other => other,
    }
}

pub struct Writer {
    path: String,
    file: HashMap<String, RotatingFile>,
}

impl Writer {
    pub fn new(path: &str) -> Self {
        Self {
            path: path.to_string(),
            file: Default::default(),
        }
    }

    /// Write data with automatic event type extraction and routing
    /// Data is routed to: <path>/<symbol>/<event_type>_YYYYMMDD.gz
    pub fn write(
        &mut self,
        recv_time: DateTime<Utc>,
        symbol: String,
        data: String,
    ) -> Result<(), anyhow::Error> {
        // Try to extract event type from the JSON data
        // We need to extract and convert to owned String before moving data
        let event_type = Self::extract_event_type(&data).map(|s| s.to_string());
        self.write_with_event_type_owned(recv_time, symbol, event_type, data)
    }

    /// Write data with explicit event type routing (owned version)
    /// Data is routed to: <path>/<symbol>/<event_type>_YYYYMMDD.gz
    fn write_with_event_type_owned(
        &mut self,
        recv_time: DateTime<Utc>,
        symbol: String,
        event_type: Option<String>,
        data: String,
    ) -> Result<(), anyhow::Error> {
        let symbol_lower = symbol.to_lowercase();
        let file_key = match &event_type {
            Some(et) => event_type_to_file_key(et),
            None => "unknown",
        };

        // Create composite key for the file: symbol/event_type
        let composite_key = format!("{}/{}", symbol_lower, file_key);

        match self.file.entry(composite_key.clone()) {
            Entry::Occupied(mut entry) => {
                entry.get_mut().write(recv_time, data)?;
            }
            Entry::Vacant(entry) => {
                let path = &self.path;
                // Create path: <base_path>/<symbol>/<event_type>
                let file_path = format!("{}/{}/{}", path, symbol_lower, file_key);
                entry
                    .insert(RotatingFile::new(recv_time, file_path)?)
                    .write(recv_time, data)?;
            }
        }
        Ok(())
    }

    /// Write data with explicit event type routing
    /// Data is routed to: <path>/<symbol>/<event_type>_YYYYMMDD.gz
    #[allow(dead_code)]
    pub fn write_with_event_type(
        &mut self,
        recv_time: DateTime<Utc>,
        symbol: String,
        event_type: Option<&str>,
        data: String,
    ) -> Result<(), anyhow::Error> {
        self.write_with_event_type_owned(recv_time, symbol, event_type.map(|s| s.to_string()), data)
    }

    /// Extract the event type from JSON data
    /// Looks for "e" field in the data object or "data.e" for combined stream format
    fn extract_event_type(data: &str) -> Option<&str> {
        // For efficiency, do a quick string search before full JSON parsing
        // Binance uses "e": for event type
        if let Some(pos) = data.find("\"e\":") {
            // Find the start of the value (after the colon and possible whitespace/quote)
            let after_colon = &data[pos + 4..];
            let trimmed = after_colon.trim_start();
            if trimmed.starts_with('"') {
                // Find the closing quote
                let value_start = 1;
                if let Some(end) = trimmed[value_start..].find('"') {
                    let event_type = &trimmed[value_start..value_start + end];
                    return Some(event_type);
                }
            }
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;
    use tempfile::tempdir;

    #[test]
    fn test_event_type_to_file_key() {
        assert_eq!(event_type_to_file_key("trade"), "trade");
        assert_eq!(event_type_to_file_key("depthUpdate"), "depth");
        assert_eq!(event_type_to_file_key("forceOrder"), "liquidation");
        assert_eq!(event_type_to_file_key("markPriceUpdate"), "markprice");
        assert_eq!(event_type_to_file_key("bookTicker"), "bookticker");
        assert_eq!(event_type_to_file_key("unknown_type"), "unknown_type");
    }

    #[test]
    fn test_extract_event_type_trade() {
        let data = r#"{"stream":"btcusdt@trade","data":{"e":"trade","E":123456789,"s":"BTCUSDT","t":12345,"p":"50000.00","q":"0.001"}}"#;
        assert_eq!(Writer::extract_event_type(data), Some("trade"));
    }

    #[test]
    fn test_extract_event_type_depth() {
        let data = r#"{"stream":"btcusdt@depth","data":{"e":"depthUpdate","E":123456789,"s":"BTCUSDT","U":1,"u":2}}"#;
        assert_eq!(Writer::extract_event_type(data), Some("depthUpdate"));
    }

    #[test]
    fn test_extract_event_type_liquidation() {
        let data = r#"{"stream":"btcusdt@forceOrder","data":{"e":"forceOrder","E":123456789,"o":{"s":"BTCUSDT"}}}"#;
        assert_eq!(Writer::extract_event_type(data), Some("forceOrder"));
    }

    #[test]
    fn test_extract_event_type_mark_price() {
        let data = r#"{"stream":"btcusdt@markPrice","data":{"e":"markPriceUpdate","E":123456789,"s":"BTCUSDT","p":"50000.00"}}"#;
        assert_eq!(Writer::extract_event_type(data), Some("markPriceUpdate"));
    }

    #[test]
    fn test_extract_event_type_no_event() {
        let data = r#"{"lastUpdateId":1234,"bids":[["50000.00","1.0"]],"asks":[["50001.00","1.0"]]}"#;
        assert_eq!(Writer::extract_event_type(data), None);
    }

    #[test]
    fn test_writer_creates_nested_directories() {
        let dir = tempdir().unwrap();
        let base_path = dir.path().to_str().unwrap();
        let mut writer = Writer::new(base_path);

        let recv_time = Utc.with_ymd_and_hms(2024, 1, 15, 12, 0, 0).unwrap();
        let trade_data = r#"{"stream":"btcusdt@trade","data":{"e":"trade","E":123456789,"s":"BTCUSDT","t":12345,"p":"50000.00","q":"0.001"}}"#;

        writer
            .write(recv_time, "BTCUSDT".to_string(), trade_data.to_string())
            .unwrap();

        // Drop writer to flush and close files
        drop(writer);

        // Check that nested directory structure was created
        let expected_file = format!("{}/btcusdt/trade_20240115.gz", base_path);
        assert!(
            Path::new(&expected_file).exists(),
            "Expected file {} does not exist",
            expected_file
        );
    }

    #[test]
    fn test_writer_routes_different_event_types() {
        let dir = tempdir().unwrap();
        let base_path = dir.path().to_str().unwrap();
        let mut writer = Writer::new(base_path);

        let recv_time = Utc.with_ymd_and_hms(2024, 1, 15, 12, 0, 0).unwrap();

        // Write trade event
        let trade_data = r#"{"stream":"btcusdt@trade","data":{"e":"trade","E":123456789,"s":"BTCUSDT"}}"#;
        writer
            .write(recv_time, "BTCUSDT".to_string(), trade_data.to_string())
            .unwrap();

        // Write depth event
        let depth_data = r#"{"stream":"btcusdt@depth","data":{"e":"depthUpdate","E":123456789,"s":"BTCUSDT"}}"#;
        writer
            .write(recv_time, "BTCUSDT".to_string(), depth_data.to_string())
            .unwrap();

        // Write liquidation event
        let liq_data = r#"{"stream":"btcusdt@forceOrder","data":{"e":"forceOrder","E":123456789,"o":{"s":"BTCUSDT"}}}"#;
        writer
            .write(recv_time, "BTCUSDT".to_string(), liq_data.to_string())
            .unwrap();

        // Write mark price event
        let mark_data = r#"{"stream":"btcusdt@markPrice","data":{"e":"markPriceUpdate","E":123456789,"s":"BTCUSDT"}}"#;
        writer
            .write(recv_time, "BTCUSDT".to_string(), mark_data.to_string())
            .unwrap();

        drop(writer);

        // Verify all files were created in correct locations
        assert!(Path::new(&format!("{}/btcusdt/trade_20240115.gz", base_path)).exists());
        assert!(Path::new(&format!("{}/btcusdt/depth_20240115.gz", base_path)).exists());
        assert!(Path::new(&format!("{}/btcusdt/liquidation_20240115.gz", base_path)).exists());
        assert!(Path::new(&format!("{}/btcusdt/markprice_20240115.gz", base_path)).exists());
    }

    #[test]
    fn test_writer_handles_multiple_symbols() {
        let dir = tempdir().unwrap();
        let base_path = dir.path().to_str().unwrap();
        let mut writer = Writer::new(base_path);

        let recv_time = Utc.with_ymd_and_hms(2024, 1, 15, 12, 0, 0).unwrap();

        // Write BTCUSDT trade
        let btc_data = r#"{"data":{"e":"trade","s":"BTCUSDT"}}"#;
        writer
            .write(recv_time, "BTCUSDT".to_string(), btc_data.to_string())
            .unwrap();

        // Write ETHUSDT trade
        let eth_data = r#"{"data":{"e":"trade","s":"ETHUSDT"}}"#;
        writer
            .write(recv_time, "ETHUSDT".to_string(), eth_data.to_string())
            .unwrap();

        drop(writer);

        // Verify separate directories for each symbol
        assert!(Path::new(&format!("{}/btcusdt/trade_20240115.gz", base_path)).exists());
        assert!(Path::new(&format!("{}/ethusdt/trade_20240115.gz", base_path)).exists());
    }

    #[test]
    fn test_writer_handles_unknown_event_type() {
        let dir = tempdir().unwrap();
        let base_path = dir.path().to_str().unwrap();
        let mut writer = Writer::new(base_path);

        let recv_time = Utc.with_ymd_and_hms(2024, 1, 15, 12, 0, 0).unwrap();

        // Write data without event type (like depth snapshot)
        let snapshot_data = r#"{"lastUpdateId":1234,"bids":[],"asks":[]}"#;
        writer
            .write(recv_time, "BTCUSDT".to_string(), snapshot_data.to_string())
            .unwrap();

        drop(writer);

        // Should be written to "unknown" event type
        assert!(Path::new(&format!("{}/btcusdt/unknown_20240115.gz", base_path)).exists());
    }

    #[test]
    fn test_writer_with_explicit_event_type() {
        let dir = tempdir().unwrap();
        let base_path = dir.path().to_str().unwrap();
        let mut writer = Writer::new(base_path);

        let recv_time = Utc.with_ymd_and_hms(2024, 1, 15, 12, 0, 0).unwrap();

        // Write with explicit event type for snapshot data
        let snapshot_data = r#"{"lastUpdateId":1234,"bids":[],"asks":[]}"#;
        writer
            .write_with_event_type(
                recv_time,
                "BTCUSDT".to_string(),
                Some("depthSnapshot"),
                snapshot_data.to_string(),
            )
            .unwrap();

        drop(writer);

        // Should use the explicit event type
        assert!(Path::new(&format!("{}/btcusdt/depthSnapshot_20240115.gz", base_path)).exists());
    }

    #[test]
    fn test_rotating_file_date_rotation() {
        let dir = tempdir().unwrap();
        let base_path = dir.path().to_str().unwrap();
        let file_path = format!("{}/test", base_path);

        let day1 = Utc.with_ymd_and_hms(2024, 1, 15, 23, 59, 59).unwrap();
        let day2 = Utc.with_ymd_and_hms(2024, 1, 16, 0, 0, 1).unwrap();

        let mut rf = RotatingFile::new(day1, file_path.clone()).unwrap();
        rf.write(day1, "data1".to_string()).unwrap();
        rf.write(day2, "data2".to_string()).unwrap();

        drop(rf);

        // Both files should exist
        assert!(Path::new(&format!("{}_20240115.gz", file_path)).exists());
        assert!(Path::new(&format!("{}_20240116.gz", file_path)).exists());
    }
}
