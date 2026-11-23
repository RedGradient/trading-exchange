//! In-memory matching engine with price-time priority and exact decimal arithmetic.

mod matching_engine;
mod models;
mod order_book;

pub use matching_engine::{MatchingEngine, MatchingError};
pub use models::{Order, OrderStatus, OrderType, Side, Trade};
pub use order_book::OrderBookSnapshot;
pub use rust_decimal::Decimal;
