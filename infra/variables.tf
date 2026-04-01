variable "resource_group_name" {
  description = "Name of the resource group"
  default     = "research-assistant-rg"
}

variable "location" {
  description = "Azure region"
  default     = "polandcentral"
}

variable "postgres_server_name" {
  description = "Name of the PostgreSQL flexible server (must be globally unique)"
  default     = "research-db-server"
}

variable "db_username" {
  description = "PostgreSQL administrator login"
  default     = "adminuser"
}

variable "db_password" {
  description = "PostgreSQL administrator password"
  sensitive   = true
}

variable "db_name" {
  description = "Name of the database"
  default     = "research_db"
}

variable "app_name" {
  description = "Name of the backend Web App (must be globally unique)"
  default     = "deep-research-assistant-api"
}

variable "frontend_app_name" {
  description = "Name of the frontend Web App (must be globally unique)"
  default     = "deep-research-assistant-ui"
}

# Application secrets — passed via TF_VAR_* env vars or tfvars (never commit real values)
variable "tavily_api_key" {
  description = "Tavily search API key"
  sensitive   = true
}

variable "deepseek_api_key" {
  description = "DeepSeek LLM API key"
  sensitive   = true
}

variable "google_api_key" {
  description = "Google Generative AI API key (used for embeddings when RAG enabled)"
  sensitive   = true
  default     = ""
}

variable "auth_secret_key" {
  description = "HMAC secret for JWT-like auth tokens"
  sensitive   = true
}

# Langfuse observability
variable "langfuse_public_key" {
  description = "Public key for Langfuse"
  sensitive   = true
  default     = ""
}

variable "langfuse_secret_key" {
  description = "Secret key for Langfuse"
  sensitive   = true
  default     = ""
}

variable "langfuse_host" {
  description = "Langfuse base URL"
  default     = "https://cloud.langfuse.com"
}

# Chroma Cloud (RAG — disabled by default; only cloud, no local)
variable "chroma_cloud_host" {
  description = "Chroma Cloud host (leave empty when RAG disabled)"
  default     = ""
}

variable "chroma_cloud_port" {
  description = "Chroma Cloud port"
  default     = "443"
}

variable "chroma_cloud_api_key" {
  description = "API key for Chroma Cloud"
  sensitive   = true
  default     = ""
}

# Terraform state storage (used only in backend.tf — kept as variables for reference)
variable "tf_state_storage_account" {
  description = "Azure Storage Account name for Terraform remote state"
  default     = "researchassistanttfstate"
}

variable "tf_state_container" {
  description = "Blob container name for Terraform state"
  default     = "tfstate"
}
