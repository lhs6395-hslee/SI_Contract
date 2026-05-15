# Networking Module

Terraform module that provisions a VPC with public and private subnets, internet gateway, optional NAT gateway, and gateway VPC endpoints for S3 and DynamoDB.

## Usage

```hcl
module "networking" {
  source = "./modules/networking"

  project_name       = "si-contract"
  environment        = "dev"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["ap-northeast-2a", "ap-northeast-2c"]
  enable_nat_gateway = true
  single_nat_gateway = true
}
```

## Resources Created

- VPC with DNS support and DNS hostnames enabled
- Public subnets (one per AZ) with auto-assign public IP
- Private subnets (one per AZ)
- Internet Gateway
- NAT Gateway with Elastic IP (conditional, single or per-AZ)
- Public and private route tables with associations
- S3 and DynamoDB gateway VPC endpoints
