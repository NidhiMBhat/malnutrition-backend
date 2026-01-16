import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel

# Import your ML logic
# Ensure 'train_model_final.py' is in the backend folder and you have run it once!
from train_model_final import model

# --- DATABASE SETUP ---
DATABASE_URL = "sqlite:///./anganwadi.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all connections (Crucial for mobile)
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- API ENDPOINTS ---

@app.post("/signup", status_code=status.HTTP_201_CREATED)
def register_worker(worker: WorkerSignupSchema, db: Session = Depends(get_db)):
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
    # 1. Predict
    result = model.predict(
        weight_kg=data.weight_kg,
        height_cm=data.height_cm,
        age_years=data.age_years,
        sex=data.sex,
        edema=data.edema
    )

    if result["status"] == "Error":
        raise HTTPException(status_code=400, detail="Invalid Data")

    # 2. Save
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
    # 1. Local Stats (This Center)
    local_counts = db.query(ChildRecord.status, func.count(ChildRecord.id)).filter(
        ChildRecord.anganwadi_code == anganwadi_code
    ).group_by(ChildRecord.status).all()
    
    local_stats = {status: count for status, count in local_counts}
    total_local = sum(local_stats.values())

    # 2. Global Stats (All Centers)
    total_global = db.query(func.count(ChildRecord.id)).scalar()

    return {
        "anganwadi_code": anganwadi_code,
        "local_stats": local_stats,
        "total_checked_here": total_local,
        "total_checked_global": total_global
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)