import os, logging, json
import azure.functions as func
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "SentimentDB")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER", "Sentiments")

def get_container():
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        logging.warning("COSMOS not configured; GET results will return empty.")
        return None
    client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    db = client.get_database_client(COSMOS_DATABASE)
    container = db.get_container_client(COSMOS_CONTAINER)
    return container

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("GetResults: received request")
    top = int(req.params.get("top", "20"))
    container = get_container()
    if not container:
        return func.HttpResponse(json.dumps({"error": "Cosmos DB not configured"}), status_code=200, mimetype="application/json")
    try:
        query = f"SELECT TOP {top} c.id, c.label, c.score, c.timestamp, c.text FROM c ORDER BY c.timestamp DESC"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        return func.HttpResponse(json.dumps(items), status_code=200, mimetype="application/json")
    except CosmosHttpResponseError as e:
        logging.error("Cosmos query error: %s", e)
        return func.HttpResponse("Cosmos query error", status_code=500)
