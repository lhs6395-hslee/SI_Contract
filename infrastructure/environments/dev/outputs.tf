output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks.cluster_endpoint
}

output "aurora_endpoint" {
  description = "Aurora PostgreSQL cluster endpoint"
  value       = module.database.aurora_cluster_endpoint
}

output "dynamodb_table_name" {
  description = "DynamoDB table name for contract metadata"
  value       = module.database.dynamodb_table_name
}

output "s3_files_bucket" {
  description = "S3 bucket for uploaded files"
  value       = module.storage.files_bucket_name
}

output "s3_templates_bucket" {
  description = "S3 bucket for contract templates"
  value       = module.storage.templates_bucket_name
}

output "certificate_arn" {
  description = "ACM certificate ARN for the domain"
  value       = module.dns.certificate_arn
}
