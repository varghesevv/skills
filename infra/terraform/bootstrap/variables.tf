variable "region" {
  description = "AWS region for the state bucket and the IAM resources' ARNs."
  type        = string
  default     = "ap-south-1"
}

variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
  default     = "skills"
}

variable "environment_name" {
  description = "The GitHub Environment (and Terraform environment) the roles trust."
  type        = string
  default     = "demo"
}

variable "github_repository" {
  description = "GitHub repository (owner/name) whose workflows may assume the roles."
  type        = string
  default     = "varghesevv/skills"
}

variable "github_repository_immutable" {
  description = "The same repository in GitHub's immutable OIDC form: owner@<owner id>/name@<repo id>."
  type        = string
  default     = "varghesevv@1423145/skills@1427422104"
}

variable "parent_zone_name" {
  description = "The existing Route 53 zone the demo record lives in. It is looked up, never created."
  type        = string
  default     = "privatedir.in"
}

variable "backup_bucket_prefix" {
  description = "Backup bucket names start with this (the account id is added); the Terraform role may manage only buckets with this prefix."
  type        = string
  default     = "skills-demo-backups"
}
