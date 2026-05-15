################################################################################
# Cluster
################################################################################

output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  description = "Endpoint URL for the EKS cluster API server"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_ca_certificate" {
  description = "Base64-encoded CA certificate for cluster communication"
  value       = aws_eks_cluster.main.certificate_authority[0].data
}

################################################################################
# OIDC
################################################################################

output "oidc_provider_arn" {
  description = "ARN of the OIDC provider for IRSA"
  value       = aws_iam_openid_connect_provider.cluster.arn
}

output "oidc_provider_url" {
  description = "URL of the OIDC provider (without https:// prefix)"
  value       = local.oidc_provider_url
}

################################################################################
# IRSA Role ARNs
################################################################################

output "backend_role_arn" {
  description = "IAM role ARN for the backend ServiceAccount"
  value       = aws_iam_role.backend_pod.arn
}

output "frontend_role_arn" {
  description = "IAM role ARN for the frontend ServiceAccount"
  value       = aws_iam_role.frontend_pod.arn
}

output "lb_controller_role_arn" {
  description = "IAM role ARN for the AWS Load Balancer Controller ServiceAccount"
  value       = aws_iam_role.aws_lb_controller.arn
}

################################################################################
# Fargate
################################################################################

output "fargate_pod_execution_role_arn" {
  description = "IAM role ARN for Fargate pod execution"
  value       = aws_iam_role.fargate_pod_execution.arn
}
