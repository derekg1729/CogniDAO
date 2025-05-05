from prefect import flow

# Deployment script for the X Posting flow
if __name__ == "__main__":
    # Deploy from local source
    print("Deploying X Posting flow to cogni-pool...")
    
    flow.from_source(
        source=".",  # Use current directory
        entrypoint="x_posting_flow.py:async_x_posting_flow",
    ).deploy(
        name="x-posting-flow",
        work_pool_name="cogni-pool",
        cron="0 */6 * * *",  # Run every 6 hours
        tags=["cogni", "broadcast", "x"],
        description="X Posting Flow: Post approved content from broadcast queue to X",
        parameters={
            "post_limit": 3,
            "simulation_mode": False  # Run in live mode
        }
    )
    
    print("Deployment complete! To run, use: prefect deployment run 'async-x-posting-flow/x-posting-flow'") 