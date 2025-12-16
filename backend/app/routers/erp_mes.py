"""
ERP/MES Mock API Router

문서 참조:
- A-2-4 DATA-REQ-020: JSONB 기반 확장 가능한 메타데이터 저장
- A-2-4 INT-REQ-010: ERP/MES 연동 (REST API, SOAP, DB Direct)
- B-1-3: Native DB Connector Integration

MVP에서는 Mock 데이터 생성기를 제공하며,
실제 ERP/MES 연동은 V2에서 구현 예정
"""

import csv
import io
import random
from datetime import datetime, timedelta
from typing import Optional, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import ErpMesData, FieldMapping, DataSource
from app.models import User
from app.auth.dependencies import get_current_user

router = APIRouter()


# ========== Pydantic Schemas ==========


class ErpMesDataCreate(BaseModel):
    """ERP/MES 데이터 생성 스키마"""
    source_type: Literal["erp", "mes"]
    source_system: str = Field(..., min_length=1, max_length=100)
    record_type: str = Field(..., min_length=1, max_length=100)
    external_id: Optional[str] = None
    raw_data: dict = Field(default_factory=dict)
    normalized_quantity: Optional[float] = None
    normalized_status: Optional[str] = None
    normalized_timestamp: Optional[datetime] = None


class ErpMesDataResponse(BaseModel):
    """ERP/MES 데이터 응답 스키마"""
    data_id: UUID
    tenant_id: UUID
    source_type: str
    source_system: str
    record_type: str
    external_id: Optional[str]
    raw_data: dict
    normalized_quantity: Optional[float]
    normalized_status: Optional[str]
    normalized_timestamp: Optional[datetime]
    sync_status: str
    synced_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class FieldMappingCreate(BaseModel):
    """필드 매핑 생성 스키마"""
    source_type: Literal["erp", "mes"]
    source_system: str
    record_type: str
    source_field: str
    target_field: str
    transform_type: Optional[str] = None
    transform_config: dict = Field(default_factory=dict)


