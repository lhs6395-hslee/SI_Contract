variable "project_name" {
  description = "Name of the project, used for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)"
  type        = string
}

variable "enable_versioning" {
  description = "Enable S3 versioning on the templates bucket"
  type        = bool
  default     = false
}

variable "lifecycle_transition_days" {
  description = "Number of days before transitioning files bucket objects to Infrequent Access"
  type        = number
  default     = 90
}
