terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# The bootstrap creates the bucket that holds every other Terraform state, so it cannot use
# that bucket itself. Its own state stays in a local file (git-ignored): keep a copy safe.
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.name_prefix
      ManagedBy = "terraform"
      Stack     = "bootstrap"
    }
  }
}
