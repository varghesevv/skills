# Core Terraform rules only (no provider plugin download needed).
config {
  call_module_type = "local"
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}
