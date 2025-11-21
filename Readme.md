# SentimentService – Azure Functions Project

This project is a Python-based Azure Functions application that provides sentiment-related services through HTTP-triggered endpoints and a scheduled background task.

## Features
- AddSentiment: HTTP POST endpoint to submit sentiment data.
- GetResults: HTTP GET endpoint to retrieve sentiment results.
- DailySummary: Timer-triggered function that runs based on a configurable schedule.

## Technologies Used
- Azure Functions (Python)
- Azure CLI
- Visual Studio Code
- Python 3.12

## Project Structure
SentimentService/
│
├── AddSentiment/
│ ├── init.py
│ └── function.json
│
├── GetResults/
│ ├── init.py
│ └── function.json
│
├── DailySummary/
│ ├── init.py
│ └── function.json
│
├── host.json
├── requirements.txt
├── local.settings.json.sample
└── README.md