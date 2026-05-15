output "zone_id" {
  description = "Route53 hosted zone ID"
  value       = local.zone_id
}

output "zone_name_servers" {
  description = "Name servers for the hosted zone (only available when zone is created)"
  value       = var.create_zone ? aws_route53_zone.main[0].name_servers : []
}

output "certificate_arn" {
  description = "ARN of the validated ACM certificate"
  value       = aws_acm_certificate_validation.main.certificate_arn
}

output "app_fqdn" {
  description = "Fully qualified domain name for the application"
  value       = length(aws_route53_record.app) > 0 ? aws_route53_record.app[0].fqdn : "si.${var.domain_name}"
}

output "api_fqdn" {
  description = "Fully qualified domain name for the API"
  value       = length(aws_route53_record.api) > 0 ? aws_route53_record.api[0].fqdn : "si-api.${var.domain_name}"
}
