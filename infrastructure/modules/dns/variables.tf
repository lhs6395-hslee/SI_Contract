variable "domain_name" {
  description = "Root domain name for the application (e.g. si-contract.example.com)"
  type        = string
}

variable "create_zone" {
  description = "Whether to create a new Route53 hosted zone"
  type        = bool
  default     = true
}

variable "alb_dns_name" {
  description = "DNS name of the ALB for alias records"
  type        = string
}

variable "alb_zone_id" {
  description = "Hosted zone ID of the ALB for alias records"
  type        = string
}

variable "cloudfront_domain_name" {
  description = "Domain name of the CloudFront distribution (empty if not used)"
  type        = string
  default     = ""
}

variable "cloudfront_zone_id" {
  description = "Hosted zone ID of the CloudFront distribution (empty if not used)"
  type        = string
  default     = ""
}

variable "enable_cloudfront" {
  description = "Whether to point the app record to CloudFront instead of ALB"
  type        = bool
  default     = false
}
