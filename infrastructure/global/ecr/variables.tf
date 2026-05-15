variable "project_name" {
  description = "Project name used as prefix for repository naming."
  type        = string
  default     = "si-contract"
}

variable "aws_region" {
  description = "AWS region for ECR repositories."
  type        = string
  default     = "ap-northeast-2"
}

variable "image_retention_count" {
  description = "Number of recent images to retain per repository."
  type        = number
  default     = 5
}
