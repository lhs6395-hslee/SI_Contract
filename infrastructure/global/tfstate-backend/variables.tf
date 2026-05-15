variable "project_name" {
  description = "Project name used as prefix for resource naming."
  type        = string
  default     = "si-contract"
}

variable "aws_region" {
  description = "AWS region for the tfstate backend resources."
  type        = string
  default     = "ap-northeast-2"
}
