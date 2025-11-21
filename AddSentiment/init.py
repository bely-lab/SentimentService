import os
import logging
import json
import azure.functions as func
from datetime import datetime
from dateutil import tz

# Cosmos SDK
from azure.cosmos import CosmosClient, PartitionKey, exceptions

# Text analytics env
TEXT_ENDPOINT = os.getenv("TEXTANALYTICS_ENDPOINT")
TEXT_KEY = os.getenv("TEXTANALYTICS_KEY")

# Cosmos env
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "SentimentDB")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER", "Sentiments")

# Cosmos client cached
_cosmos_client = None
_database = None
_container = None

def get_cosmos_container():
    global _cosmos_client, _database, _container
    if _container:
        return _container
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        logging.warning("COSMOS not configured - skipping DB storage.")
        return None
    _cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    _database = _cosmos_client.create_database_if_not_exists(id=COSMOS_DATABASE)
    _container = _database.create_container_if_not_exists(
        id=COSMOS_CONTAINER,
        partition_key=PartitionKey(path="/id"),
        offer_throughput=400
    )
    return _container

def analyze_with_textblob(text):
    try:
        from textblob import TextBlob
    except Exception as e:
        logging.error("TextBlob not available: %s", e)
        return {"label": "neutral", "score": 0.5, "model": "fallback"}
    tb = TextBlob(text)
    polarity = tb.sentiment.polarity
    if polarity > 0.1:
        label = "positive"
    elif polarity < -0.1:
        label = "negative"
    else:
        label = "neutral"
    score = round((polarity + 1) / 2, 3)
    return {"label": label, "score": score, "model": "textblob"}

def analyze_with_azure(text):
    try:
        from azure.ai.textanalytics import TextAnalyticsClient
        from azure.core.credentials import AzureKeyCredential
    except Exception as e:
        logging.error("Azure Text Analytics SDK not available: %s", e)
        return None
    try:
        client = TextAnalyticsClient(endpoint=TEXT_ENDPOINT, credential=AzureKeyCredential(TEXT_KEY))
        response = client.analyze_sentiment(documents=[text])[0]
        label = response.sentiment
        scores = response.confidence_scores
        score = {
            "positive": scores.positive,
            "neutral": scores.neutral,
            "negative": scores.negative
        }.get(label, 0.0)
        return {"label": label, "score": round(score, 3), "model": "azure_text_analytics"}
    except Exception as e:
        logging.error("Azure Text Analytics error: %s", e)
        return None

def upsert_to_cosmos(item):
    container = get_cosmos_container()
    if not container:
        return False
    try:
        container.upsert_item(item)
        return True
    except Exception as e:
        logging.error("Cosmos upsert failed: %s", e)
        return False

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("AddSentiment: received request")
    try:
        body = req.get_json()
        text = body.get("text", "").strip()
        metadata = body.get("metadata", {})  # optional
    except Exception as e:
        logging.error("Invalid JSON: %s", e)
        return func.HttpResponse("Invalid JSON", status_code=400)

    if not text:
        return func.HttpResponse("Field 'text' is required", status_code=400)

    # Analyze
    result = None
    if TEXT_ENDPOINT and TEXT_KEY:
        result = analyze_with_azure(text)
    if not result:
        result = analyze_with_textblob(text)

    # Build item to store
    timestamp = datetime.utcnow().isoformat() + "Z"
    # create id - simple: timestamp + random suffix
    import uuid
    item = {
        "id": str(uuid.uuid4()),
        "text": text,
        "label": result.get("label"),
        "score": result.get("score"),
        "model": result.get("model"),
        "metadata": metadata,
        "timestamp": timestamp
    }

    stored = upsert_to_cosmos(item)
    if stored:
        result["stored"] = True
        result["id"] = item["id"]
    else:
        result["stored"] = False

    return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")
