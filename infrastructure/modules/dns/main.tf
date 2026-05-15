locals {
  zone_id        = var.create_zone ? aws_route53_zone.main[0].zone_id : data.aws_route53_zone.existing[0].zone_id
  has_alb        = var.alb_dns_name != "" && var.alb_zone_id != ""
  has_cloudfront = var.enable_cloudfront && var.cloudfront_domain_name != "" && var.cloudfront_zone_id != ""
}

resource "aws_route53_zone" "main" {
  count = var.create_zone ? 1 : 0

  name = var.domain_name

  tags = {
    Name = var.domain_name
  }
}

data "aws_route53_zone" "existing" {
  count = var.create_zone ? 0 : 1

  name         = var.domain_name
  private_zone = false
}

resource "aws_route53_record" "app" {
  count = local.has_alb || local.has_cloudfront ? 1 : 0

  zone_id = local.zone_id
  name    = "si.${var.domain_name}"
  type    = "A"

  alias {
    name                   = local.has_cloudfront ? var.cloudfront_domain_name : var.alb_dns_name
    zone_id                = local.has_cloudfront ? var.cloudfront_zone_id : var.alb_zone_id
    evaluate_target_health = !local.has_cloudfront
  }
}

resource "aws_route53_record" "api" {
  count = local.has_alb ? 1 : 0

  zone_id = local.zone_id
  name    = "si-api.${var.domain_name}"
  type    = "A"

  alias {
    name                   = var.alb_dns_name
    zone_id                = var.alb_zone_id
    evaluate_target_health = true
  }
}
