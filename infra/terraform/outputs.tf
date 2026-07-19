output "trades_queue_url" {
  description = "URL of the primary trade events queue."
  value       = aws_sqs_queue.trades.url
}

output "trades_queue_arn" {
  description = "ARN of the primary trade events queue."
  value       = aws_sqs_queue.trades.arn
}

output "trades_dlq_url" {
  description = "URL of the trade events dead-letter queue."
  value       = aws_sqs_queue.trades_dlq.url
}

output "trades_dlq_arn" {
  description = "ARN of the trade events dead-letter queue."
  value       = aws_sqs_queue.trades_dlq.arn
}

output "trades_settled_topic_arn" {
  description = "ARN of the SNS topic for settled events."
  value       = aws_sns_topic.trades_settled.arn
}

output "trades_settled_topic_name" {
  description = "Name of the SNS topic for settled events."
  value       = aws_sns_topic.trades_settled.name
}

output "ws_fanout_queue_url" {
  description = "URL of the WebSocket fan-out queue."
  value       = aws_sqs_queue.ws_fanout.url
}

output "ws_fanout_queue_arn" {
  description = "ARN of the WebSocket fan-out queue."
  value       = aws_sqs_queue.ws_fanout.arn
}