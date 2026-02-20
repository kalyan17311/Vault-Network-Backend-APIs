from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client
import os
from dotenv import load_dotenv
from passlib.hash import bcrypt
from datetime import date
import logging
from typing import Optional

load_dotenv()

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize lazily at startup to avoid import-time crashes when env is missing
supabase: Optional[object] = None


@app.on_event("startup")
async def startup():
    global supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        logging.warning("SUPABASE_URL or SUPABASE_KEY not set; Supabase client won't be initialized.")
        return
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logging.info("Supabase client initialized")
    except Exception:
        logging.exception("Failed to initialize Supabase client")
        supabase = None


@app.get("/health")
def health():
    return {"status": "ok", "supabase_initialized": supabase is not None}


# -----------------------
# Request Models
# -----------------------

class RegisterModel(BaseModel):
    username: str
    email: str
    password: str


class LoginModel(BaseModel):
    email: str
    password: str


class MiningModel(BaseModel):
    email: str
    mine_clicked: bool
    total_mined_coins: int
    mined_date: date


# -----------------------
# 1️⃣ Register API
# -----------------------

@app.post("/register")
def register_user(data: RegisterModel):
    if supabase is None:
        return {"status": 402, "message": "Supabase client not initialized", "user": None}
    try:
        response = supabase.auth.sign_up({
            "email": data.email,
            "password": data.password,
            "options": {"data": {"username": data.username}}
        })
        user = getattr(response, "user", None)
        return {"status": 200, "message": "User registered successfully", "user": user}
    except Exception as e:
        # Always return JSON even on server error
        return {"status": 402, "message": str(e), "user": None}

# -----------------------
# 2️⃣ Login API
# -----------------------

@app.post("/login")
def login_user(data: LoginModel):
    if supabase is None:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        response = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })

        access_token = None
        if getattr(response, "session", None):
            access_token = getattr(response.session, "access_token", None)

        return {
            "message": "Login successful",
            "access_token": access_token
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------
# 3️⃣ Save Mining Details API
# -----------------------

@app.post("/save-mining")
def save_mining(data: MiningModel):
    if supabase is None:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")
    try:
        response = supabase.table("mining_details").insert({
            "email": data.email,
            "mine_clicked": data.mine_clicked,
            "total_mined_coins": data.total_mined_coins,
            "mined_date": data.mined_date.isoformat()
        }).execute()

        return {"message": "Mining data saved successfully"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------
# 4️⃣ Get Mining Details API
# -----------------------

@app.get("/get-mining/{email}")
def get_mining(email: str):
    try:
        response = supabase.table("mining_details") \
            .select("*") \
            .eq("email", email) \
            .execute()
        return getattr(response, "data", [])

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
