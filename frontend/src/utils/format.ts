export function formatDecimal(value: string, fractionDigits = 2): string {
  const n = parseFloat(value)
  if (!Number.isFinite(n)) {
    return value
  }
  return n.toFixed(fractionDigits)
}
