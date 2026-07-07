resource "aws_sns_topic" "trades_settled" {
  # This topic enables fan-out notifications after settlement.
  name = "${local.name_prefix}-${var.trades_settled_topic_name}"
}
