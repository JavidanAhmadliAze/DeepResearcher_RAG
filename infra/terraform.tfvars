# ============================================================
# terraform.tfvars — example values, DO NOT commit real secrets.
# Copy this file, fill in real values, and keep it out of git
# (it is already in .gitignore via the *.tfvars pattern).
# Pass secrets via TF_VAR_* env vars in CI instead.
# ============================================================

resource_group_name  = "research-assistant-rg"
location             = "polandcentral"
postgres_server_name = "research-db-server"        # must be globally unique in Azure
app_service_plan_name = "research-app-plan"
app_name             = "deep-research-assistant-api" # must be globally unique in Azure

# PostgreSQL admin credentials
db_username = "adminuser"
db_password = "Javi_1865_Engineering"
db_name     = "research_db"

# Terraform state storage
tf_state_storage_account = "researchassistanttfstate" # must be globally unique, lowercase, 3-24 chars
tf_state_container        = "tfstate"

# Application secrets
tavily_api_key  = "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"
deepseek_api_key = "sk-fa87ea6c1d874c20a149bc9a90211fa3"
google_api_key  = ""   # only needed when ENABLE_RAG=true
auth_secret_key = "JsiaK4YpYLSqUBZe9OVP8WVLEMuHuCsQJK0M5FHeFu8"

# Langfuse (optional — leave empty to disable observability)
langfuse_public_key = ""
langfuse_secret_key = ""
langfuse_host       = "https://cloud.langfuse.com"

# Chroma Cloud (only used when ENABLE_RAG=true)
chroma_cloud_host    = ""
chroma_cloud_port    = "443"
chroma_cloud_api_key = ""
