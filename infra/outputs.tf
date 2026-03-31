output "webapp_url" {
  description = "Public URL of the deployed backend API"
  value       = "https://${azurerm_linux_web_app.webapp.default_hostname}"
}

output "postgres_fqdn" {
  description = "Fully-qualified domain name of the PostgreSQL server"
  value       = azurerm_postgresql_flexible_server.postgres.fqdn
}

output "database_url" {
  description = "Async DATABASE_URL to paste into .env or CI secrets"
  value       = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${azurerm_postgresql_flexible_server.postgres.fqdn}:5432/${var.db_name}?ssl=true"
  sensitive   = true
}

output "tf_state_storage_account" {
  description = "Storage account name holding Terraform remote state"
  value       = azurerm_storage_account.tf_state.name
}
