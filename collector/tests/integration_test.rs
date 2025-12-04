//! Integration tests for the collector's event handling and routing logic.
//!
//! These tests use tokio channels to simulate WebSocket messages and verify
//! that events are correctly routed to their respective output files.

use std::collections::HashMap;

// Note: These tests use a simplified mock approach since the actual modules
// are in the binary crate. We test the file writing logic independently.

mod file_routing {
    use super::*;

    /// Helper struct to simulate the Writer functionality for testing
    struct TestWriter {
        files: HashMap<String, Vec<String>>,
    }

    impl TestWriter {
        fn new() -> Self {
            Self {
                files: HashMap::new(),
            }
        }

        /// Extract event type from JSON data (same logic as file.rs)
        fn extract_event_type(data: &str) -> Option<String> {
            if let Some(pos) = data.find("\"e\":") {
                let after_colon = &data[pos + 4..];
                let trimmed = after_colon.trim_start();
                if trimmed.starts_with('"') {
                    let value_start = 1;
                    if let Some(end) = trimmed[value_start..].find('"') {
                        return Some(trimmed[value_start..value_start + end].to_string());
                    }
                }
            }
            None
        }

        /// Map event type to file key (same logic as file.rs)
        fn event_type_to_file_key(event_type: &str) -> &'static str {
            match event_type {
                "trade" => "trade",
                "aggTrade" => "aggtrade",
                "bookTicker" => "bookticker",
                "depthUpdate" => "depth",
                "forceOrder" => "liquidation",
                "markPriceUpdate" => "markprice",
                _ => "unknown",
            }
        }

        fn write(&mut self, symbol: &str, data: &str) {
            let event_type = Self::extract_event_type(data);
            let file_key = match &event_type {
                Some(et) => Self::event_type_to_file_key(et),
                None => "unknown",
            };

            let composite_key = format!("{}/{}", symbol.to_lowercase(), file_key);
            self.files
                .entry(composite_key)
                .or_insert_with(Vec::new)
                .push(data.to_string());
        }

