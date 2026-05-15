variable "project_name" {
  description = "Name of the project, used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for the Aurora DB subnet group"
  type        = list(string)
}

variable "aurora_security_group_id" {
  description = "Security group ID to attach to the Aurora cluster"
  type        = string
}

variable "aurora_min_capacity_acu" {
  description = "Minimum ACU capacity for Aurora Serverless v2 scaling"
  type        = number
  default     = 0.5
}

variable "aurora_max_capacity_acu" {
  description = "Maximum ACU capacity for Aurora Serverless v2 scaling"
  type        = number
  default     = 4
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL engine version"
  type        = string
  default     = "16.4"
}

variable "dynamodb_billing_mode" {
  description = "DynamoDB billing mode (PAY_PER_REQUEST or PROVISIONED)"
  type        = string
  default     = "PAY_PER_REQUEST"
}

variable "dynamodb_ttl_days" {
  description = "Number of days before DynamoDB items expire via TTL"
  type        = number
  default     = 7
}
