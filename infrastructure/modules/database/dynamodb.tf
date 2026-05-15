################################################################################
# DynamoDB — Pipeline State Table
################################################################################

resource "aws_dynamodb_table" "pipeline_state" {
  name         = "${var.project_name}-${var.environment}-pipeline-state"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "project_id"

  attribute {
    name = "project_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-pipeline-state"
    Environment = var.environment
  }
}
