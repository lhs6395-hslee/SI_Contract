output "distribution_id" {
  description = "ID of the CloudFront distribution"
  value       = var.enable ? aws_cloudfront_distribution.main[0].id : ""
}

output "distribution_domain_name" {
  description = "Domain name of the CloudFront distribution"
  value       = var.enable ? aws_cloudfront_distribution.main[0].domain_name : ""
}

output "distribution_zone_id" {
  description = "Hosted zone ID of the CloudFront distribution (for Route53 alias)"
  value       = var.enable ? aws_cloudfront_distribution.main[0].hosted_zone_id : ""
}
