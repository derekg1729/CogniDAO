from prefect import flow

# Deployment script for the Ritual of Presence flow
if __name__ == "__main__":
    # Deploy from local source
    print("Deploying Ritual of Presence flow to cogni-pool...")
    
    flow.from_source(
        source=".",  # Use current directory
        entrypoint="ritual_of_presence.py:ritual_of_presence_flow",
    ).deploy(
        name="ritual-of-presence",
        work_pool_name="cogni-pool",
        cron="0 * * * *",  # Run every hour
        tags=["cogni", "ritual"],
        description="Ritual of Presence: Generate thoughts with full core context",
    )
    
    print("Deployment complete! To run, use: prefect deployment run 'ritual-of-presence-flow/ritual-of-presence'")