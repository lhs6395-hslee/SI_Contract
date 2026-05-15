module "networking" {
  source             = "../../modules/networking"
  project_name       = var.project_name
  environment        = var.environment
  availability_zones = var.availability_zones
  single_nat_gateway = false # HA for production
}

module "security" {
  source       = "../../modules/security"
  project_name = var.project_name
  environment  = var.environment
  vpc_id       = module.networking.vpc_id
  vpc_cidr     = module.networking.vpc_cidr_block
}

module "storage" {
  source       = "../../modules/storage"
  project_name = var.project_name
  environment  = var.environment
}

module "secrets" {
  source       = "../../modules/secrets"
  project_name = var.project_name
  environment  = var.environment
}

module "database" {
  source                   = "../../modules/database"
  project_name             = var.project_name
  environment              = var.environment
  private_subnet_ids       = module.networking.private_subnet_ids
  aurora_security_group_id = module.security.aurora_security_group_id
  aurora_min_capacity_acu  = 0.5
  aurora_max_capacity_acu  = 8
}

module "eks" {
  source                    = "../../modules/eks"
  project_name              = var.project_name
  environment               = var.environment
  private_subnet_ids        = module.networking.private_subnet_ids
  cluster_security_group_id = module.security.eks_cluster_security_group_id
}

module "dns" {
  source       = "../../modules/dns"
  domain_name  = var.domain_name
  create_zone  = false # rayhli.com Zone already exists
  alb_dns_name = ""    # Populated after ALB is created by AWS LB Controller via K8s Ingress
  alb_zone_id  = ""
}

module "cdn" {
  source          = "../../modules/cdn"
  project_name    = var.project_name
  environment     = var.environment
  domain_name     = var.domain_name
  certificate_arn = module.dns.certificate_arn
  alb_dns_name    = "" # Populated after ALB is created by AWS LB Controller
  enable          = true
}

module "monitoring" {
  source             = "../../modules/monitoring"
  project_name       = var.project_name
  environment        = var.environment
  eks_cluster_name   = module.eks.cluster_name
  alarm_email        = var.alarm_email
  log_retention_days = 30
}
