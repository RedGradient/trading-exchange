variable "project_name" {
  description = "Project name used as a resource naming prefix."
  type        = string
  default     = "exchange"
}

variable "environment" {
  description = "Logical environment name (usually local for LocalStack)."
  type        = string
  default     = "local"
}

variable "aws_region" {
  description = "AWS region for provider configuration (metadata in LocalStack)."
  type        = string
  default     = "us-east-1"
}

variable "localstack_endpoint" {
  description = "Shared LocalStack endpoint for AWS-compatible services."
  type        = string
  default     = "http://localhost:4566"
}

variable "trades_queue_name" {
  description = "Primary SQS queue name for trade events."
  type        = string
  default     = "trades"
}

variable "trades_dlq_name" {
  description = "Dead-letter queue name for failed message processing."
  type        = string
  default     = "trades-dlq"
}

variable "trades_settled_topic_name" {
  description = "SNS topic name for post-settlement events."
  type        = string
  default     = "trades-settled"
}

variable "visibility_timeout_seconds" {
  description = "How long a message stays invisible while a worker processes it."
  type        = number
  default     = 30
}

variable "message_retention_seconds" {
  description = "How long messages are retained in the primary queue."
  type        = number
  default     = 345600 # 4 days
}

variable "max_receive_count" {
  description = "Number of failed receives before moving a message to DLQ."
  type        = number
  default     = 3
}
