variable "environment" {
  type    = string
  default = "staging"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "domain_name" {
  type    = string
  default = "app.example.com"
}

variable "cloudflare_zone_id" {
  type    = string
  default = ""
}

variable "cloudflare_api_token" {
  type      = string
  sensitive = true
  default   = ""
}

variable "database_instance_class" {
  type    = string
  default = "db.r7g.large"
}

variable "redis_node_type" {
  type    = string
  default = "cache.r7g.large"
}

locals {
  name = "proactive-seo-${var.environment}"
  tags = {
    Project     = "proactive-seo"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
