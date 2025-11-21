import os, logging, json
from datetime import datetime, timedelta
from dateutil import parser
import azure.functions as func
from azure.cosmos import CosmosClient, PartitionKey

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "SentimentDB")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER", "Sentiments")
SUMMARY_CONTAINER = os.getenv("SUMMARY_CONTAINER", "Summaries")

def get_cosmos_client():
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        logging.warning("Cosmos not configured; summary will not run.")
        return None
    return CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)

def main(timer: func.TimerRequest):
    logging.info("DailySummary trigger started")
    client = get_cosmos_client()
    if not client:
        logging.warning("No Cosmos client - exiting")
        return

    db = client.get_database_client(COSMOS_DATABASE)
    sentiments = db.get_container_client(COSMOS_CONTAINER)
    summaries = db.create_container_if_not_exists(id=SUMMARY_CONTAINER, partition_key=PartitionKey(path="/id"))

    # compute for last 24 hours
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    # query ISO timestamp comparison
    start_iso = yesterday.isoformat() + "Z"

    query = f"SELECT c.label, c.score FROM c WHERE c.timestamp >= '{start_iso}'"
    items = list(sentiments.query_items(query=query, enable_cross_partition_query=True))

    if not items:
        logging.info("No items in last 24h")
        summary = {
            "id": str(now.timestamp()),
            "timestamp": now.isoformat() + "Z",
            "count": 0,
            "avg_score": None,
            "positive": 0,
            "neutral": 0,
            "negative": 0
        }
    else:
        total = sum([i.get("score", 0) for i in items])
        count = len(items)
        avg = round(total / count, 3) if count else None
        pos = sum(1 for i in items if i.get("label") == "positive")
        neu = sum(1 for i in items if i.get("label") == "neutral")
        neg = sum(1 for i in items if i.get("label") == "negative")
        summary = {
            "id": str(now.timestamp()),
            "timestamp": now.isoformat() + "Z",
            "count": count,
            "avg_score": avg,
            "positive": pos,
            "neutral": neu,
            "negative": neg
        }

    # upsert summary
    try:
        summaries.upsert_item(summary)
        logging.info("Summary upserted: %s", summary)
    except Exception as e:
        logging.error("Failed to upsert summary: %s", e)
