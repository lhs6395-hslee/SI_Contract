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

# 참고: STS / Bedrock-runtime Interface Endpoint는 환경 main.tf에서 정의한다.
#       (networking이 security의 SG를, security가 networking의 vpc_id를 서로
#        요구해 모듈 간 순환이 생기므로 환경 레벨에서 양쪽 출력을 조합한다.)
