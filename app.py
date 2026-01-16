import uvicorn
import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel

# Import your Model Logic
# Ensure 'train_model_final.py' is in the same folder!
from train_model_final import model

# --- DATABASE SETUP (Updated for Cloud & Local) ---
# 1. Get the URL from the cloud environment, or use local SQLite as a backup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./anganwadi.db")

# 2. Fix a small formatting issue (Render uses 'postgres://' but Python needs 'postgresql://')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. SQLite needs specific args, PostgreSQL does not.
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- DATABASE TABLES ---
class HealthWorker(Base):
    __tablename__ = "workers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    aadhar_number = Column(String, unique=True, index=True)
    anganwadi_code = Column(String, index=True)
    password = Column(String)

class ChildRecord(Base):
    __tablename__ = "children"
    id = Column(Integer, primary_key=True, index=True)
    anganwadi_code = Column(String, index=True)
    name = Column(String)
    age_years = Column(Float)
    sex = Column(String)
    height = Column(Float)
    weight = Column(Float)
    status = Column(String)
    z_score = Column(Float)
    color_code = Column(String)

# Create tables automatically (Safe to run every time)
Base.metadata.create_all(bind=engine)

# --- VALIDATION MODELS ---
class WorkerSignupSchema(BaseModel):
    name: str
    aadhar_number: str
    anganwadi_code: str
    password: str 

class WorkerLoginSchema(BaseModel):
    aadhar_number: str
    anganwadi_code: str
    password: str

class ChildAssessmentSchema(BaseModel):
    anganwadi_code: str
    child_name: str
    age_years: float
    sex: str
    height_cm: float
    weight_kg: float
    edema: bool = False

# --- APP SETUP ---
app = FastAPI(title="Anganwadi Smart Assistant")

# CORS: Allow mobile apps from anywhere to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- API ENDPOINTS ---

@app.post("/signup", status_code=status.HTTP_201_CREATED)
def register_worker(worker: WorkerSignupSchema, db: Session = Depends(get_db)):
    # Check if worker already exists
    existing_worker = db.query(HealthWorker).filter(
        HealthWorker.aadhar_number == worker.aadhar_number
    ).first()

    if existing_worker:
        raise HTTPException(status_code=400, detail="Worker already registered.")

    new_worker = HealthWorker(
        name=worker.name,
        aadhar_number=worker.aadhar_number,
        anganwadi_code=worker.anganwadi_code,
        password=worker.password
    )
    db.add(new_worker)
    db.commit()
    return {"message": "Registration Successful", "name": worker.name}

@app.post("/login")
def login_worker(creds: WorkerLoginSchema, db: Session = Depends(get_db)):
    worker = db.query(HealthWorker).filter(
        HealthWorker.aadhar_number == creds.aadhar_number,
        HealthWorker.anganwadi_code == creds.anganwadi_code,
        HealthWorker.password == creds.password
    ).first()

    if not worker:
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    return {
        "status": "success",
        "worker_name": worker.name,
        "anganwadi_code": worker.anganwadi_code
    }

@app.post("/assess")
def assess_child(data: ChildAssessmentSchema, db: Session = Depends(get_db)):
    # 1. PREDICT using the Logic in train_model_final.py
    result = model.predict(
        weight_kg=data.weight_kg,
        height_cm=data.height_cm,
        age_years=data.age_years,
        sex=data.sex,
        edema=data.edema
    )

    if result["status"] == "Error":
        raise HTTPException(status_code=400, detail="Invalid Data")

    # 2. SAVE to Database
    new_child = ChildRecord(
        anganwadi_code=data.anganwadi_code,
        name=data.child_name,
        age_years=data.age_years,
        sex=data.sex,
        height=data.height_cm,
        weight=data.weight_kg,
        status=result["status"],
        z_score=result["z_score"],
        color_code=result["color_code"]
    )
    db.add(new_child)
    db.commit()

    return {
        "child_name": data.child_name,
        "diagnosis": result
    }

@app.get("/stats/{anganwadi_code}")
def get_dashboard_stats(anganwadi_code: str, db: Session = Depends(get_db)):
    # 1. Local Stats (Grouped by Status for THIS Anganwadi)
    local_counts = db.query(ChildRecord.status, func.count(ChildRecord.id)).filter(
        ChildRecord.anganwadi_code == anganwadi_code
    ).group_by(ChildRecord.status).all()
    
    local_stats = {status: count for status, count in local_counts}
    total_local = sum(local_stats.values())

    # 2. Global Stats (Total children in the ENTIRE system)
    total_global = db.query(func.count(ChildRecord.id)).scalar()

    return {
        "anganwadi_code": anganwadi_code,
        "local_stats": local_stats,
        "total_checked_here": total_local,
        "total_checked_global": total_global
    }

if __name__ == "__main__":
    # Localhost start command
    uvicorn.run(app, host="0.0.0.0", port=8000)
