use anyhow::anyhow;
use clap::Parser;
use tokio::{self, select, signal, sync::mpsc::unbounded_channel};
use tracing::{error, info};

use crate::file::Writer;

mod binance;
mod binancefuturescm;
mod binancefuturesum;
mod bybit;
mod error;
mod file;
mod hyperliquid;
mod throttler;

/// Stream configuration for additional data feeds
#[derive(Debug, Clone, Default)]
pub struct StreamConfig {
    /// Include liquidation (forceOrder) events
    pub include_liquidations: bool,
    /// Include mark price updates
    pub include_mark_price: bool,
    /// Include book ticker (best bid/ask) events
    pub include_book_ticker: bool,
}

#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Args {
    /// Path for the files where collected data will be written.
    path: String,

    /// Name of the exchange
    exchange: String,

    /// Symbols for which data will be collected.
    symbols: Vec<String>,

    /// Include liquidation (forceOrder) events in the data collection.
    /// When enabled, subscribes to <symbol>@forceOrder stream.
    #[arg(long)]
    include_liquidations: bool,

    /// Include mark price updates in the data collection.
    /// When enabled, subscribes to <symbol>@markPrice@1s stream.
    #[arg(long)]
    include_mark_price: bool,

    /// Exclude book ticker (best bid/ask) events from data collection.
    /// By default, book ticker is included.
    #[arg(long)]
    exclude_book_ticker: bool,
}

fn build_binance_futures_streams(config: &StreamConfig) -> Vec<String> {
    let mut streams = vec![
        "$symbol@trade".to_string(),
        "$symbol@depth@0ms".to_string(),
    ];

    if config.include_book_ticker {
        streams.push("$symbol@bookTicker".to_string());
    }

    if config.include_liquidations {
        streams.push("$symbol@forceOrder".to_string());
    }

    if config.include_mark_price {
        streams.push("$symbol@markPrice@1s".to_string());
    }

    streams
}

#[tokio::main(flavor = "multi_thread")]
async fn main() -> Result<(), anyhow::Error> {
    let args = Args::parse();

    tracing_subscriber::fmt::init();

    let stream_config = StreamConfig {
        include_liquidations: args.include_liquidations,
        include_mark_price: args.include_mark_price,
        include_book_ticker: !args.exclude_book_ticker,
    };

    let (writer_tx, mut writer_rx) = unbounded_channel();

    let _handle = match args.exchange.as_str() {
        "binancefutures" | "binancefuturesum" => {
            let streams = build_binance_futures_streams(&stream_config);
            info!(?streams, "subscribing to streams");

            tokio::spawn(binancefuturesum::run_collection(
                streams,
                args.symbols,
                writer_tx,
            ))
        }
        "binancefuturescm" => {
            let streams = build_binance_futures_streams(&stream_config);
            info!(?streams, "subscribing to streams");

            tokio::spawn(binancefuturescm::run_collection(
                streams,
                args.symbols,
                writer_tx,
            ))
        }
        "binance" | "binancespot" => {
            let streams = ["$symbol@trade", "$symbol@bookTicker", "$symbol@depth@100ms"]
                .iter()
                .map(|stream| stream.to_string())
                .collect();

            tokio::spawn(binance::run_collection(streams, args.symbols, writer_tx))
        }
        "bybit" => {
            let topics = [
                "orderbook.1.$symbol",
                "orderbook.50.$symbol",
                "orderbook.500.$symbol",
                "publicTrade.$symbol",
            ]
            .iter()
            .map(|topic| topic.to_string())
            .collect();

            tokio::spawn(bybit::run_collection(topics, args.symbols, writer_tx))
        }
        "hyperliquid" => {
            let subscriptions = ["trades", "l2Book", "bbo"]
                .iter()
                .map(|sub| sub.to_string())
                .collect();

            tokio::spawn(hyperliquid::run_collection(
                subscriptions,
                args.symbols,
                writer_tx,
            ))
        }
        exchange => {
            return Err(anyhow!("{exchange} is not supported."));
        }
    };

    let mut writer = Writer::new(&args.path);
    loop {
        select! {
            _ = signal::ctrl_c() => {
                info!("ctrl-c received");
                break;
            }
            r = writer_rx.recv() => match r {
                Some((recv_time, symbol, data)) => {
                    if let Err(error) = writer.write(recv_time, symbol, data) {
                        error!(?error, "write error");
                        break;
                    }
                }
                None => {
                    break;
                }
            }
        }
    }
    // let _ = handle.await;
    Ok(())
}
