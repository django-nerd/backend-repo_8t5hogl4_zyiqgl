import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from database import create_document

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# Request model for submissions
class SubmissionIn(BaseModel):
    instagram_handle: Optional[str] = Field(None, description="Instagram username/handle, e.g. @jane")
    followers: int = Field(..., ge=0, description="Number of followers provided by the user")
    contact: Optional[str] = Field(None, description="Optional contact (email/phone)")
    note: Optional[str] = Field(None, description="Optional note")

@app.post("/api/submit")
def submit_followers(payload: SubmissionIn):
    """Accept a followers count + optional handle/contact and store it. Also triggers a notification hook if configured."""
    try:
        # Persist to DB
        from schemas import Submission as SubmissionSchema
        sub = SubmissionSchema(
            instagram_handle=payload.instagram_handle,
            followers=payload.followers,
            contact=payload.contact,
            note=payload.note,
        )
        doc_id = create_document("submission", sub)

        # Optional: send a webhook notification if NOTIFY_WEBHOOK_URL is set
        webhook = os.getenv("NOTIFY_WEBHOOK_URL")
        notify_status = "skipped"
        if webhook:
            try:
                import requests
                r = requests.post(webhook, json={
                    "event": "new_submission",
                    "id": doc_id,
                    "followers": payload.followers,
                    "instagram_handle": payload.instagram_handle,
                    "contact": payload.contact,
                    "note": payload.note,
                }, timeout=5)
                notify_status = f"sent:{r.status_code}"
            except Exception as e:
                notify_status = f"error:{str(e)[:50]}"

        return {"ok": True, "id": doc_id, "notify": notify_status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Expose schemas for the database viewer
@app.get("/schema")
def get_schema():
    from schemas import User, Product, Submission
    return {
        "user": User.model_json_schema(),
        "product": Product.model_json_schema(),
        "submission": Submission.model_json_schema(),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
