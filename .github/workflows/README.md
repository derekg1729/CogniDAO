# GitHub Workflows

This directory contains GitHub Actions workflows for automating CI/CD processes.

## Workflow Files

- `deploy.yml` - Deploys the application to preview and production environments
- `validate-workflows.yml` - Validates the syntax of all workflow files
- `local-test.yml` - For local testing of the application

## Workflow Validation

Workflow files are automatically validated when changes are made via the `validate-workflows.yml` workflow. 
This ensures that syntax errors are caught before deployment workflows are run.

### Manual Validation

To manually validate workflow files:

1. Push changes to a branch and create a PR
2. The validation workflow will automatically run
3. Alternatively, trigger the validation workflow manually via the GitHub Actions UI

## Deployment Process

The `deploy.yml` workflow handles deployment to both preview and production environments:

- **Preview Environment**: Automatically deployed on pushes to main branch
- **Production Environment**: Requires manual approval through GitHub environments

### Required Secrets

The deployment workflow requires the following secrets to be configured:

| Secret Name | Environment | Description |
|-------------|------------|-------------|
| `PREVIEW_SSH_KEY` | preview | SSH private key for the preview server |
| `PREVIEW_SERVER_IP` | preview | IP address of the preview server |
| `PROD_SSH_KEY` | prod | SSH private key for the production server |
| `PROD_SERVER_IP` | prod | IP address of the production server |
| `OPENAI_API_KEY` | both | OpenAI API key |
| `COGNI_API_KEY` | both | Cogni API key | 