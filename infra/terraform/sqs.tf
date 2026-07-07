resource "aws_sqs_queue" "trades_dlq" {
  # DLQ helps diagnose and replay problematic messages.
  name = "${local.name_prefix}-${var.trades_dlq_name}"
}

resource "aws_sqs_queue" "trades" {
  name = "${local.name_prefix}-${var.trades_queue_name}"

  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds

  # After repeated processing failures, SQS moves the message to DLQ.
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.trades_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}