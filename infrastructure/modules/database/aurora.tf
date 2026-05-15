################################################################################
# Aurora Serverless v2 — PostgreSQL
################################################################################

locals {
  db_name        = replace(var.project_name, "-", "_")
  cluster_prefix = "${var.project_name}-${var.environment}"
  is_prod        = var.environment == "prod"
}

# ------------------------------------------------------------------------------
# Master password — never stored in tfvars
# ------------------------------------------------------------------------------

resource "random_password" "aurora_master" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "aurora_master_password" {
  name                    = "${local.cluster_prefix}/aurora/master-password"
  description             = "Master password for Aurora cluster ${local.cluster_prefix}"
  recovery_window_in_days = local.is_prod ? 30 : 0
}

resource "aws_secretsmanager_secret_version" "aurora_master_password" {
  secret_id     = aws_secretsmanager_secret.aurora_master_password.id
  secret_string = random_password.aurora_master.result
}

# ------------------------------------------------------------------------------
# Subnet group
# ------------------------------------------------------------------------------

resource "aws_db_subnet_group" "aurora" {
  name        = "${local.cluster_prefix}-aurora"
  description = "Private subnets for Aurora cluster"
  subnet_ids  = var.private_subnet_ids

  tags = {
    Name        = "${local.cluster_prefix}-aurora"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# Cluster
# ------------------------------------------------------------------------------

resource "aws_rds_cluster" "aurora" {
  cluster_identifier = "${local.cluster_prefix}-aurora"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = var.aurora_engine_version
  database_name      = local.db_name
  master_username    = "dbadmin"
  master_password    = random_password.aurora_master.result

  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [var.aurora_security_group_id]

  storage_encrypted = true
  apply_immediately = !local.is_prod

  skip_final_snapshot       = !local.is_prod
  final_snapshot_identifier = local.is_prod ? "${local.cluster_prefix}-aurora-final" : null

  serverlessv2_scaling_configuration {
    min_capacity = var.aurora_min_capacity_acu
    max_capacity = var.aurora_max_capacity_acu
  }

  tags = {
    Name        = "${local.cluster_prefix}-aurora"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# Cluster instance (Serverless v2)
# ------------------------------------------------------------------------------

resource "aws_rds_cluster_instance" "aurora" {
  identifier         = "${local.cluster_prefix}-aurora-1"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version

  apply_immediately = !local.is_prod

  tags = {
    Name        = "${local.cluster_prefix}-aurora-1"
    Environment = var.environment
  }
}
