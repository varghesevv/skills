variable "bucket_name" {
  description = "Globally unique bucket name."
  type        = string
}

variable "user_name" {
  description = "IAM user the server uses to write backups."
  type        = string
}

variable "expire_days" {
  description = "Backups are deleted after this many days."
  type        = number
  default     = 30
}
