from prefect import flow, task
import tweepy  # or MCP client for X API

@task
def get_next_message():
    # Read from message-queue.md
    with open('broadcast/message-queue.md', 'r') as file:
        return file.readline().strip()

@task
def post_to_x(msg):
    # Use Tweepy or MCP client to post to X
    print(f"Tweeting: {msg}")
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