class FieldMappingResponse(BaseModel):
    """필드 매핑 응답 스키마"""
    mapping_id: UUID
    tenant_id: UUID
    source_type: str
    source_system: str
    record_type: str
    source_field: str
    target_field: str
    transform_type: Optional[str]
    transform_config: dict
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DataSourceCreate(BaseModel):
    """데이터 소스 생성 스키마"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_type: Literal["erp", "mes"]
    source_system: str
    connection_type: Literal["rest_api", "soap", "db_direct", "file"]
    connection_config: dict = Field(default_factory=dict)
    sync_enabled: bool = True
    sync_interval_minutes: int = 60


class DataSourceResponse(BaseModel):
    """데이터 소스 응답 스키마"""
    source_id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str]
    source_type: str
    source_system: str
    connection_type: str
    sync_enabled: bool
    sync_interval_minutes: int
    last_sync_at: Optional[datetime]
    last_sync_status: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MockDataGenerateRequest(BaseModel):
    """Mock 데이터 생성 요청"""
    source_type: Literal["erp", "mes"]
    source_system: str = "mock_system"
    record_type: str
    count: int = Field(default=10, ge=1, le=100)


class MockDataGenerateResponse(BaseModel):
    """Mock 데이터 생성 응답"""
    generated_count: int
    source_type: str
    source_system: str
    record_type: str
    sample_data: list[dict]


# ========== Mock Data Generators ==========


def generate_erp_production_order() -> dict:
    """SAP 스타일 생산 오더 Mock 데이터"""
    order_id = f"PO{random.randint(100000, 999999)}"
    return {
        "AUFNR": order_id,  # Production Order Number (SAP style)
        "MATNR": f"MAT{random.randint(1000, 9999)}",  # Material Number
        "WERKS": random.choice(["1000", "2000", "3000"]),  # Plant
        "GAMNG": random.uniform(100, 10000),  # Target Quantity (MENGE 대신)
        "MEINS": random.choice(["EA", "KG", "L", "M"]),  # Unit of Measure
        "GSTRP": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),  # Start Date
        "GLTRP": (datetime.now() + timedelta(days=random.randint(1, 60))).isoformat(),  # End Date
        "STATUS": random.choice(["REL", "CNF", "TECO", "CRTD"]),  # Status
        "PRIO": random.choice(["1", "2", "3"]),  # Priority
        "ARBPL": f"WC{random.randint(100, 999)}",  # Work Center
        "LGORT": f"SL{random.randint(10, 99)}",  # Storage Location
        "KOSTL": f"CC{random.randint(1000, 9999)}",  # Cost Center
    }


def generate_erp_inventory() -> dict:
    """Oracle 스타일 재고 Mock 데이터"""
    return {
        "INVENTORY_ITEM_ID": random.randint(10000, 99999),
        "ORGANIZATION_ID": random.randint(100, 999),
        "SUBINVENTORY_CODE": random.choice(["FG", "RAW", "WIP", "QC"]),
        "ITEM_NUMBER": f"ITEM-{random.randint(1000, 9999)}",
        "DESCRIPTION": f"Sample Material {random.randint(1, 100)}",
        "ON_HAND_QTY": random.uniform(0, 5000),
        "RESERVED_QTY": random.uniform(0, 1000),
        "AVAILABLE_QTY": random.uniform(0, 4000),
        "UOM_CODE": random.choice(["EA", "KG", "L", "M"]),
        "LOCATOR_ID": random.randint(1, 50),
        "LOT_NUMBER": f"LOT{datetime.now().strftime('%Y%m')}{random.randint(100, 999)}",
        "EXPIRATION_DATE": (datetime.now() + timedelta(days=random.randint(30, 365))).isoformat(),
        "LAST_UPDATE_DATE": datetime.now().isoformat(),
    }


def generate_erp_bom() -> dict:
    """BOM (Bill of Materials) Mock 데이터"""
    return {
        "BOM_ID": f"BOM{random.randint(10000, 99999)}",
        "PARENT_ITEM": f"FG-{random.randint(1000, 9999)}",
        "PARENT_DESC": f"Finished Good {random.randint(1, 50)}",
        "COMPONENT_ITEM": f"COMP-{random.randint(1000, 9999)}",
        "COMPONENT_DESC": f"Component Material {random.randint(1, 100)}",
        "COMPONENT_QTY": random.uniform(1, 100),
        "UOM": random.choice(["EA", "KG", "L", "M"]),
        "OPERATION_SEQ": random.choice([10, 20, 30, 40, 50]),
        "EFFECTIVE_DATE": (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat(),
        "DISABLE_DATE": None,
        "BOM_LEVEL": random.randint(1, 5),
    }


def generate_mes_work_order() -> dict:
    """MES 작업 지시서 Mock 데이터"""
    order_id = f"WO{datetime.now().strftime('%Y%m%d')}{random.randint(100, 999)}"
    return {
        "work_order_id": order_id,
        "production_line": random.choice(["LINE-A", "LINE-B", "LINE-C", "LINE-D"]),
        "product_code": f"PROD-{random.randint(1000, 9999)}",
        "product_name": f"Product Type {random.choice(['Alpha', 'Beta', 'Gamma', 'Delta'])}",
        "planned_quantity": random.randint(100, 1000),
        "produced_quantity": random.randint(0, 800),
        "defect_quantity": random.randint(0, 50),
        "status": random.choice(["scheduled", "in_progress", "completed", "on_hold", "cancelled"]),
        "priority": random.choice(["high", "medium", "low"]),
        "scheduled_start": (datetime.now() - timedelta(hours=random.randint(0, 48))).isoformat(),
        "scheduled_end": (datetime.now() + timedelta(hours=random.randint(1, 24))).isoformat(),
        "actual_start": (datetime.now() - timedelta(hours=random.randint(0, 24))).isoformat() if random.random() > 0.3 else None,
        "actual_end": None,
        "operator_id": f"OP{random.randint(100, 999)}",
        "shift": random.choice(["day", "evening", "night"]),
        "machine_id": f"MC{random.randint(100, 999)}",
    }


def generate_mes_equipment_status() -> dict:
    """MES 설비 상태 Mock 데이터"""
    return {
        "equipment_id": f"EQ{random.randint(1000, 9999)}",
        "equipment_name": f"Machine {random.choice(['CNC', 'Press', 'Welding', 'Assembly'])} {random.randint(1, 10)}",
        "equipment_type": random.choice(["cnc", "press", "welding", "assembly", "inspection", "packaging"]),
        "location": f"Area-{random.choice(['A', 'B', 'C', 'D'])}-{random.randint(1, 20)}",
        "status": random.choice(["running", "idle", "maintenance", "breakdown", "setup"]),
        "current_oee": round(random.uniform(60, 95), 2),
        "availability": round(random.uniform(80, 100), 2),
        "performance": round(random.uniform(70, 100), 2),
        "quality": round(random.uniform(90, 100), 2),
        "current_cycle_time": round(random.uniform(10, 120), 2),  # seconds
        "target_cycle_time": round(random.uniform(10, 100), 2),
        "last_maintenance": (datetime.now() - timedelta(days=random.randint(1, 90))).isoformat(),
        "next_maintenance": (datetime.now() + timedelta(days=random.randint(1, 30))).isoformat(),
        "temperature": round(random.uniform(20, 80), 1) if random.random() > 0.3 else None,
        "vibration": round(random.uniform(0, 10), 2) if random.random() > 0.3 else None,
        "power_consumption": round(random.uniform(10, 500), 1),
        "last_update": datetime.now().isoformat(),
    }


def generate_mes_quality_record() -> dict:
    """MES 품질 검사 기록 Mock 데이터"""
    return {
        "inspection_id": f"QC{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}",
        "work_order_id": f"WO{datetime.now().strftime('%Y%m%d')}{random.randint(100, 999)}",
        "product_code": f"PROD-{random.randint(1000, 9999)}",
        "lot_number": f"LOT{datetime.now().strftime('%Y%m')}{random.randint(100, 999)}",
        "inspection_type": random.choice(["incoming", "in_process", "final", "sampling"]),
        "inspector_id": f"QI{random.randint(100, 999)}",
        "sample_size": random.randint(5, 100),
        "passed_count": random.randint(0, 100),
        "failed_count": random.randint(0, 10),
        "defect_types": random.sample(
            ["scratch", "dimension", "color", "crack", "contamination", "functional"],
            k=random.randint(0, 3)
        ),
        "result": random.choice(["pass", "fail", "conditional"]),
        "inspection_date": datetime.now().isoformat(),
        "measurements": {
            "dimension_a": round(random.uniform(99.5, 100.5), 3),
            "dimension_b": round(random.uniform(49.8, 50.2), 3),
            "weight": round(random.uniform(0.95, 1.05), 4),
        },
        "notes": random.choice([None, "Minor deviation within tolerance", "Requires supervisor review"]),
    }


# Mock 데이터 생성기 매핑
MOCK_GENERATORS = {
    "erp": {
        "production_order": generate_erp_production_order,
        "inventory": generate_erp_inventory,
        "bom": generate_erp_bom,
    },
    "mes": {
        "work_order": generate_mes_work_order,
        "equipment_status": generate_mes_equipment_status,
        "quality_record": generate_mes_quality_record,
    },
}


def normalize_data(raw_data: dict, record_type: str) -> tuple[Optional[float], Optional[str], Optional[datetime]]:
    """원본 데이터에서 정규화된 공통 필드 추출"""
    quantity = None
    status = None
    timestamp = None

    # ERP Production Order
    if "GAMNG" in raw_data:
        quantity = raw_data.get("GAMNG")
        status = raw_data.get("STATUS")
        if raw_data.get("GSTRP"):
            try:
                timestamp = datetime.fromisoformat(raw_data["GSTRP"])
            except:
                pass

    # ERP Inventory
    elif "ON_HAND_QTY" in raw_data:
        quantity = raw_data.get("ON_HAND_QTY")
        if raw_data.get("LAST_UPDATE_DATE"):
            try:
                timestamp = datetime.fromisoformat(raw_data["LAST_UPDATE_DATE"])
            except:
                pass

    # MES Work Order
    elif "planned_quantity" in raw_data:
        quantity = raw_data.get("planned_quantity")
        status = raw_data.get("status")
        if raw_data.get("scheduled_start"):
            try:
                timestamp = datetime.fromisoformat(raw_data["scheduled_start"])
            except:
                pass

    # MES Equipment Status
    elif "current_oee" in raw_data:
        quantity = raw_data.get("current_oee")
        status = raw_data.get("status")
        if raw_data.get("last_update"):
            try:
                timestamp = datetime.fromisoformat(raw_data["last_update"])
            except:
                pass

    # MES Quality Record
    elif "sample_size" in raw_data:
        quantity = raw_data.get("sample_size")
        status = raw_data.get("result")
        if raw_data.get("inspection_date"):
            try:
                timestamp = datetime.fromisoformat(raw_data["inspection_date"])
            except:
                pass

    return quantity, status, timestamp


# ========== API Endpoints ==========


@router.get("/data", response_model=list[ErpMesDataResponse])
async def list_erp_mes_data(
    source_type: Optional[str] = Query(None, description="erp 또는 mes"),
    source_system: Optional[str] = Query(None, description="소스 시스템 (sap, oracle, etc.)"),
    record_type: Optional[str] = Query(None, description="레코드 유형"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ERP/MES 데이터 목록 조회"""
    query = db.query(ErpMesData).filter(ErpMesData.tenant_id == current_user.tenant_id)

    if source_type:
        query = query.filter(ErpMesData.source_type == source_type)
    if source_system:
        query = query.filter(ErpMesData.source_system == source_system)
    if record_type:
        query = query.filter(ErpMesData.record_type == record_type)

    return query.order_by(ErpMesData.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/data", response_model=ErpMesDataResponse)
async def create_erp_mes_data(
    data: ErpMesDataCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ERP/MES 데이터 생성 (수동 입력 또는 외부 연동)"""
    db_data = ErpMesData(
        tenant_id=current_user.tenant_id,
        source_type=data.source_type,
        source_system=data.source_system,
        record_type=data.record_type,
        external_id=data.external_id,
        raw_data=data.raw_data,
        normalized_quantity=data.normalized_quantity,
        normalized_status=data.normalized_status,
        normalized_timestamp=data.normalized_timestamp,
    )
    db.add(db_data)
    db.commit()
    db.refresh(db_data)
    return db_data


@router.get("/data/{data_id}", response_model=ErpMesDataResponse)
async def get_erp_mes_data(
    data_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ERP/MES 데이터 상세 조회"""
    data = db.query(ErpMesData).filter(
        ErpMesData.data_id == data_id,
        ErpMesData.tenant_id == current_user.tenant_id
    ).first()

    if not data:
        raise HTTPException(status_code=404, detail="Data not found")
    return data


@router.delete("/data/{data_id}")
async def delete_erp_mes_data(
    data_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ERP/MES 데이터 삭제"""
    data = db.query(ErpMesData).filter(
        ErpMesData.data_id == data_id,
        ErpMesData.tenant_id == current_user.tenant_id
    ).first()

    if not data:
        raise HTTPException(status_code=404, detail="Data not found")

    db.delete(data)
    db.commit()
    return {"message": "Data deleted successfully"}


# ========== Mock Data Generation ==========


@router.post("/mock/generate", response_model=MockDataGenerateResponse)
async def generate_mock_data(
    request: MockDataGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mock ERP/MES 데이터 생성

    MVP 단계에서 테스트용 데이터 생성
    지원하는 record_type:
    - ERP: production_order, inventory, bom
    - MES: work_order, equipment_status, quality_record
    """
    generators = MOCK_GENERATORS.get(request.source_type, {})
    generator = generators.get(request.record_type)

    if not generator:
        available = list(generators.keys()) if generators else []
        raise HTTPException(
            status_code=400,
            detail=f"Unknown record_type '{request.record_type}' for source_type '{request.source_type}'. "
                   f"Available: {available}"
        )

    generated = []
    sample_data = []

    for i in range(request.count):
        raw_data = generator()
        quantity, status, timestamp = normalize_data(raw_data, request.record_type)

        db_data = ErpMesData(
            tenant_id=current_user.tenant_id,
            source_type=request.source_type,
            source_system=request.source_system,
            record_type=request.record_type,
            external_id=raw_data.get("AUFNR") or raw_data.get("work_order_id") or raw_data.get("equipment_id") or str(uuid4())[:8],
            raw_data=raw_data,
            normalized_quantity=quantity,
            normalized_status=status,
            normalized_timestamp=timestamp,
        )
        db.add(db_data)
        generated.append(db_data)

        if i < 3:  # 샘플 데이터는 최대 3개만
            sample_data.append(raw_data)

    db.commit()

    return MockDataGenerateResponse(
        generated_count=len(generated),
        source_type=request.source_type,
        source_system=request.source_system,
        record_type=request.record_type,
        sample_data=sample_data,
    )


@router.get("/mock/types")
async def get_available_mock_types():
    """사용 가능한 Mock 데이터 타입 조회"""
    return {
        "erp": {
            "record_types": list(MOCK_GENERATORS.get("erp", {}).keys()),
            "description": "ERP (Enterprise Resource Planning) 데이터",
            "examples": ["production_order (생산 오더)", "inventory (재고)", "bom (자재명세서)"],
        },
        "mes": {
            "record_types": list(MOCK_GENERATORS.get("mes", {}).keys()),
            "description": "MES (Manufacturing Execution System) 데이터",
            "examples": ["work_order (작업지시)", "equipment_status (설비상태)", "quality_record (품질검사)"],
        },
    }


# ========== Field Mappings ==========


@router.get("/mappings", response_model=list[FieldMappingResponse])
async def list_field_mappings(
    source_type: Optional[str] = None,
    source_system: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """필드 매핑 목록 조회"""
    query = db.query(FieldMapping).filter(FieldMapping.tenant_id == current_user.tenant_id)

    if source_type:
        query = query.filter(FieldMapping.source_type == source_type)
    if source_system:
        query = query.filter(FieldMapping.source_system == source_system)

    return query.order_by(FieldMapping.created_at.desc()).all()


@router.post("/mappings", response_model=FieldMappingResponse)
async def create_field_mapping(
    mapping: FieldMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """필드 매핑 생성"""
    db_mapping = FieldMapping(
        tenant_id=current_user.tenant_id,
        source_type=mapping.source_type,
        source_system=mapping.source_system,
        record_type=mapping.record_type,
        source_field=mapping.source_field,
        target_field=mapping.target_field,
        transform_type=mapping.transform_type,
        transform_config=mapping.transform_config,
    )
    db.add(db_mapping)
    db.commit()
    db.refresh(db_mapping)
    return db_mapping


@router.delete("/mappings/{mapping_id}")
async def delete_field_mapping(
    mapping_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """필드 매핑 삭제"""
    mapping = db.query(FieldMapping).filter(
        FieldMapping.mapping_id == mapping_id,
        FieldMapping.tenant_id == current_user.tenant_id
    ).first()

    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    db.delete(mapping)
    db.commit()
    return {"message": "Mapping deleted successfully"}


# ========== Data Sources ==========


@router.get("/sources", response_model=list[DataSourceResponse])
async def list_data_sources(
    source_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """데이터 소스 목록 조회"""
    query = db.query(DataSource).filter(DataSource.tenant_id == current_user.tenant_id)

    if source_type:
        query = query.filter(DataSource.source_type == source_type)

    return query.order_by(DataSource.created_at.desc()).all()


@router.post("/sources", response_model=DataSourceResponse)
async def create_data_source(
    source: DataSourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """데이터 소스 생성"""
    # 연결 설정에서 민감한 정보 검증 (실제로는 암호화 필요)
    if "password" in source.connection_config:
        # TODO: V2에서 암호화 구현
        pass

    db_source = DataSource(
        tenant_id=current_user.tenant_id,
        name=source.name,
        description=source.description,
        source_type=source.source_type,
        source_system=source.source_system,
        connection_type=source.connection_type,
        connection_config=source.connection_config,
        sync_enabled=source.sync_enabled,
        sync_interval_minutes=source.sync_interval_minutes,
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


@router.get("/sources/{source_id}", response_model=DataSourceResponse)
async def get_data_source(
    source_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """데이터 소스 상세 조회"""
    source = db.query(DataSource).filter(
        DataSource.source_id == source_id,
        DataSource.tenant_id == current_user.tenant_id
    ).first()

    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    return source


@router.delete("/sources/{source_id}")
async def delete_data_source(
    source_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """데이터 소스 삭제"""
    source = db.query(DataSource).filter(
        DataSource.source_id == source_id,
        DataSource.tenant_id == current_user.tenant_id
    ).first()

    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    db.delete(source)
    db.commit()
    return {"message": "Data source deleted successfully"}


@router.post("/sources/{source_id}/test")
async def test_data_source_connection(
    source_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """데이터 소스 연결 테스트 (MVP: Mock 응답)"""
    source = db.query(DataSource).filter(
        DataSource.source_id == source_id,
        DataSource.tenant_id == current_user.tenant_id
    ).first()

    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    # MVP: 항상 성공 (실제 연결 테스트는 V2에서 구현)
    return {
        "success": True,
        "message": f"Connection test successful (Mock - {source.connection_type})",
        "response_time_ms": random.randint(50, 200),
        "server_info": {
            "type": source.source_system,
            "version": "Mock 1.0",
        },
    }


# ========== Statistics ==========


@router.get("/stats")
async def get_erp_mes_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ERP/MES 데이터 통계"""
    from sqlalchemy import func

    tenant_id = current_user.tenant_id

    # 소스 타입별 카운트
    type_counts = db.query(
        ErpMesData.source_type,
        func.count(ErpMesData.data_id)
    ).filter(
        ErpMesData.tenant_id == tenant_id
    ).group_by(ErpMesData.source_type).all()

    # 레코드 타입별 카운트
    record_counts = db.query(
        ErpMesData.record_type,
        func.count(ErpMesData.data_id)
    ).filter(
        ErpMesData.tenant_id == tenant_id
    ).group_by(ErpMesData.record_type).all()

    # 데이터 소스 수
    source_count = db.query(func.count(DataSource.source_id)).filter(
        DataSource.tenant_id == tenant_id
    ).scalar()

    # 필드 매핑 수
    mapping_count = db.query(func.count(FieldMapping.mapping_id)).filter(
        FieldMapping.tenant_id == tenant_id
    ).scalar()

    return {
        "total_records": sum(c[1] for c in type_counts),
        "by_source_type": {t[0]: t[1] for t in type_counts},
        "by_record_type": {r[0]: r[1] for r in record_counts},
        "data_sources": source_count,
        "field_mappings": mapping_count,
    }


# ========== File Import ==========


class ImportResponse(BaseModel):
    """파일 Import 응답 스키마"""
    success: bool
    imported_count: int
    failed_count: int
    errors: list[str]


def parse_csv_content(content: str) -> list[dict]:
    """CSV 문자열을 파싱하여 딕셔너리 리스트로 변환"""
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


def parse_excel_content(content: bytes) -> list[dict]:
    """Excel 파일을 파싱하여 딕셔너리 리스트로 변환"""
    try:
        import pandas as pd
        df = pd.read_excel(io.BytesIO(content))
        # NaN 값을 None으로 변환
        df = df.where(pd.notnull(df), None)
        return df.to_dict('records')
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="pandas 또는 openpyxl 라이브러리가 필요합니다"
        )


@router.post("/import", response_model=ImportResponse)
async def import_erp_mes_data(
    file: UploadFile = File(..., description="CSV 또는 Excel 파일"),
    source_type: Literal["erp", "mes"] = Form(..., description="소스 타입 (erp 또는 mes)"),
    record_type: str = Form(..., description="레코드 타입 (production_order, inventory 등)"),
    source_system: str = Form(default="file_import", description="소스 시스템명"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """CSV/Excel 파일에서 ERP/MES 데이터 Import

    지원 파일 형식:
    - CSV (.csv): UTF-8 인코딩
    - Excel (.xlsx, .xls)

    파일의 각 행이 하나의 레코드로 저장됩니다.
    첫 번째 행은 컬럼 헤더로 사용됩니다.
    """
    # 파일 확장자 검증
    filename = file.filename or ""
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    if ext not in ["csv", "xlsx", "xls"]:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. CSV 또는 Excel 파일만 지원합니다. (받은 형식: {ext})"
        )

    # 파일 읽기
    content = await file.read()

    # 파일 파싱
    try:
        if ext == "csv":
            # CSV 인코딩 감지 시도
            try:
                text_content = content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text_content = content.decode("cp949")  # 한글 Windows
                except UnicodeDecodeError:
                    text_content = content.decode("latin-1")

            rows = parse_csv_content(text_content)
        else:
            rows = parse_excel_content(content)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"파일 파싱 실패: {str(e)}"
        )

    if not rows:
        raise HTTPException(
            status_code=400,
            detail="파일에 데이터가 없습니다"
        )

    # 데이터 Import
    imported_count = 0
    failed_count = 0
    errors: list[str] = []

    for i, row in enumerate(rows):
        try:
            # 빈 행 스킵
            if not any(row.values()):
                continue

            # external_id 추출 시도 (일반적인 ID 필드명들)
            external_id = None
            for id_field in ["id", "ID", "external_id", "AUFNR", "work_order_id", "equipment_id", "order_id"]:
                if id_field in row and row[id_field]:
                    external_id = str(row[id_field])
                    break

            # 정규화 필드 추출 시도
            quantity = None
            status = None
            timestamp = None

            # 수량 필드
            for qty_field in ["quantity", "qty", "GAMNG", "planned_quantity", "ON_HAND_QTY", "sample_size"]:
                if qty_field in row and row[qty_field] is not None:
                    try:
                        quantity = float(row[qty_field])
                        break
                    except (ValueError, TypeError):
                        pass

            # 상태 필드
            for status_field in ["status", "STATUS", "result", "sync_status"]:
                if status_field in row and row[status_field]:
                    status = str(row[status_field])
                    break

            # 타임스탬프 필드
            for ts_field in ["timestamp", "created_at", "GSTRP", "scheduled_start", "inspection_date", "last_update"]:
                if ts_field in row and row[ts_field]:
                    try:
                        ts_value = row[ts_field]
                        if isinstance(ts_value, datetime):
                            timestamp = ts_value
                        else:
                            timestamp = datetime.fromisoformat(str(ts_value).replace("Z", "+00:00"))
                        break
                    except (ValueError, TypeError):
                        pass

            # 데이터 저장
            db_data = ErpMesData(
                tenant_id=current_user.tenant_id,
                source_type=source_type,
                source_system=source_system,
                record_type=record_type,
                external_id=external_id or f"row_{i+1}",
                raw_data=row,
                normalized_quantity=quantity,
                normalized_status=status,
                normalized_timestamp=timestamp,
            )
            db.add(db_data)
            imported_count += 1

        except Exception as e:
            failed_count += 1
            if len(errors) < 10:  # 에러는 최대 10개만 저장
                errors.append(f"행 {i+1}: {str(e)}")

    # 커밋
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"데이터 저장 실패: {str(e)}"
        )

    return ImportResponse(
        success=imported_count > 0,
        imported_count=imported_count,
        failed_count=failed_count,
        errors=errors,
    )
