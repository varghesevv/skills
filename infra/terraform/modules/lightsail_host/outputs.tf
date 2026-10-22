output "instance_name" {
  value = aws_lightsail_instance.this.name
}

output "instance_arn" {
  value = aws_lightsail_instance.this.arn
}

output "static_ip_address" {
  value = aws_lightsail_static_ip.this.ip_address
}
