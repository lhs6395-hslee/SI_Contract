################################################################################
# Aurora outputs
################################################################################

output "aurora_cluster_endpoint" {
  description = "Writer endpoint for the Aurora cluster"
  value       = aws_rds_cluster.aurora.endpoint
}

output "aurora_reader_endpoint" {
  description = "Reader endpoint for the Aurora cluster"
  value       = aws_rds_cluster.aurora.reader_endpoint
}

output "aurora_port" {
  description = "Port the Aurora cluster listens on"
  value       = aws_rds_cluster.aurora.port
}

output "aurora_cluster_id" {
  description = "Identifier of the Aurora cluster"
  value       = aws_rds_cluster.aurora.id
}

output "aurora_database_name" {
  description = "Name of the default database created in the Aurora cluster"
  value       = aws_rds_cluster.aurora.database_name
}

################################################################################
# DynamoDB outputs
################################################################################

output "dynamodb_table_name" {
  description = "Name of the DynamoDB pipeline state table"
  value       = aws_dynamodb_table.pipeline_state.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB pipeline state table"
  value       = aws_dynamodb_table.pipeline_state.arn
}
