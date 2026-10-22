# The bucket name comes from backend.hcl (git-ignored, see backend.hcl.example) or from
# -backend-config in CI, because a backend block cannot use variables.
terraform {
  backend "s3" {
    key          = "envs/demo/terraform.tfstate"
    region       = "ap-south-1"
    encrypt      = true
    use_lockfile = true
  }
}
