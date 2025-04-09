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
    )
    
    print("Deployment complete!")
    print("To run, use: prefect deployment run 'gitcogni-review-flow/gitcogni-review'")
    print("Parameter options:")
    print("  --param pr_identifier='https://github.com/username/repo/pull/123'  # Use PR URL")
    print("  --param pr_identifier='username/repo#123'                          # Use repo and PR number")
    print("  --param base_branch=main --param head_branch=feature-branch        # Compare branches directly") 