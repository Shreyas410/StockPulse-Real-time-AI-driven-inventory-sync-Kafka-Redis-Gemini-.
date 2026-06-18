import json
import os
from pathlib import Path

import google.generativeai as genai
import requests
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="MCP Server",
    description="Model Control Plane: Converts natural language to inventory API calls using Gemini",
    version="1.0.0"
)

# GEMINI LLM is used to convert natural language queries into structured inventory API calls

INVENTORY_API_URL = os.environ.get("INVENTORY_API_URL", "http://127.0.0.1:8000")

# Load Gemini API key from environment or an ignored `secrets.json` file.
# Create `secrets.json` (not checked into git) with: {"GOOGLE_API_KEY": "your_key_here"}
secrets_path = Path(__file__).parent / "secrets.json"
if not os.environ.get("GOOGLE_API_KEY") and secrets_path.exists():
    try:
        with open(secrets_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "GOOGLE_API_KEY" in data:
                os.environ["GOOGLE_API_KEY"] = data["GOOGLE_API_KEY"]
    except Exception as e:
        print("Failed to load secrets.json:", e)

GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("Warning: GOOGLE_API_KEY not set. MCP Server will not call Gemini.")

class QueryRequest(BaseModel):
    query: str

@app.post("/query")
async def handle_query(request: QueryRequest):
    
    user_query = request.query

    # Prompt for gemini to convert natural language into Json
    prompt = (
        "You are an assistant for an inventory system. "
        "Convert the following user request into a JSON array for /inventory. "
        "Each object in the array should be like: {\"item\": \"tshirts\", \"change\": -3} or {\"item\": \"pants\", \"change\": 5}. "
        "If there are multiple actions, include multiple objects in the array. "
        "Reply ONLY with the JSON array, no explanation, no text, no markdown. "
        f"User: {user_query}"
    )

    model = genai.GenerativeModel("models/gemini-2.0-flash")
    response = model.generate_content(prompt)

   
    try:

        text = response.text.strip()
      
      
        if text.startswith("```"):
            text = text.split("```")[1].strip()
    
        json_start = text.find("[")
        json_end = text.rfind("]") + 1
        if json_start != -1 and json_end != -1:
            text = text[json_start:json_end]
        payload = json.loads(text)


        # Ensure payload is a list
        if isinstance(payload, dict):
            payload = [payload]
    except Exception as e:
        print("Gemini raw output:", response.text)  # Debug {output of gemini}
        return {"error": "Could not parse Gemini response", "details": str(e), "raw_response": response.text}

  
    results = []
    for act in payload:
        resp = requests.post(f"{INVENTORY_API_URL}/inventory", json=act)
        try:
            results.append(resp.json())
        except Exception:
            results.append({"error": "Inventory service error", "status_code": resp.status_code})

    # Optionally, return the final inventory state
    final_inventory = requests.get(f"{INVENTORY_API_URL}/inventory").json()
    return {
        "actions": payload,
        "results": results,
        "final_inventory": final_inventory,
        "gemini_raw": response.text  # For debugging it shows gemini response.
    }
# for CORS support, allowing requests from any origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
#  Run on port 8001.
if __name__ == "__main__":
  
    uvicorn.run("mcp_server:app", host="127.0.0.1", port=8001, reload=True)