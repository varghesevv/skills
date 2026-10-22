data "aws_caller_identity" "current" {}

data "aws_route53_zone" "parent" {
  name         = var.parent_zone_name
  private_zone = false
}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  state_bucket = "${var.name_prefix}-terraform-state-${local.account_id}"
  github_sub   = "repo:${var.github_repository}"
}

# ---- Terraform state ----------------------------------------------------------------------

resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---- GitHub Actions sign-in (OIDC, no stored AWS keys) ------------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "terraform_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Pull request plans, and applies that wait for approval in the GitHub Environment.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "${local.github_sub}:pull_request",
        "${local.github_sub}:environment:${var.environment_name}",
      ]
    }
  }
}

data "aws_iam_policy_document" "deploy_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${local.github_sub}:environment:${var.environment_name}"]
    }
  }
}

# ---- Role: skills-terraform (plan and apply) ----------------------------------------------

resource "aws_iam_role" "terraform" {
  name               = "${var.name_prefix}-terraform"
  assume_role_policy = data.aws_iam_policy_document.terraform_trust.json
}

data "aws_iam_policy_document" "terraform" {
  statement {
    sid       = "Lightsail"
    actions   = ["lightsail:*"]
    resources = ["*"]
  }

  statement {
    sid       = "StateBucketList"
    actions   = ["s3:ListBucket", "s3:GetBucketVersioning"]
    resources = [aws_s3_bucket.state.arn]
  }
  statement {
    sid       = "StateObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.state.arn}/*"]
  }

  # Terraform creates and configures the backup bucket. It never reads or writes the backups
  # themselves, so there are no object-level permissions here.
  statement {
    sid = "BackupBuckets"
    actions = [
      "s3:CreateBucket", "s3:DeleteBucket", "s3:ListBucket", "s3:ListBucketVersions",
      "s3:GetBucket*", "s3:PutBucket*",
      "s3:GetLifecycleConfiguration", "s3:PutLifecycleConfiguration",
      "s3:GetEncryptionConfiguration", "s3:PutEncryptionConfiguration",
      "s3:GetAccelerateConfiguration", "s3:GetReplicationConfiguration",
    ]
    resources = ["arn:aws:s3:::${var.backup_bucket_prefix}-*"]
  }

  statement {
    sid = "BackupUser"
    actions = [
      "iam:CreateUser", "iam:DeleteUser", "iam:GetUser", "iam:TagUser", "iam:UntagUser",
      "iam:ListUserTags", "iam:PutUserPolicy", "iam:GetUserPolicy", "iam:DeleteUserPolicy",
      "iam:ListUserPolicies", "iam:ListAttachedUserPolicies", "iam:ListGroupsForUser",
      "iam:ListAccessKeys",
    ]
    resources = ["arn:aws:iam::${local.account_id}:user/${var.name_prefix}-*"]
  }

  statement {
    sid = "DnsRecord"
    actions = [
      "route53:ChangeResourceRecordSets", "route53:ListResourceRecordSets",
      "route53:GetHostedZone", "route53:ListTagsForResource",
    ]
    resources = [data.aws_route53_zone.parent.arn]
  }
  statement {
    sid       = "DnsLookup"
    actions   = ["route53:ListHostedZones", "route53:ListHostedZonesByName", "route53:GetChange"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "terraform" {
  name   = "terraform"
  role   = aws_iam_role.terraform.id
  policy = data.aws_iam_policy_document.terraform.json
}

# ---- Role: skills-deploy (only opens and closes ports on the demo instance) ---------------

resource "aws_iam_role" "deploy" {
  name               = "${var.name_prefix}-deploy"
  assume_role_policy = data.aws_iam_policy_document.deploy_trust.json
}

data "aws_iam_policy_document" "deploy" {
  statement {
    sid = "InstanceFirewall"
    actions = [
      "lightsail:GetInstance", "lightsail:GetInstancePortStates",
      "lightsail:OpenInstancePublicPorts", "lightsail:CloseInstancePublicPorts",
    ]
    resources = ["arn:aws:lightsail:${var.region}:${local.account_id}:Instance/*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
