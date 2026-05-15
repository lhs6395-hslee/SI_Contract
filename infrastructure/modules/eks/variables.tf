variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)"
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.35"
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for EKS cluster and Fargate profiles"
  type        = list(string)
}

variable "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster ENIs"
  type        = string
}

variable "enable_fargate_spot" {
  description = "Enable Fargate Spot capacity for cost optimization"
  type        = bool
  default     = true
}

variable "app_namespace" {
  description = "Kubernetes namespace for application workloads"
  type        = string
  default     = "si-contract"
}
