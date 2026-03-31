#!/usr/bin/env bash
# Run this ONCE before the first `terraform init` to create the storage account
# that holds Terraform remote state. After this script succeeds, uncomment the
# backend "azurerm" block in main.tf and run `terraform init -migrate-state`.
set -euo pipefail

RESOURCE_GROUP="research-assistant-rg"
LOCATION="polandcentral"
STORAGE_ACCOUNT="researchassistanttfstate"  # must be globally unique
CONTAINER="tfstate"

echo "Creating resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

echo "Creating storage account..."
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --encryption-services blob

echo "Creating blob container..."
az storage container create \
  --name "$CONTAINER" \
  --account-name "$STORAGE_ACCOUNT"

echo ""
echo "Done. Now uncomment the backend block in infra/main.tf and run:"
echo "  cd infra && terraform init -migrate-state"
