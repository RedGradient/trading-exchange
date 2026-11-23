use std::{error::Error, fmt};

use rust_decimal::Decimal;

use crate::order_book::OrderBook;
use crate::{Order, OrderBookSnapshot, OrderStatus, OrderType, Side, Trade};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MatchingError {
    SymbolMismatch,
    MissingLimitPrice,
    InvalidPrice,
    InvalidQuantity,
    DuplicateOrderId,
    SequenceOverflow,
}

impl fmt::Display for MatchingError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::SymbolMismatch => "Order symbol does not match the engine symbol",
            Self::MissingLimitPrice => "Limit order must have a price",
            Self::InvalidPrice => "Price must be positive",
            Self::InvalidQuantity => "Quantity and remaining quantity must be positive, and remaining must not exceed quantity",
            Self::DuplicateOrderId => "Order ID already exists in the book",
            Self::SequenceOverflow => "Engine sequence exhausted",
        })
    }
}

impl Error for MatchingError {}

#[derive(Debug)]
pub struct MatchingEngine {
    sequence: u64,
    order_book: OrderBook,
    symbol: String,
}

impl MatchingEngine {
    pub fn new(symbol: impl Into<String>) -> Self {
        Self {
            sequence: 0,
            order_book: OrderBook::default(),
            symbol: symbol.into(),
        }
    }

    /// Matches at maker prices, updates the taker, and stores any limit remainder.
    /// Validation errors leave both the order and the engine unchanged.
    pub fn place(&mut self, order: &mut Order) -> Result<Vec<Trade>, MatchingError> {
        self.validate(order)?;
        // At most one trade per resting order, plus the incoming order sequence.
        self.validate_sequence()?;
        order.sequence = self.next_sequence();
        let maker_side = match order.side {
            Side::Buy => Side::Sell,
            Side::Sell => Side::Buy,
        };
        let mut trades = Vec::new();
        while order.remaining > Decimal::ZERO {
            let Some(maker) = self.order_book.best(maker_side) else {
                break;
            };
            let price = maker.price.expect("Resting orders must have a price");
            if order.order_type == OrderType::Limit {
                let limit = order.price.expect("Limit price was validated");
                let crosses = match order.side {
                    Side::Buy => price <= limit,
                    Side::Sell => price >= limit,
                };
                if !crosses {
                    break;
                }
            }
            let maker_order_id = maker.id;
            let quantity = order.remaining.min(maker.remaining);
            self.order_book.fill(maker_order_id, quantity);
            order.remaining -= quantity;
            trades.push(Trade {
                symbol: self.symbol.clone(),
                price,
                quantity,
                maker_order_id,
                taker_order_id: order.id,
                aggressor_side: order.side,
                sequence: self.next_sequence(),
            });
        }
        order.status = if order.remaining.is_zero() {
            OrderStatus::Filled
        } else if !trades.is_empty() {
            OrderStatus::PartiallyFilled
        } else if order.order_type == OrderType::Market {
            OrderStatus::Cancelled
        } else {
            OrderStatus::Open
        };
        if order.order_type == OrderType::Limit && order.remaining > Decimal::ZERO {
            self.order_book.add(order.clone());
        }
        Ok(trades)
    }

    /// Removes a resting order; unknown or fully filled orders return None.
    pub fn cancel(&mut self, order_id: u64) -> Option<Order> {
        self.order_book.cancel(order_id)
    }

    /// Returns aggregated asks ascending and bids descending by price.
    pub fn snapshot(&self, depth: usize) -> OrderBookSnapshot {
        self.order_book.snapshot(depth)
    }

    fn validate(&self, order: &Order) -> Result<(), MatchingError> {
        if order.symbol != self.symbol {
            return Err(MatchingError::SymbolMismatch);
        }
        if order.order_type == OrderType::Limit && order.price.is_none() {
            return Err(MatchingError::MissingLimitPrice);
        }
        if order.price.is_some_and(|price| price <= Decimal::ZERO) {
            return Err(MatchingError::InvalidPrice);
        }
        if order.quantity <= Decimal::ZERO
            || order.remaining <= Decimal::ZERO
            || order.remaining > order.quantity
        {
            return Err(MatchingError::InvalidQuantity);
        }
        if self.order_book.contains(order.id) {
            return Err(MatchingError::DuplicateOrderId);
        }
        Ok(())
    }

    fn validate_sequence(&self) -> Result<(), MatchingError> {
        self.sequence
            .checked_add(self.order_book.len() as u64)
            .and_then(|sequence| sequence.checked_add(1))
            .ok_or(MatchingError::SequenceOverflow)?;
        Ok(())
    }

    fn next_sequence(&mut self) -> u64 {
        self.sequence += 1;
        self.sequence
    }
}
