from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client
import os
from dotenv import load_dotenv
from passlib.hash import argon2
from passlib.hash import bcrypt
from datetime import date, datetime
import logging
from typing import Optional
from pydantic import BaseModel, EmailStr

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
    referral_code: Optional[str] = None


class LoginModel(BaseModel):
    email: str
    password: str


class MiningModel(BaseModel):
    email: EmailStr
    total_mined_coins: float
    mined_date: datetime


# -----------------------
# 1️⃣ Register API
# -----------------------

# @app.post("/register")
# def register_user(data: RegisterModel):
#     if supabase is None:
#         return {"status": 402, "message": "Supabase client not initialized", "user": None}
    
#     try:
#         # Hash the password using passlib
#         hashed_pw = argon2.hash(data.password)
        
#         # Insert into Supabase users table
#         response = supabase.table("Users").insert({
#             "username": data.username,
#             "email": data.email,
#             "password": hashed_pw,
#             "created_at": datetime.utcnow().isoformat()
#         }).execute()
        
#         return {
#             "status": 200,
#             "message": "User saved successfully",
#             "user": {"username": data.username, "email": data.email}
#         }
#     except Exception as e:
#         return {"status": 402, "message": str(e), "user": None}


@app.post("/register")
def register_user(data: RegisterModel):
    if supabase is None:
        return {"status": 402, "message": "Supabase client not initialized", "user": None}

    try:
        hashed_pw = argon2.hash(data.password)

        # 1️⃣ Insert new user
        response = supabase.table("Users").insert({
            "username": data.username,
            "email": data.email,
            "password": hashed_pw,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        if not response.data:
            return {"status": 400, "message": "User creation failed"}

        # 2️⃣ Give 500 coins to NEW user (insert in mining_details)
        supabase.table("mining_details").insert({
            "email": data.email,
            "total_mined_coins": 500,
            "mined_date": datetime.utcnow().isoformat()
        }).execute()

        # 3️⃣ If referral email exists
        if data.referral_code:

            ref_user = supabase.table("Users") \
                .select("email") \
                .eq("email", data.referral_code) \
                .execute()

            if ref_user.data:

                # Give 500 coins to REFERRAL user
                supabase.table("mining_details").insert({
                    "email": data.referral_code,
                    "total_mined_coins": 500,
                    "mined_date": datetime.utcnow().isoformat()
                }).execute()

        return {
            "status": 200,
            "message": "User registered successfully with referral bonus",
            "user": {"username": data.username, "email": data.email}
        }

    except Exception as e:
        return {"status": 402, "message": str(e), "user": None}
# -----------------------
# 2️⃣ Login API
# -----------------------

@app.post("/login")
def login_user(data: LoginModel):
    if supabase is None:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")

    if not data.email.strip() or not data.password.strip():
        raise HTTPException(status_code=400, detail="Email and password cannot be empty")

    try:
        # 1️⃣ Search user by email
        user_resp = supabase.table("Users") \
            .select("*") \
            .eq("email", data.email) \
            .execute()

        # ✅ Correct way to check results
        if not user_resp.data or len(user_resp.data) == 0:
            raise HTTPException(status_code=401, detail="Email not found")

        user_record = user_resp.data[0]

        # 2️⃣ Verify password
        hashed_pw = user_record.get("password")
        if not hashed_pw or not argon2.verify(data.password, hashed_pw):
            raise HTTPException(status_code=401, detail="Incorrect password")

        return {
            "status": 200,
            "message": "Login successful",
            "username": user_record.get("username"),
            "email": user_record.get("email")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
            "total_mined_coins": data.total_mined_coins,
            "mined_date": data.mined_date.isoformat()
        }).execute()

        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to insert mining data")

        return {
            "status": 200,
            "message": "Mining data saved successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------
# 4️⃣ Get Mining Details API
# -----------------------

@app.get("/get-mining/{email}")
def get_mining(email: str):
    if supabase is None:
        raise HTTPException(status_code=500, detail="Supabase client not initialized")

    try:
        response = supabase.table("mining_details") \
            .select("total_mined_coins, mined_date") \
            .eq("email", email) \
            .order("mined_date", desc=True) \
            .execute()

        if not response.data:
            return {
                "status": 404,
                "message": "No mining data found",
                "data": []
            }

        return {
            "status": 200,
            "message": "Mining data fetched successfully",
            "data": response.data
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
