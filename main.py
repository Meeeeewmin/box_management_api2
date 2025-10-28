from fastapi import FastAPI, HTTPException, Depends, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, DateTime, Integer, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
import openpyxl
from io import BytesIO
import re
import os
import time

# Database Configuration - 환경변수 사용
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://iot_user:iot_password@iot_box_db:3306/iot_box_db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Model
class BoxDB(Base):
    __tablename__ = "iot_boxes"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    mac_address = Column(String(17), unique=True, nullable=False, index=True)
    ip_address = Column(String(15), nullable=True)
    main_equipment = Column(String(100), nullable=True)
    location = Column(String(200), nullable=True)
    process = Column(String(100), nullable=False, index=True)
    manager = Column(String(50), nullable=True)  # 담당자 컬럼 추가
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# Pydantic Models
class BoxBase(BaseModel):
    mac_address: str = Field(..., description="MAC 주소 (필수)")
    ip_address: Optional[str] = Field(None, description="IP 주소")
    main_equipment: Optional[str] = Field(None, description="메인 설비")
    location: Optional[str] = Field(None, description="위치")
    process: str = Field(..., description="공정 (필수)")
    manager: Optional[str] = Field(None, description="담당자")  # 담당자 필드 추가
    note: Optional[str] = Field(None, description="비고")
    
    @validator('mac_address')
    def validate_mac(cls, v):
        if not v:
            raise ValueError('MAC 주소를 입력해주세요')
        pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        if not re.match(pattern, v):
            raise ValueError('올바른 MAC 주소 형식이 아닙니다 (예: AA:BB:CC:DD:EE:FF)')
        return v.upper()
    
    @validator('ip_address')
    def validate_ip(cls, v):
        if v is None:
            return v
        pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(pattern, v):
            raise ValueError('올바른 IP 주소 형식이 아닙니다 (예: 192.168.1.100)')
        return v
    
    @validator('process')
    def validate_process(cls, v):
        if v:
            return v.upper()
        return v

class BoxCreate(BoxBase):
    pass

class BoxUpdate(BaseModel):
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    main_equipment: Optional[str] = None
    location: Optional[str] = None
    process: Optional[str] = None
    manager: Optional[str] = None  # 담당자 필드 추가
    note: Optional[str] = None
    
    @validator('mac_address')
    def validate_mac(cls, v):
        if v is None:
            return v
        if not v:
            raise ValueError('MAC 주소를 입력해주세요')
        pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        if not re.match(pattern, v):
            raise ValueError('올바른 MAC 주소 형식이 아닙니다 (예: AA:BB:CC:DD:EE:FF)')
        return v.upper()
    
    @validator('process')
    def validate_process(cls, v):
        if v:
            return v.upper()
        return v

