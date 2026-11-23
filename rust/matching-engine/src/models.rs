use rust_decimal::Decimal;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Side {
    Buy,
    Sell,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OrderType {
    Limit,
    Market,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OrderStatus {
    Open,
    PartiallyFilled,
    Filled,
    Cancelled,
    Rejected,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Order {
    pub id: u64,
    pub symbol: String,
    pub side: Side,
    pub order_type: OrderType,
    pub price: Option<Decimal>,
    pub quantity: Decimal,
    pub remaining: Decimal,
    pub status: OrderStatus,
    pub sequence: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Trade {
    pub symbol: String,
    pub price: Decimal,
    pub quantity: Decimal,
    pub maker_order_id: u64,
    pub taker_order_id: u64,
    pub aggressor_side: Side,
    pub sequence: u64,
}
