locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

################################################################################
# Application Secrets
################################################################################

resource "aws_secretsmanager_secret" "app" {
  name        = "${local.name_prefix}/app-secrets"
  description = "Application secrets for ${local.name_prefix}"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}/app-secrets"
  })
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id

  # Placeholder values — replace with real values via AWS Console
  secret_string = sensitive(jsonencode({
    ANTHROPIC_API_KEY = "CHANGE_ME_VIA_CONSOLE"
    DB_HOST           = "CHANGE_ME_VIA_CONSOLE"
    DB_PORT           = "5432"
    DB_NAME           = "CHANGE_ME_VIA_CONSOLE"
    DB_USERNAME       = "CHANGE_ME_VIA_CONSOLE"
    DB_PASSWORD       = "CHANGE_ME_VIA_CONSOLE"
  }))

  lifecycle {
    ignore_changes = [secret_string]
  }
}
