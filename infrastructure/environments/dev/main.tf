module "networking" {
  source             = "../../modules/networking"
  project_name       = var.project_name
  environment        = var.environment
  availability_zones = var.availability_zones
  single_nat_gateway = true # cost optimization for dev
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

module "monitoring" {
  source           = "../../modules/monitoring"
  project_name     = var.project_name
  environment      = var.environment
  eks_cluster_name = module.eks.cluster_name
  alarm_email      = var.alarm_email
}

# ──────────────────────────────────────────────────────────────────────────────
# VPC Interface Endpoints — IRSA(STS) + Bedrock from private subnets
#
# Fargate Pod는 private subnet에서 IRSA credential을 받으려면 STS에 도달해야 하고,
# Bedrock 호출도 필요하다. networking↔security 순환 의존을 피하기 위해
# (networking이 SG를, security가 vpc_id를 서로 요구) 환경 레벨에서 정의한다.
# ──────────────────────────────────────────────────────────────────────────────
resource "aws_vpc_endpoint" "sts" {
  vpc_id              = module.networking.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.sts"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = module.networking.private_subnet_ids
  security_group_ids  = [module.security.vpc_endpoints_security_group_id]

  tags = {
    Name        = "${var.project_name}-${var.environment}-sts-endpoint"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = module.networking.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = module.networking.private_subnet_ids
  security_group_ids  = [module.security.vpc_endpoints_security_group_id]

  tags = {
    Name        = "${var.project_name}-${var.environment}-bedrock-runtime-endpoint"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
