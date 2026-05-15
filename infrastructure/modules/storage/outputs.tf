################################################################################
# Files bucket outputs
################################################################################

output "files_bucket_name" {
  description = "Name of the files S3 bucket"
  value       = aws_s3_bucket.files.id
}

output "files_bucket_arn" {
  description = "ARN of the files S3 bucket"
  value       = aws_s3_bucket.files.arn
}

################################################################################
# Templates bucket outputs
################################################################################

output "templates_bucket_name" {
  description = "Name of the templates S3 bucket"
  value       = aws_s3_bucket.templates.id
}

output "templates_bucket_arn" {
  description = "ARN of the templates S3 bucket"
  value       = aws_s3_bucket.templates.arn
}
