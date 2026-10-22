provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.name_prefix
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_route53_zone" "parent" {
  name         = var.parent_zone_name
  private_zone = false
}

module "host" {
  source = "../../modules/lightsail_host"

  name                        = var.instance_name
  availability_zone           = var.availability_zone
  blueprint_id                = var.blueprint_id
  bundle_id                   = var.bundle_id
  key_pair_name               = var.key_pair_name
  ssh_allowed_cidrs           = var.ssh_allowed_cidrs
  allow_lightsail_browser_ssh = var.allow_lightsail_browser_ssh
  snapshot_time               = var.snapshot_time
}

module "backups" {
  source = "../../modules/backup_bucket"

  bucket_name = "${var.name_prefix}-${var.environment}-backups-${data.aws_caller_identity.current.account_id}"
  user_name   = "${var.name_prefix}-${var.environment}-backup"
}

resource "aws_route53_record" "site" {
  zone_id = data.aws_route53_zone.parent.zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [module.host.static_ip_address]
}
