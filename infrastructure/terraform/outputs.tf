output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value     = module.eks.cluster_endpoint
  sensitive = true
}

output "database_endpoint" {
  value     = aws_db_instance.postgres.address
  sensitive = true
}

output "redis_endpoint" {
  value     = aws_elasticache_replication_group.redis.primary_endpoint_address
  sensitive = true
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.id
}

output "application_secret_arn" {
  value = aws_secretsmanager_secret.application.arn
}
