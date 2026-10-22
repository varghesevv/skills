variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "environment" {
  description = "Environment name; used in tags and resource names. A production stack would be envs/prod with its own value."
  type        = string
  default     = "demo"
}

variable "name_prefix" {
  type    = string
  default = "skills"
}

variable "instance_name" {
  description = "Name of the existing (hand-made) instance to adopt."
  type        = string
  default     = "skills"
}

variable "availability_zone" {
  type    = string
  default = "ap-south-1a"
}

variable "blueprint_id" {
  type    = string
  default = "ubuntu_24_04"
}

variable "bundle_id" {
  type    = string
  default = "small_3_1"
}

variable "key_pair_name" {
  description = "The existing Lightsail key pair of the instance."
  type        = string
  default     = "skills-demo"
}

variable "domain_name" {
  type    = string
  default = "skills-demo.privatedir.in"
}

variable "parent_zone_name" {
  description = "The existing Route 53 zone. It is looked up, never created or destroyed here."
  type        = string
  default     = "privatedir.in"
}

variable "ssh_allowed_cidrs" {
  description = "Your own address(es) for manual SSH, for example [\"203.0.113.10/32\"] (Q13). Empty means no manual SSH."
  type        = list(string)
  default     = []
}

variable "allow_lightsail_browser_ssh" {
  type    = bool
  default = true
}

variable "snapshot_time" {
  description = "Daily snapshot time in UTC (22:00 UTC is 02:00 in Dubai)."
  type        = string
  default     = "22:00"
}