        fn get_events(&self, symbol: &str, event_type: &str) -> Option<&Vec<String>> {
            let key = format!("{}/{}", symbol.to_lowercase(), event_type);
            self.files.get(&key)
        }
    }

    #[test]
    fn test_event_routing_trade() {
        let mut writer = TestWriter::new();

        let trade = r#"{"stream":"btcusdt@trade","data":{"e":"trade","E":1234567890123,"s":"BTCUSDT","t":12345,"p":"50000.00","q":"0.001"}}"#;
        writer.write("BTCUSDT", trade);

        let events = writer.get_events("btcusdt", "trade").unwrap();
        assert_eq!(events.len(), 1);
        assert!(events[0].contains("\"e\":\"trade\""));
    }

    #[test]
    fn test_event_routing_depth() {
        let mut writer = TestWriter::new();

        let depth = r#"{"stream":"btcusdt@depth@0ms","data":{"e":"depthUpdate","E":1234567890123,"s":"BTCUSDT","U":100,"u":110,"pu":99,"b":[],"a":[]}}"#;
        writer.write("BTCUSDT", depth);

        let events = writer.get_events("btcusdt", "depth").unwrap();
        assert_eq!(events.len(), 1);
        assert!(events[0].contains("\"e\":\"depthUpdate\""));
    }

    #[test]
    fn test_event_routing_liquidation() {
        let mut writer = TestWriter::new();

        let liquidation = r#"{"stream":"btcusdt@forceOrder","data":{"e":"forceOrder","E":1234567890123,"o":{"s":"BTCUSDT","S":"SELL","o":"LIMIT","f":"IOC","q":"0.014","p":"50000.00"}}}"#;
        writer.write("BTCUSDT", liquidation);

        let events = writer.get_events("btcusdt", "liquidation").unwrap();
        assert_eq!(events.len(), 1);
        assert!(events[0].contains("\"e\":\"forceOrder\""));
    }

    #[test]
    fn test_event_routing_mark_price() {
        let mut writer = TestWriter::new();

        let mark_price = r#"{"stream":"btcusdt@markPrice@1s","data":{"e":"markPriceUpdate","E":1234567890123,"s":"BTCUSDT","p":"50000.00","i":"50001.00"}}"#;
        writer.write("BTCUSDT", mark_price);

        let events = writer.get_events("btcusdt", "markprice").unwrap();
        assert_eq!(events.len(), 1);
        assert!(events[0].contains("\"e\":\"markPriceUpdate\""));
    }

    #[test]
    fn test_event_routing_book_ticker() {
        let mut writer = TestWriter::new();

        let book_ticker = r#"{"stream":"btcusdt@bookTicker","data":{"e":"bookTicker","u":12345678,"s":"BTCUSDT","b":"50000.00","B":"1.5","a":"50001.00","A":"2.0"}}"#;
        writer.write("BTCUSDT", book_ticker);

        let events = writer.get_events("btcusdt", "bookticker").unwrap();
        assert_eq!(events.len(), 1);
        assert!(events[0].contains("\"e\":\"bookTicker\""));
    }

    #[test]
    fn test_event_routing_unknown() {
        let mut writer = TestWriter::new();

        // Depth snapshot has no "e" field
        let snapshot = r#"{"lastUpdateId":1234567890,"bids":[["50000.00","1.0"]],"asks":[["50001.00","1.0"]]}"#;
        writer.write("BTCUSDT", snapshot);

        let events = writer.get_events("btcusdt", "unknown").unwrap();
        assert_eq!(events.len(), 1);
        assert!(events[0].contains("lastUpdateId"));
    }

    #[test]
    fn test_multiple_event_types_same_symbol() {
        let mut writer = TestWriter::new();

        // Write different event types for BTCUSDT
        let trade = r#"{"data":{"e":"trade","s":"BTCUSDT","t":1}}"#;
        let depth = r#"{"data":{"e":"depthUpdate","s":"BTCUSDT","u":1,"pu":0}}"#;
        let liquidation = r#"{"data":{"e":"forceOrder","o":{"s":"BTCUSDT"}}}"#;
        let mark_price = r#"{"data":{"e":"markPriceUpdate","s":"BTCUSDT"}}"#;
        let book_ticker = r#"{"data":{"e":"bookTicker","s":"BTCUSDT"}}"#;

        writer.write("BTCUSDT", trade);
        writer.write("BTCUSDT", depth);
        writer.write("BTCUSDT", liquidation);
        writer.write("BTCUSDT", mark_price);
        writer.write("BTCUSDT", book_ticker);

        // Verify all routed correctly
        assert!(writer.get_events("btcusdt", "trade").is_some());
        assert!(writer.get_events("btcusdt", "depth").is_some());
        assert!(writer.get_events("btcusdt", "liquidation").is_some());
        assert!(writer.get_events("btcusdt", "markprice").is_some());
        assert!(writer.get_events("btcusdt", "bookticker").is_some());
    }

    #[test]
    fn test_multiple_symbols() {
        let mut writer = TestWriter::new();

        let btc_trade = r#"{"data":{"e":"trade","s":"BTCUSDT"}}"#;
        let eth_trade = r#"{"data":{"e":"trade","s":"ETHUSDT"}}"#;
        let sol_trade = r#"{"data":{"e":"trade","s":"SOLUSDT"}}"#;

        writer.write("BTCUSDT", btc_trade);
        writer.write("ETHUSDT", eth_trade);
        writer.write("SOLUSDT", sol_trade);

        assert!(writer.get_events("btcusdt", "trade").is_some());
        assert!(writer.get_events("ethusdt", "trade").is_some());
        assert!(writer.get_events("solusdt", "trade").is_some());
    }

    #[test]
    fn test_case_insensitive_symbol_routing() {
        let mut writer = TestWriter::new();

        // Different cases should route to same lowercase directory
        writer.write("BTCUSDT", r#"{"data":{"e":"trade","s":"BTCUSDT"}}"#);
        writer.write("btcusdt", r#"{"data":{"e":"trade","s":"btcusdt"}}"#);
        writer.write("BtcUsdt", r#"{"data":{"e":"trade","s":"BtcUsdt"}}"#);

        let events = writer.get_events("btcusdt", "trade").unwrap();
        assert_eq!(events.len(), 3);
    }
}

mod prev_u_bookkeeping {
    use super::*;

    /// Simulates the prev_u_map bookkeeping logic from the handler
    fn update_prev_u_map(
        prev_u_map: &mut HashMap<String, i64>,
        symbol: &str,
        u: i64,
        pu: i64,
    ) -> bool {
        let prev_u = prev_u_map.get(symbol);
        let needs_snapshot = prev_u.is_none() || pu != *prev_u.unwrap();
        *prev_u_map.entry(symbol.to_string()).or_insert(0) = u;
        needs_snapshot
    }

    #[test]
    fn test_first_depth_update_triggers_snapshot() {
        let mut prev_u_map = HashMap::new();

        // First update should trigger snapshot (prev_u not set)
        let needs_snapshot = update_prev_u_map(&mut prev_u_map, "BTCUSDT", 110, 100);
        assert!(needs_snapshot, "First update should trigger snapshot");
        assert_eq!(prev_u_map.get("BTCUSDT"), Some(&110));
    }

    #[test]
    fn test_continuous_updates_no_snapshot() {
        let mut prev_u_map = HashMap::new();
        prev_u_map.insert("BTCUSDT".to_string(), 100);

        // Continuous update (pu matches prev_u) should NOT trigger snapshot
        let needs_snapshot = update_prev_u_map(&mut prev_u_map, "BTCUSDT", 110, 100);
        assert!(!needs_snapshot, "Continuous update should not trigger snapshot");
        assert_eq!(prev_u_map.get("BTCUSDT"), Some(&110));
    }

    #[test]
    fn test_gap_triggers_snapshot() {
        let mut prev_u_map = HashMap::new();
        prev_u_map.insert("BTCUSDT".to_string(), 100);

        // Gap detected (pu doesn't match prev_u) should trigger snapshot
        let needs_snapshot = update_prev_u_map(&mut prev_u_map, "BTCUSDT", 120, 115);
        assert!(needs_snapshot, "Gap should trigger snapshot");
        assert_eq!(prev_u_map.get("BTCUSDT"), Some(&120));
    }

    #[test]
    fn test_multiple_symbols_independent_tracking() {
        let mut prev_u_map = HashMap::new();

        // Initialize BTC
        update_prev_u_map(&mut prev_u_map, "BTCUSDT", 100, 0);

        // ETH first update should trigger snapshot
        let eth_needs = update_prev_u_map(&mut prev_u_map, "ETHUSDT", 50, 40);
        assert!(eth_needs, "First ETH update should trigger snapshot");

        // BTC continuous should NOT trigger
        let btc_needs = update_prev_u_map(&mut prev_u_map, "BTCUSDT", 110, 100);
        assert!(!btc_needs, "Continuous BTC should not trigger");

        // Verify independent tracking
        assert_eq!(prev_u_map.get("BTCUSDT"), Some(&110));
        assert_eq!(prev_u_map.get("ETHUSDT"), Some(&50));
    }

    #[test]
    fn test_sequence_of_updates() {
        let mut prev_u_map = HashMap::new();

        // Simulate a sequence of depth updates
        let updates = vec![
            ("BTCUSDT", 100, 0, true),   // First - needs snapshot
            ("BTCUSDT", 110, 100, false), // Continuous
            ("BTCUSDT", 120, 110, false), // Continuous
            ("BTCUSDT", 140, 130, true),  // Gap detected!
            ("BTCUSDT", 150, 140, false), // Continuous after resync
        ];

        for (symbol, u, pu, expected_needs_snapshot) in updates {
            let needs = update_prev_u_map(&mut prev_u_map, symbol, u, pu);
            assert_eq!(
                needs, expected_needs_snapshot,
                "u={}, pu={}: expected needs_snapshot={}",
                u, pu, expected_needs_snapshot
            );
        }
    }
}

mod extract_symbol_from_events {
    /// Extract symbol from forceOrder event (nested in "o" object)
    fn extract_symbol_from_force_order(data: &str) -> Option<String> {
        let j: serde_json::Value = serde_json::from_str(data).ok()?;
        let o = j.get("data")?.get("o")?;
        o.get("s")?.as_str().map(|s| s.to_string())
    }

    /// Extract symbol from regular events (at "s" key)
    fn extract_symbol_from_regular(data: &str) -> Option<String> {
        let j: serde_json::Value = serde_json::from_str(data).ok()?;
        j.get("data")?.get("s")?.as_str().map(|s| s.to_string())
    }

    #[test]
    fn test_extract_from_trade() {
        let data = r#"{"stream":"btcusdt@trade","data":{"e":"trade","E":1234,"s":"BTCUSDT","t":1}}"#;
        assert_eq!(extract_symbol_from_regular(data), Some("BTCUSDT".to_string()));
    }

    #[test]
    fn test_extract_from_depth() {
        let data = r#"{"stream":"btcusdt@depth","data":{"e":"depthUpdate","s":"BTCUSDT","U":1,"u":2}}"#;
        assert_eq!(extract_symbol_from_regular(data), Some("BTCUSDT".to_string()));
    }

    #[test]
    fn test_extract_from_force_order() {
        let data = r#"{"stream":"btcusdt@forceOrder","data":{"e":"forceOrder","E":1234,"o":{"s":"BTCUSDT","S":"SELL"}}}"#;
        assert_eq!(extract_symbol_from_force_order(data), Some("BTCUSDT".to_string()));
    }

    #[test]
    fn test_extract_from_mark_price() {
        let data = r#"{"stream":"btcusdt@markPrice","data":{"e":"markPriceUpdate","s":"BTCUSDT","p":"50000"}}"#;
        assert_eq!(extract_symbol_from_regular(data), Some("BTCUSDT".to_string()));
    }

    #[test]
    fn test_extract_from_book_ticker() {
        let data = r#"{"stream":"btcusdt@bookTicker","data":{"e":"bookTicker","s":"BTCUSDT","b":"50000"}}"#;
        assert_eq!(extract_symbol_from_regular(data), Some("BTCUSDT".to_string()));
    }
}

mod stream_configuration {
    /// Simulates the stream building logic from main.rs
    fn build_streams(
        include_book_ticker: bool,
        include_liquidations: bool,
        include_mark_price: bool,
    ) -> Vec<String> {
        let mut streams = vec![
            "$symbol@trade".to_string(),
            "$symbol@depth@0ms".to_string(),
        ];

        if include_book_ticker {
            streams.push("$symbol@bookTicker".to_string());
        }

        if include_liquidations {
            streams.push("$symbol@forceOrder".to_string());
        }

        if include_mark_price {
            streams.push("$symbol@markPrice@1s".to_string());
        }

        streams
    }

    #[test]
    fn test_default_streams() {
        let streams = build_streams(true, false, false);
        assert!(streams.contains(&"$symbol@trade".to_string()));
        assert!(streams.contains(&"$symbol@depth@0ms".to_string()));
        assert!(streams.contains(&"$symbol@bookTicker".to_string()));
        assert!(!streams.contains(&"$symbol@forceOrder".to_string()));
        assert!(!streams.contains(&"$symbol@markPrice@1s".to_string()));
    }

    #[test]
    fn test_with_liquidations() {
        let streams = build_streams(true, true, false);
        assert!(streams.contains(&"$symbol@forceOrder".to_string()));
    }

    #[test]
    fn test_with_mark_price() {
        let streams = build_streams(true, false, true);
        assert!(streams.contains(&"$symbol@markPrice@1s".to_string()));
    }

    #[test]
    fn test_full_configuration() {
        let streams = build_streams(true, true, true);
        assert_eq!(streams.len(), 5);
        assert!(streams.contains(&"$symbol@trade".to_string()));
        assert!(streams.contains(&"$symbol@depth@0ms".to_string()));
        assert!(streams.contains(&"$symbol@bookTicker".to_string()));
        assert!(streams.contains(&"$symbol@forceOrder".to_string()));
        assert!(streams.contains(&"$symbol@markPrice@1s".to_string()));
    }

    #[test]
    fn test_without_book_ticker() {
        let streams = build_streams(false, true, true);
        assert!(!streams.contains(&"$symbol@bookTicker".to_string()));
        assert!(streams.contains(&"$symbol@forceOrder".to_string()));
        assert!(streams.contains(&"$symbol@markPrice@1s".to_string()));
    }

    #[test]
    fn test_stream_expansion() {
        let streams = build_streams(true, true, true);
        let symbols = vec!["BTCUSDT", "ETHUSDT"];

        let expanded: Vec<String> = symbols
            .iter()
            .flat_map(|symbol| {
                streams
                    .iter()
                    .map(|stream| stream.replace("$symbol", &symbol.to_lowercase()))
                    .collect::<Vec<_>>()
            })
            .collect();

        assert!(expanded.contains(&"btcusdt@trade".to_string()));
        assert!(expanded.contains(&"ethusdt@trade".to_string()));
        assert!(expanded.contains(&"btcusdt@forceOrder".to_string()));
        assert!(expanded.contains(&"ethusdt@forceOrder".to_string()));
        assert!(expanded.contains(&"btcusdt@markPrice@1s".to_string()));
        assert!(expanded.contains(&"ethusdt@markPrice@1s".to_string()));
    }
}
