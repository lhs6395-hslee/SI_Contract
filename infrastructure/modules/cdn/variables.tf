variable "project_name" {
  description = "Name of the project, used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)"
  type        = string
}

variable "alb_dns_name" {
  description = "DNS name of the ALB to use as CloudFront origin"
  type        = string
}

variable "domain_name" {
  description = "Custom domain name for the CloudFront distribution (e.g. app.domain.com)"
  type        = string
}

variable "certificate_arn" {
  description = "ARN of the ACM certificate in us-east-1 for CloudFront"
  type        = string
}

variable "enable" {
  description = "Whether to create the CloudFront distribution"
  type        = bool
  default     = false
}
