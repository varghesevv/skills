resource "aws_lightsail_instance" "this" {
  name              = var.name
  availability_zone = var.availability_zone
  blueprint_id      = var.blueprint_id
  bundle_id         = var.bundle_id
  key_pair_name     = var.key_pair_name
  ip_address_type   = var.ip_address_type

  add_on {
    type          = "AutoSnapshot"
    snapshot_time = var.snapshot_time
    status        = "Enabled"
  }

  lifecycle {
    # The server is set up over SSH (infra/scripts/bootstrap-server.sh), not by user data, and
    # user data cannot be changed on an existing instance without replacing it.
    ignore_changes = [user_data]
  }
}

# A static IP keeps its address when the instance is stopped and started. Attaching one gives
# the instance a NEW public address; the DNS record follows it.
resource "aws_lightsail_static_ip" "this" {
  name = "${var.name}-ip"
}

resource "aws_lightsail_static_ip_attachment" "this" {
  static_ip_name = aws_lightsail_static_ip.this.name
  instance_name  = aws_lightsail_instance.this.name
}

resource "aws_lightsail_instance_public_ports" "this" {
  instance_name = aws_lightsail_instance.this.name

  # HTTP stays open: Caddy needs it for certificates, and redirects to HTTPS.
  port_info {
    protocol  = "tcp"
    from_port = 80
    to_port   = 80
    cidrs     = ["0.0.0.0/0"]
  }

  port_info {
    protocol  = "tcp"
    from_port = 443
    to_port   = 443
    cidrs     = ["0.0.0.0/0"]
  }

  dynamic "port_info" {
    for_each = (length(var.ssh_allowed_cidrs) > 0 || var.allow_lightsail_browser_ssh) ? [1] : []

    content {
      protocol          = "tcp"
      from_port         = 22
      to_port           = 22
      cidrs             = var.ssh_allowed_cidrs
      cidr_list_aliases = var.allow_lightsail_browser_ssh ? ["lightsail-connect"] : []
    }
  }
}
