from prefect import flow, task
from prefect.blocks.system import Secret
import tweepy  # or MCP client for X API

@task
def get_next_message():
    # Read from message-queue.md
    with open('broadcast/message-queue.md', 'r') as file:
        return file.readline().strip()

@task
def post_to_x(msg):
    # Retrieve the API key from the Prefect Secret block
    api_key = Secret.load("X_API_KEY").get()
    # Use the API key with Tweepy or MCP client
    print(f"Tweeting: {msg}")
    # client = tweepy.Client(bearer_token=api_key)
    # client.create_tweet(text=msg)

@task
def log_post(msg):
    with open('broadcast/sent-log.md', 'a') as log_file:
        log_file.write(f"{msg}\n")

@flow
def cogni_broadcast():
    msg = get_next_message()
    if msg:
        post_to_x(msg)
        log_post(msg)

if __name__ == "__main__":
    cogni_broadcast() 