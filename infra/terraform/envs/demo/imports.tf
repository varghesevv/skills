# The instance was created by hand before Terraform existed. This block makes the first
# `plan` adopt it instead of creating a second one. The plan must show NO replacement of the
# instance ("must be replaced" would destroy the server): if it does, stop and fix the
# arguments. After the first successful apply this file can stay; it does nothing once the
# resource is in state.
import {
  to = module.host.aws_lightsail_instance.this
  id = var.instance_name
}
