resource "aws_sqs_queue" "ws_fanout" {
  # Receives trade.settled notifications for WebSocket broadcast.
  name                       = "${local.name_prefix}-${var.ws_fanout_queue_name}"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
}

resource "aws_sqs_queue_policy" "ws_fanout" {
  queue_url = aws_sqs_queue.ws_fanout.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSNSPublish"
        Effect = "Allow"
        Principal = {
          Service = "sns.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.ws_fanout.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_sns_topic.trades_settled.arn
          }
        }
      }
    ]
  })
}

resource "aws_sns_topic_subscription" "trades_settled_to_ws_fanout" {
  topic_arn = aws_sns_topic.trades_settled.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.ws_fanout.arn
}
