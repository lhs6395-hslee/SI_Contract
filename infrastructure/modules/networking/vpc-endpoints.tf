################################################################################
# VPC Gateway Endpoints
################################################################################

data "aws_region" "current" {}

resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.this.id
  service_name = "com.amazonaws.${data.aws_region.current.name}.s3"

  vpc_endpoint_type = "Gateway"
  route_table_ids = [
    aws_route_table.public.id,
    aws_route_table.private.id,
  ]

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-s3-endpoint"
  })
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id       = aws_vpc.this.id
  service_name = "com.amazonaws.${data.aws_region.current.name}.dynamodb"

  vpc_endpoint_type = "Gateway"
  route_table_ids = [
    aws_route_table.public.id,
    aws_route_table.private.id,
  ]

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-dynamodb-endpoint"
  })
}

################################################################################
# VPC Interface Endpoints (IRSA/Bedrock require STS + Bedrock access from private subnets)
################################################################################

resource "aws_vpc_endpoint" "sts" {
  count = var.vpc_endpoint_security_group_id != "" ? 1 : 0

  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.sts"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [var.vpc_endpoint_security_group_id]

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-sts-endpoint"
  })
}

resource "aws_vpc_endpoint" "bedrock_runtime" {
  count = var.vpc_endpoint_security_group_id != "" ? 1 : 0

  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [var.vpc_endpoint_security_group_id]

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-bedrock-runtime-endpoint"
  })
}
