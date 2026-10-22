variable "name" {
  description = "Instance name. The demo instance was created by hand and is imported under this name."
  type        = string
}

variable "availability_zone" {
  type = string
}

variable "blueprint_id" {
  description = "Operating system image, for example ubuntu_24_04."
  type        = string
}

variable "bundle_id" {
  description = "Size, for example small_3_1 (2 GB RAM, 2 vCPU, 60 GB SSD)."
  type        = string
}

variable "key_pair_name" {
  description = "Existing Lightsail key pair for the ubuntu user. It is not created here, so its private key never touches Terraform state."
  type        = string
}

variable "ip_address_type" {
  description = "ipv4 or dualstack. Must match the existing instance, or Terraform would replace it."
  type        = string
  default     = "dualstack"
}

variable "ssh_allowed_cidrs" {
  description = "Addresses allowed to reach SSH (port 22). Empty keeps SSH closed to everyone (deploys open it for their own runner address for a short time)."
  type        = list(string)
  default     = []
}

variable "allow_lightsail_browser_ssh" {
  description = "Keep port 22 open to the Lightsail console's browser SSH, as an emergency way in."
  type        = bool
  default     = true
}

variable "snapshot_time" {
  description = "Daily automatic snapshot time, UTC, on the hour (HH:00)."
  type        = string
  default     = "22:00"
}
