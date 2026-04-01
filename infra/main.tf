terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }

  # Remote state in Azure Blob Storage.
  # Bootstrap: run `infra/bootstrap.sh` once to create the storage account,
  # then uncomment this block and run `terraform init -migrate-state`.
  # backend "azurerm" {
  #   resource_group_name  = "research-assistant-rg"
  #   storage_account_name = "researchassistanttfstate"   # must be globally unique
  #   container_name       = "tfstate"
  #   key                  = "deep-research-assistant.tfstate"
  # }
}

provider "azurerm" {
  features {}
}

# ---------------------------------------------------------------------------
# Resource Group
# ---------------------------------------------------------------------------
resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

# ---------------------------------------------------------------------------
# Storage Account for Terraform remote state (bootstrap resource)
# After first apply, enable the backend block above and migrate state.
# ---------------------------------------------------------------------------
resource "azurerm_storage_account" "tf_state" {
  name                     = var.tf_state_storage_account
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS" # cheapest replication

  tags = {
    purpose = "terraform-state"
  }
}

resource "azurerm_storage_container" "tf_state" {
  name                  = var.tf_state_container
  storage_account_name  = azurerm_storage_account.tf_state.name
  container_access_type = "private"
}

# ---------------------------------------------------------------------------
# PostgreSQL Flexible Server
# Tier: Burstable B1ms — cheapest option, covered by Azure student credits.
# Azure PostgreSQL enforces SSL/TLS by default; no extra resource needed.
# ---------------------------------------------------------------------------
resource "azurerm_postgresql_flexible_server" "postgres" {
  name                   = var.postgres_server_name
  resource_group_name    = azurerm_resource_group.rg.name
  location               = azurerm_resource_group.rg.location
  version                = "16"
  administrator_login    = var.db_username
  administrator_password = var.db_password

  storage_mb = 32768 # 32 GB — minimum allowed

  # Burstable B1ms: cheapest tier (~$12/mo), adequate for dev/student workloads.
  sku_name = "B_Standard_B1ms"

  # High availability increases cost — disable for student accounts.
  high_availability {
    mode = "Disabled"
  }
}

# Allow all Azure-internal traffic (0.0.0.0/0.0.0.0 is the Azure "allow Azure services" rule).
# The App Service (F1/B1) cannot use VNet integration, so this firewall rule is required.
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  name             = "allow-azure-internal"
  server_id        = azurerm_postgresql_flexible_server.postgres.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_postgresql_flexible_server_database" "db" {
  name      = var.db_name
  server_id = azurerm_postgresql_flexible_server.postgres.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# ---------------------------------------------------------------------------
# App Service Plan (Linux, B1)
# B1 Basic: 1 vCore, 1.75 GB RAM — cheapest always-on tier.
# ---------------------------------------------------------------------------
resource "azurerm_service_plan" "plan" {
  name                = "${var.app_name}-plan"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  os_type             = "Linux"
  sku_name            = "B1"
}

# ---------------------------------------------------------------------------
# Linux Web App (FastAPI backend)
# Deployed via zip + publish profile from CI/CD.
# ---------------------------------------------------------------------------
resource "azurerm_linux_web_app" "api" {
  name                = var.app_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  service_plan_id     = azurerm_service_plan.plan.id

  site_config {
    application_stack {
      python_version = "3.12"
    }
    startup_command = "uvicorn src.api.main:app --host 0.0.0.0 --port 8000"
  }

  app_settings = {
    "PYTHONPATH" = "/home/site/wwwroot"

    # --- Database ---
    "DATABASE_URL" = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${azurerm_postgresql_flexible_server.postgres.fqdn}:5432/${var.db_name}?sslmode=require"

    # --- Application secrets ---
    "TAVILY_API_KEY"   = var.tavily_api_key
    "DEEPSEEK_API_KEY" = var.deepseek_api_key
    "GOOGLE_API_KEY"   = var.google_api_key
    "AUTH_SECRET_KEY"  = var.auth_secret_key

    # --- Langfuse observability ---
    "LANGFUSE_PUBLIC_KEY" = var.langfuse_public_key
    "LANGFUSE_SECRET_KEY" = var.langfuse_secret_key
    "LANGFUSE_BASE_URL"   = var.langfuse_host

    # --- RAG (disabled; Chroma Cloud only when enabled) ---
    "ENABLE_RAG"           = "false"
    "CHROMA_CLOUD_HOST"    = var.chroma_cloud_host
    "CHROMA_CLOUD_PORT"    = var.chroma_cloud_port
    "CHROMA_CLOUD_API_KEY" = var.chroma_cloud_api_key
  }
}

# ---------------------------------------------------------------------------
# Linux Web App (Next.js frontend — static export served by `serve`)
# Reuses the same App Service Plan as the backend.
# ---------------------------------------------------------------------------
resource "azurerm_linux_web_app" "frontend" {
  name                = var.frontend_app_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  service_plan_id     = azurerm_service_plan.plan.id

  site_config {
    application_stack {
      node_version = "20-lts"
    }
    startup_command = "npx serve -s . -l $PORT"
  }
}
