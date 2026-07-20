data "aws_availability_zones" "available" {
  state = "available"
}

module "vpc" {
  source                       = "terraform-aws-modules/vpc/aws"
  version                      = "~> 6.0"
  name                         = local.name
  cidr                         = var.vpc_cidr
  azs                          = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets              = [for index in range(3) : cidrsubnet(var.vpc_cidr, 4, index)]
  public_subnets               = [for index in range(3) : cidrsubnet(var.vpc_cidr, 4, index + 8)]
  database_subnets             = [for index in range(3) : cidrsubnet(var.vpc_cidr, 6, index + 48)]
  enable_nat_gateway           = true
  single_nat_gateway           = var.environment != "production"
  one_nat_gateway_per_az       = var.environment == "production"
  enable_dns_hostnames         = true
  enable_dns_support           = true
  create_database_subnet_group = true
  private_subnet_tags          = { "kubernetes.io/role/internal-elb" = 1 }
  public_subnet_tags           = { "kubernetes.io/role/elb" = 1 }
  tags                         = local.tags
}

module "eks" {
  source                                   = "terraform-aws-modules/eks/aws"
  version                                  = "~> 21.0"
  name                                     = local.name
  kubernetes_version                       = "1.34"
  endpoint_public_access                   = true
  endpoint_private_access                  = true
  enable_cluster_creator_admin_permissions = true
  vpc_id                                   = module.vpc.vpc_id
  subnet_ids                               = module.vpc.private_subnets
  addons = {
    coredns                = {}
    eks-pod-identity-agent = { before_compute = true }
    kube-proxy             = {}
    vpc-cni                = { before_compute = true }
  }
  eks_managed_node_groups = {
    general = {
      instance_types = ["m7g.large"]
      ami_type       = "AL2023_ARM_64_STANDARD"
      min_size       = 3
      max_size       = 20
      desired_size   = 3
      capacity_type  = "ON_DEMAND"
      labels         = { workload = "general" }
    }
    workers = {
      instance_types = ["c7g.xlarge"]
      ami_type       = "AL2023_ARM_64_STANDARD"
      min_size       = 1
      max_size       = 50
      desired_size   = 2
      capacity_type  = "SPOT"
      labels         = { workload = "agents" }
      taints         = { agents = { key = "workload", value = "agents", effect = "NO_SCHEDULE" } }
    }
  }
  tags = local.tags
}

resource "random_password" "database" {
  length  = 32
  special = true
}

resource "random_password" "encryption" {
  length  = 48
  special = false
}

resource "aws_security_group" "data" {
  name        = "${local.name}-data"
  description = "Data services accessible only from EKS nodes"
  vpc_id      = module.vpc.vpc_id
  ingress {
    description     = "PostgreSQL from EKS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
  ingress {
    description     = "Redis from EKS"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_kms_key" "platform" {
  description             = "ProActive SEO application and data encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = local.tags
}

resource "aws_db_instance" "postgres" {
  identifier                   = local.name
  engine                       = "postgres"
  engine_version               = "16.9"
  instance_class               = var.database_instance_class
  allocated_storage            = 100
  max_allocated_storage        = 1000
  storage_type                 = "gp3"
  storage_encrypted            = true
  kms_key_id                   = aws_kms_key.platform.arn
  db_name                      = "proactive"
  username                     = "proactive"
  password                     = random_password.database.result
  db_subnet_group_name         = module.vpc.database_subnet_group_name
  vpc_security_group_ids       = [aws_security_group.data.id]
  multi_az                     = var.environment == "production"
  backup_retention_period      = var.environment == "production" ? 35 : 7
  deletion_protection          = var.environment == "production"
  skip_final_snapshot          = var.environment != "production"
  performance_insights_enabled = true
  auto_minor_version_upgrade   = true
  apply_immediately            = false
  tags                         = local.tags
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = local.name
  subnet_ids = module.vpc.database_subnets
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = local.name
  description                = "ProActive SEO Redis cache, sessions, Celery, and Streams"
  engine                     = "redis"
  node_type                  = var.redis_node_type
  num_cache_clusters         = var.environment == "production" ? 3 : 2
  automatic_failover_enabled = true
  multi_az_enabled           = var.environment == "production"
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  kms_key_id                 = aws_kms_key.platform.arn
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.data.id]
  snapshot_retention_limit   = 7
  tags                       = local.tags
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "${local.name}-artifacts"
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.platform.arn
      sse_algorithm     = "aws:kms"
    }
  }
}
resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_secretsmanager_secret" "application" {
  name                    = "/proactive-seo/${var.environment}/application"
  kms_key_id              = aws_kms_key.platform.arn
  recovery_window_in_days = 30
  tags                    = local.tags
}
resource "aws_secretsmanager_secret_version" "application" {
  secret_id = aws_secretsmanager_secret.application.id
  secret_string = jsonencode({
    APP_DATABASE_URL              = "postgresql+asyncpg://proactive:${urlencode(random_password.database.result)}@${aws_db_instance.postgres.address}:5432/proactive"
    APP_REDIS_URL                 = "rediss://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
    APP_CREDENTIAL_ENCRYPTION_KEY = random_password.encryption.result
    APP_LIVE_ACTIONS_ENABLED      = "false"
  })
}

resource "cloudflare_ruleset" "waf" {
  count       = var.cloudflare_zone_id == "" ? 0 : 1
  zone_id     = var.cloudflare_zone_id
  name        = "ProActive SEO custom WAF"
  description = "Block common exploit paths and suspicious automation"
  kind        = "zone"
  phase       = "http_request_firewall_custom"
  rules = [
    {
      action      = "block"
      description = "Block common secret and traversal probes"
      expression  = "http.request.uri.path contains \"/.env\" or http.request.uri.path contains \"/.git\" or http.request.uri.path contains \"../\""
      enabled     = true
      ref         = "block_secret_probes"
    },
    {
      action      = "managed_challenge"
      description = "Challenge high-volume unauthenticated API traffic"
      expression  = "starts_with(http.request.uri.path, \"/api/v1/auth/\") and cf.bot_management.score lt 30"
      enabled     = true
      ref         = "challenge_auth_bots"
    }
  ]
}
