from fastapi import FastAPI
from fastapi import HTTPException
# from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import hashlib
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

# Initialize FastAPI app
app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://medchain-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize Firebase Admin
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Define medicine model
class Medicine(BaseModel):
    name: str
    batch: str
    expiry: str


@app.post("/register")
def register_medicine(med: Medicine):
    # Create hash
    med_data = med.dict()
    med_json = json.dumps(med_data, sort_keys=True)
    hash_val = hashlib.sha256(med_json.encode()).hexdigest()

    # Add tracking and status fields
    ledger_entry = {
        "medicine": med_data,
        "hash": hash_val,
        "tracking": [
            {
                "location": "Manufacturer",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        ],
        "eta": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
        "status": "In Transit"
    }

    # Store in Firestore
    doc_ref = db.collection("ledger").document()
    doc_ref.set(ledger_entry)

    return {"message": "Medicine registered", "data": ledger_entry}


@app.get("/ledger")
def get_ledger():
    docs = db.collection("ledger").stream()
    ledger = []
    for doc in docs:
        ledger.append(doc.to_dict())
    return ledger


from sklearn.linear_model import LinearRegression
import numpy as np

@app.post("/predict")
def predict_stock(stock_history: List[int]):
    try:
        if len(stock_history) < 3:
            return {"error": "Need at least 3 days of stock data"}

        # Debug log
        print("📦 Received stock history:", stock_history)

        # Prepare data
        X = np.array([[i] for i in range(len(stock_history))])
        y = np.array(stock_history)

        model = LinearRegression()
        model.fit(X, y)

        # Predict next day
        next_day = len(stock_history)
        predicted = model.predict([[next_day]])[0]
        alert = predicted < 20

        return {
            "predicted_stock": round(predicted),
            "alert": bool(alert),
            "message": "Low stock alert" if alert else "Stock level is fine"
        }

    except Exception as e:
        print("❌ Prediction error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/seed")
def seed_medicines():
    sample_meds = [
        {"name": "Paracetamol 500mg", "batch": "BATCH-A1", "expiry": "2026-01-01"},
        {"name": "Amoxicillin 250mg", "batch": "BATCH-B2", "expiry": "2025-08-15"},
        {"name": "Metformin 500mg", "batch": "BATCH-C3", "expiry": "2027-11-30"},
        {"name": "Azithromycin 250mg", "batch": "BATCH-D4", "expiry": "2024-12-10"},
        {"name": "Ciprofloxacin 500mg", "batch": "BATCH-E5", "expiry": "2025-03-01"},
        {"name": "Ibuprofen 400mg", "batch": "BATCH-F6", "expiry": "2026-05-20"},
        {"name": "Dolo 650mg", "batch": "BATCH-G7", "expiry": "2025-09-05"},
        {"name": "Cetirizine 10mg", "batch": "BATCH-H8", "expiry": "2026-10-12"},
        {"name": "Vitamin C 1000mg", "batch": "BATCH-I9", "expiry": "2027-07-18"},
        {"name": "Rabeprazole 20mg", "batch": "BATCH-J10", "expiry": "2025-02-28"}
    ]

    for med in sample_meds:
        med_json = json.dumps(med, sort_keys=True)
        hash_val = hashlib.sha256(med_json.encode()).hexdigest()
        db.collection("ledger").add({
            "medicine": med,
            "hash": hash_val
        })

    return {"message": "Sample medicines seeded"}

from fastapi import Body

@app.post("/update-location")
def update_location(batch: str = Body(...), location: str = Body(...)):
    docs = db.collection("ledger").stream()
    for doc in docs:
        data = doc.to_dict()
        if data["medicine"]["batch"] == batch:
            tracking_list = data.get("tracking", [])
            tracking_list.append({
                "location": location,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
            })

            status = f"In Transit at {location}"
            doc.reference.update({
                "tracking": tracking_list,
                "status": status
            })
            return {"message": "Tracking updated", "new_tracking": tracking_list}
    return {"error": "Batch not found"}
