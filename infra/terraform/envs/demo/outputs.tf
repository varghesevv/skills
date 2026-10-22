output "static_ip_address" {
  description = "The server's public address (the DNS record points here)."
  value       = module.host.static_ip_address
}

output "instance_name" {
  value = module.host.instance_name
}

output "backup_bucket" {
  description = "Set as BACKUP_BUCKET in the GitHub Environment."
  value       = module.backups.bucket_name
}

output "backup_user" {
  description = "Create an access key for this IAM user by hand and store it in the GitHub Environment secrets."
  value       = module.backups.user_name
}

output "site_url" {
  value = "https://${var.domain_name}"
}
