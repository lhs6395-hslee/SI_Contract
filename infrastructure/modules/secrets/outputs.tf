output "secret_arn" {
  description = "ARN of the application secrets in Secrets Manager"
  value       = aws_secretsmanager_secret.app.arn
}

output "secret_name" {
  description = "Name of the application secrets in Secrets Manager"
  value       = aws_secretsmanager_secret.app.name
}
