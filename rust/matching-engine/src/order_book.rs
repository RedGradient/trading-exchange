use std::collections::{BTreeMap, HashMap, VecDeque};

use rust_decimal::Decimal;

use crate::{Order, OrderStatus, Side};

type Levels = BTreeMap<Decimal, VecDeque<u64>>;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct OrderBookSnapshot {
    pub asks: Vec<(Decimal, Decimal)>,
    pub bids: Vec<(Decimal, Decimal)>,
}

#[derive(Debug, Default)]
pub(crate) struct OrderBook {
    orders: HashMap<u64, Order>,
    asks: Levels,
    bids: Levels,
}

impl OrderBook {
    pub(crate) fn get(&self, id: u64) -> Option<&Order> {
        self.orders.get(&id)
    }

    pub(crate) fn len(&self) -> usize {
        self.orders.len()
    }

    pub(crate) fn contains(&self, id: u64) -> bool {
        self.orders.contains_key(&id)
    }

    pub(crate) fn add(&mut self, order: Order) {
        let price = order
            .price
            .expect("Only priced limit orders rest in the book");
        self.levels_mut(order.side)
            .entry(price)
            .or_default()
            .push_back(order.id);
        self.orders.insert(order.id, order);
    }

    pub(crate) fn best(&self, side: Side) -> Option<&Order> {
        let (_, level) = match side {
            Side::Buy => self.bids.last_key_value()?,
            Side::Sell => self.asks.first_key_value()?,
        };
        self.orders.get(level.front()?)
    }

    pub(crate) fn fill(&mut self, id: u64, quantity: Decimal) {
        let order = self.orders.get_mut(&id).expect("Maker must exist");
        order.remaining -= quantity;
        if order.remaining.is_zero() {
            self.remove(id);
        } else {
            order.status = OrderStatus::PartiallyFilled;
        }
    }

    pub(crate) fn cancel(&mut self, id: u64) -> Option<Order> {
        let mut order = self.remove(id)?;
        order.status = OrderStatus::Cancelled;
        Some(order)
    }

    fn remove(&mut self, id: u64) -> Option<Order> {
        let order = self.orders.remove(&id)?;
        let price = order.price.expect("Resting orders must have a price");
        let levels = self.levels_mut(order.side);
        let level = levels.get_mut(&price).expect("Price level must exist");
        let position = level
            .iter()
            .position(|&queued_id| queued_id == id)
            .expect("Order must exist at its price level");
        level.remove(position);
        if level.is_empty() {
            levels.remove(&price);
        }
        Some(order)
    }

    fn levels_mut(&mut self, side: Side) -> &mut Levels {
        match side {
            Side::Buy => &mut self.bids,
            Side::Sell => &mut self.asks,
        }
    }

    pub(crate) fn snapshot(&self, depth: usize) -> OrderBookSnapshot {
        let aggregate = |(&price, ids): (&Decimal, &VecDeque<u64>)| {
            let quantity = ids.iter().map(|id| self.orders[id].remaining).sum();
            (price, quantity)
        };
        OrderBookSnapshot {
            asks: self.asks.iter().take(depth).map(aggregate).collect(),
            bids: self.bids.iter().rev().take(depth).map(aggregate).collect(),
        }
    }
}
