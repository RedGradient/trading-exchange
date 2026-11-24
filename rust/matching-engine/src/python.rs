//! Python bindings; the matching core does not depend on Python objects.

use pyo3::exceptions::{PyOverflowError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::{Decimal, MatchingEngine, MatchingError, Order, OrderStatus, OrderType, Side, Trade};

pyo3::create_exception!(matching_engine_rust, SymbolMismatchError, PyValueError);

#[pyclass(name = "MatchingEngine", module = "matching_engine_rust")]
struct PythonMatchingEngine {
    inner: MatchingEngine,
}

#[pymethods]
impl PythonMatchingEngine {
    #[new]
    fn new(symbol: String) -> Self {
        Self {
            inner: MatchingEngine::new(symbol),
        }
    }

    fn place<'py>(
        &mut self,
        py: Python<'py>,
        order: &Bound<'py, PyAny>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let mut incoming = extract_order(order)?;
        let trades = self.inner.place(&mut incoming).map_err(matching_error)?;
        let updates = trades
            .iter()
            .map(|trade| {
                let (remaining, status) = match self.inner.get_order(trade.maker_order_id) {
                    Some(maker) => (maker.remaining, maker.status),
                    None => (Decimal::ZERO, OrderStatus::Filled),
                };
                order_update(py, trade.maker_order_id, remaining, status)
            })
            .collect::<PyResult<Vec<_>>>()?;
        let trades = trades
            .iter()
            .map(|trade| trade_dict(py, trade))
            .collect::<PyResult<Vec<_>>>()?;
        let result = PyDict::new(py);
        result.set_item("remaining", incoming.remaining)?;
        result.set_item("status", status_name(incoming.status))?;
        result.set_item("sequence", incoming.sequence)?;
        result.set_item("makers", updates)?;
        result.set_item("trades", trades)?;
        Ok(result)
    }

    fn cancel<'py>(
        &mut self,
        py: Python<'py>,
        order_id: u64,
    ) -> PyResult<Option<Bound<'py, PyDict>>> {
        self.inner
            .cancel(order_id)
            .map(|order| order_update(py, order.id, order.remaining, order.status))
            .transpose()
    }

    fn snapshot<'py>(&self, py: Python<'py>, depth: usize) -> PyResult<Bound<'py, PyDict>> {
        let snapshot = self.inner.snapshot(depth);
        let result = PyDict::new(py);
        result.set_item("asks", snapshot.asks)?;
        result.set_item("bids", snapshot.bids)?;
        Ok(result)
    }

    fn best_bid_id(&self) -> Option<u64> {
        self.inner.best_order(Side::Buy).map(|order| order.id)
    }

    fn best_ask_id(&self) -> Option<u64> {
        self.inner.best_order(Side::Sell).map(|order| order.id)
    }
}

fn extract_order(order: &Bound<'_, PyAny>) -> PyResult<Order> {
    let side = match order.getattr("side")?.extract::<String>()?.as_str() {
        "BUY" => Side::Buy,
        "SELL" => Side::Sell,
        _ => return Err(PyValueError::new_err("Unknown order side")),
    };
    let order_type = match order.getattr("type")?.extract::<String>()?.as_str() {
        "LIMIT" => OrderType::Limit,
        "MARKET" => OrderType::Market,
        _ => return Err(PyValueError::new_err("Unknown order type")),
    };
    let price = order.getattr("price")?;
    Ok(Order {
        id: order.getattr("id")?.extract()?,
        symbol: order.getattr("symbol")?.extract()?,
        side,
        order_type,
        price: if price.is_none() {
            None
        } else {
            Some(exact_decimal(&price)?)
        },
        quantity: exact_decimal(&order.getattr("quantity")?)?,
        remaining: exact_decimal(&order.getattr("remaining")?)?,
        status: OrderStatus::Open,
        sequence: 0,
    })
}

fn exact_decimal(value: &Bound<'_, PyAny>) -> PyResult<Decimal> {
    let decimal = value.extract::<Decimal>()?;
    // Reject values that rust_decimal cannot represent without rounding.
    if !value.eq(decimal.into_pyobject(value.py())?)? {
        return Err(PyValueError::new_err(
            "Decimal exceeds the Rust engine precision",
        ));
    }
    Ok(decimal)
}

fn order_update<'py>(
    py: Python<'py>,
    id: u64,
    remaining: Decimal,
    status: OrderStatus,
) -> PyResult<Bound<'py, PyDict>> {
    let result = PyDict::new(py);
    result.set_item("id", id)?;
    result.set_item("remaining", remaining)?;
    result.set_item("status", status_name(status))?;
    Ok(result)
}

fn trade_dict<'py>(py: Python<'py>, trade: &Trade) -> PyResult<Bound<'py, PyDict>> {
    let result = PyDict::new(py);
    result.set_item("symbol", &trade.symbol)?;
    result.set_item("price", trade.price)?;
    result.set_item("quantity", trade.quantity)?;
    result.set_item("maker_order_id", trade.maker_order_id)?;
    result.set_item("taker_order_id", trade.taker_order_id)?;
    result.set_item(
        "aggressor_side",
        match trade.aggressor_side {
            Side::Buy => "BUY",
            Side::Sell => "SELL",
        },
    )?;
    result.set_item("sequence", trade.sequence)?;
    Ok(result)
}

fn status_name(status: OrderStatus) -> &'static str {
    match status {
        OrderStatus::Open => "OPEN",
        OrderStatus::PartiallyFilled => "PARTIALLY_FILLED",
        OrderStatus::Filled => "FILLED",
        OrderStatus::Cancelled => "CANCELLED",
        OrderStatus::Rejected => "REJECTED",
    }
}

fn matching_error(error: MatchingError) -> PyErr {
    match error {
        MatchingError::SymbolMismatch => SymbolMismatchError::new_err(error.to_string()),
        MatchingError::SequenceOverflow => PyOverflowError::new_err(error.to_string()),
        _ => PyValueError::new_err(error.to_string()),
    }
}

#[pymodule]
fn matching_engine_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PythonMatchingEngine>()?;
    module.add(
        "SymbolMismatchError",
        module.py().get_type::<SymbolMismatchError>(),
    )?;
    Ok(())
}