class BoxResponse(BoxBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[BoxResponse]

# FastAPI App
app = FastAPI(
    title="IoT Box Management API",
    description="IoT 박스 관리 시스템",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create tables
@app.on_event("startup")
def startup():
    max_retries = 30
    for i in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            print("Database connected successfully!")
            break
        except Exception as e:
            if i < max_retries - 1:
                print(f"Waiting for database... ({i+1}/{max_retries})")
                time.sleep(1)
            else:
                print(f"Failed to connect to database: {e}")
                raise

# API Endpoints
@app.post("/boxes", response_model=BoxResponse, status_code=201)
def create_box(box: BoxCreate, db: Session = Depends(get_db)):
    existing = db.query(BoxDB).filter(BoxDB.mac_address == box.mac_address).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 등록된 MAC 주소입니다")
    
    db_box = BoxDB(**box.dict())
    db.add(db_box)
    db.commit()
    db.refresh(db_box)
    return db_box

@app.get("/boxes", response_model=PaginatedResponse)
def get_boxes(
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(50, ge=1, le=1000, description="페이지당 항목 수"),
    search: Optional[str] = Query(None, description="검색어"),
    process: Optional[str] = Query(None, description="공정 필터"),
    db: Session = Depends(get_db)
):
    query = db.query(BoxDB)
    
    if search:
        search_filter = or_(
            BoxDB.mac_address.contains(search),
            BoxDB.ip_address.contains(search),
            BoxDB.main_equipment.contains(search),
            BoxDB.location.contains(search),
            BoxDB.process.contains(search),
            BoxDB.manager.contains(search)  # 담당자 검색 추가
        )
        query = query.filter(search_filter)
    
    if process:
        query = query.filter(BoxDB.process == process)
    
    total = query.count()
    offset = (page - 1) * page_size
    items = query.order_by(BoxDB.created_at.desc()).offset(offset).limit(page_size).all()
    total_pages = (total + page_size - 1) // page_size
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": items
    }

@app.get("/boxes/{box_id}", response_model=BoxResponse)
def get_box(box_id: int, db: Session = Depends(get_db)):
    box = db.query(BoxDB).filter(BoxDB.id == box_id).first()
    if not box:
        raise HTTPException(status_code=404, detail="박스를 찾을 수 없습니다")
    return box

@app.put("/boxes/{box_id}", response_model=BoxResponse)
def update_box(box_id: int, box_update: BoxUpdate, db: Session = Depends(get_db)):
    db_box = db.query(BoxDB).filter(BoxDB.id == box_id).first()
    if not db_box:
        raise HTTPException(status_code=404, detail="박스를 찾을 수 없습니다")
    
    if box_update.mac_address and box_update.mac_address != db_box.mac_address:
        existing = db.query(BoxDB).filter(BoxDB.mac_address == box_update.mac_address).first()
        if existing:
            raise HTTPException(status_code=400, detail="이미 등록된 MAC 주소입니다")
    
    update_data = box_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_box, key, value)
    
    db_box.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_box)
    return db_box

@app.delete("/boxes/{box_id}", status_code=204)
def delete_box(box_id: int, db: Session = Depends(get_db)):
    db_box = db.query(BoxDB).filter(BoxDB.id == box_id).first()
    if not db_box:
        raise HTTPException(status_code=404, detail="박스를 찾을 수 없습니다")
    
    db.delete(db_box)
    db.commit()
    return None

@app.get("/boxes/export/excel")
def export_to_excel(
    search: Optional[str] = Query(None),
    process: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(BoxDB)
    
    if search:
        search_filter = or_(
            BoxDB.mac_address.contains(search),
            BoxDB.ip_address.contains(search),
            BoxDB.main_equipment.contains(search),
            BoxDB.location.contains(search),
            BoxDB.process.contains(search),
            BoxDB.manager.contains(search)  # 담당자 검색 추가
        )
        query = query.filter(search_filter)
    
    if process:
        query = query.filter(BoxDB.process == process)
    
    boxes = query.order_by(BoxDB.created_at.desc()).all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "IoT Boxes"
    
    headers = ["ID", "MAC 주소", "IP 주소", "메인 설비", "위치", "공정", "담당자", "비고", "등록일", "수정일"]
    ws.append(headers)
    
    for box in boxes:
        ws.append([
            box.id,
            box.mac_address,
            box.ip_address or "",
            box.main_equipment or "",
            box.location or "",
            box.process,
            box.manager or "",
            box.note or "",
            box.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            box.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        ])
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"iot_boxes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/processes")
def get_processes(db: Session = Depends(get_db)):
    processes = db.query(BoxDB.process).distinct().all()
    # 대소문자 구분 없이 중복 제거
    seen = set()
    unique_processes = []
    for p in processes:
        if p[0]:
            upper_process = p[0].upper()
            if upper_process not in seen:
                seen.add(upper_process)
                unique_processes.append(upper_process)
    return sorted(unique_processes)

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/admin/normalize-processes")
def normalize_processes(db: Session = Depends(get_db)):
    """기존 공정명을 모두 대문자로 변환 (관리자용)"""
    boxes = db.query(BoxDB).all()
    updated_count = 0
    for box in boxes:
        if box.process:
            new_process = box.process.upper()
            if box.process != new_process:
                box.process = new_process
                box.updated_at = datetime.utcnow()
                updated_count += 1
    
    db.commit()
    return {
        "status": "success",
        "message": f"{updated_count}개의 공정명이 대문자로 변환되었습니다"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
