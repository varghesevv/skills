output "state_bucket" {
  description = "Set as the GitHub repository variable TF_STATE_BUCKET and in envs/demo/backend.hcl."
  value       = aws_s3_bucket.state.bucket
}

output "terraform_role_arn" {
  description = "Set as the GitHub repository variable AWS_TERRAFORM_ROLE_ARN."
  value       = aws_iam_role.terraform.arn
}

output "deploy_role_arn" {
  description = "Set as the GitHub repository variable AWS_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.deploy.arn
}
