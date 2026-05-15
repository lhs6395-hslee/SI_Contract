output "frontend_log_group_name" {
  description = "Name of the CloudWatch log group for frontend application"
  value       = aws_cloudwatch_log_group.frontend.name
}

output "backend_log_group_name" {
  description = "Name of the CloudWatch log group for backend application"
  value       = aws_cloudwatch_log_group.backend.name
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications (empty if not created)"
  value       = var.alarm_email != "" ? aws_sns_topic.alerts[0].arn : ""
}
