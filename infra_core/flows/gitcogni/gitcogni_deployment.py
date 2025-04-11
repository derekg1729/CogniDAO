from prefect import flow

# Deployment script for the GitCogni flow
if __name__ == "__main__":
    # Deploy from local source
    print("Deploying GitCogni review flow to cogni-pool...")
    
    flow.from_source(
        source=".",  # Use current directory
        entrypoint="gitcogni_flow.py:gitcogni_review_flow",
    ).deploy(
        name="gitcogni-review",
        work_pool_name="cogni-pool",
        tags=["cogni", "git"],
        description="GitCogni: Review PRs and commits with AI pedantry",
        parameters={
            "pr_url": None,  # Required parameter
            "test_mode": False  # Optional parameter, default to False
        }
    )
    
    print("Deployment complete!")
    print("To run, use: prefect deployment run 'gitcogni-review-flow/gitcogni-review'")
    print("Parameter options:")
    print("  --param pr_url='https://github.com/owner/repo/pull/123'  # Required: GitHub PR URL to review")
    print("  --param test_mode=true                                   # Optional: Clean up files after execution")