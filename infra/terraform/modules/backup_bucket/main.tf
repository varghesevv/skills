resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name

  # Backups must survive an accidental `terraform destroy`. Remove this line on purpose to
  # tear the environment down completely.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    id     = "expire-old-backups"
    status = "Enabled"

    filter {}

    expiration {
      days = var.expire_days
    }
    noncurrent_version_expiration {
      noncurrent_days = var.expire_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}

# Lightsail instances cannot use instance roles, so the server uses an IAM user that can only
# write to and read from this bucket. The access key is NOT created here: create it by hand and
# put it in the GitHub Environment secrets, so the secret never enters Terraform state.
resource "aws_iam_user" "backup" {
  name = var.user_name
}

data "aws_iam_policy_document" "backup" {
  statement {
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.this.arn]
  }
  statement {
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.this.arn}/*"]
  }
}

resource "aws_iam_user_policy" "backup" {
  name   = "backup-bucket-only"
  user   = aws_iam_user.backup.name
  policy = data.aws_iam_policy_document.backup.json
}
