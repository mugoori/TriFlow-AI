"""
Module Definitions and Industry Profiles Seed Data
테넌트별 모듈 설정을 위한 마스터 데이터

사용:
- 마이그레이션에서 SQL로 직접 삽입 (005_tenant_modules.py)
- 또는 이 데이터를 스크립트에서 참조하여 동적으로 삽입
"""
from typing import List, Optional, TypedDict


class ModuleDefinitionDict(TypedDict, total=False):
    """모듈 정의 타입"""
    module_code: str
    name: str
    description: Optional[str]
    category: str  # 'core', 'feature', 'industry'
    icon: str
    default_enabled: bool
    requires_subscription: Optional[str]  # 'standard', 'enterprise', None
    depends_on: Optional[List[str]]
    display_order: int


class IndustryProfileDict(TypedDict, total=False):
    """산업별 프로필 타입"""
    industry_code: str
    name: str
    description: str
    default_modules: List[str]
    default_kpis: List[str]
    sample_rulesets: List[str]
    icon: str


# =============================================================================
# 모듈 정의 마스터 데이터
# =============================================================================

MODULE_DEFINITIONS: List[ModuleDefinitionDict] = [
    # -----------------------------------------------------
    # Core 모듈 (항상 포함, 비활성화 불가)
    # -----------------------------------------------------
    {
        "module_code": "dashboard",
        "name": "대시보드",
        "description": "핵심 지표 및 현황 대시보드",
        "category": "core",
        "icon": "LayoutDashboard",
        "default_enabled": True,
        "requires_subscription": None,
        "display_order": 1,
    },
    {
        "module_code": "chat",
        "name": "AI Chat",
        "description": "AI 어시스턴트와 대화",
        "category": "core",
        "icon": "MessageSquare",
        "default_enabled": True,
        "requires_subscription": None,
        "display_order": 2,
    },
    {
        "module_code": "data",
        "name": "데이터 관리",
        "description": "ERP/MES/센서 데이터 관리",
        "category": "core",
        "icon": "Database",
        "default_enabled": True,
        "requires_subscription": None,
        "display_order": 7,
    },
    {
        "module_code": "settings",
        "name": "설정",
        "description": "시스템 설정 관리",
        "category": "core",
        "icon": "Settings",
        "default_enabled": True,
        "requires_subscription": None,
        "display_order": 10,
    },

    # -----------------------------------------------------
    # Feature 모듈 (구독 플랜에 따라 활성화)
    # -----------------------------------------------------
    {
        "module_code": "workflows",
        "name": "워크플로우",
        "description": "자동화 워크플로우 관리",
        "category": "feature",
        "icon": "GitBranch",
        "default_enabled": True,
        "requires_subscription": None,  # 모든 플랜에서 사용 가능
        "display_order": 3,
    },
    {
        "module_code": "rulesets",
        "name": "판단 규칙",
        "description": "Rhai 스크립트 기반 규칙 관리",
        "category": "feature",
        "icon": "FileCode",
        "default_enabled": False,
        "requires_subscription": "standard",  # standard 이상
        "display_order": 4,
    },
    {
        "module_code": "experiments",
        "name": "A/B 실험",
        "description": "규칙 A/B 테스트 관리",
        "category": "feature",
        "icon": "FlaskConical",
        "default_enabled": False,
        "requires_subscription": "enterprise",  # enterprise 이상
        "display_order": 5,
    },
    {
        "module_code": "learning",
        "name": "학습",
        "description": "AI 학습 및 규칙 자동 생성",
        "category": "feature",
        "icon": "GraduationCap",
        "default_enabled": False,
        "requires_subscription": "enterprise",  # enterprise 이상
        "display_order": 6,
    },

    # -----------------------------------------------------
    # Industry 모듈 (도메인 특화)
    # -----------------------------------------------------
    {
        "module_code": "quality_pharma",
        "name": "품질관리 (제약)",
        "description": "제약 산업 특화 품질 관리 - GMP, 배치 추적, 멸균 관리",
        "category": "industry",
        "icon": "Pill",
        "default_enabled": False,
        "requires_subscription": None,
        "display_order": 100,
    },
    {
        "module_code": "quality_food",
        "name": "품질관리 (식품)",
        "description": "식품 산업 특화 품질 관리 - HACCP, 발효 모니터링, 염도 관리",
        "category": "industry",
        "icon": "UtensilsCrossed",
        "default_enabled": False,
        "requires_subscription": None,
        "display_order": 101,
    },
    {
        "module_code": "quality_elec",
        "name": "품질관리 (전자)",
        "description": "전자 산업 특화 품질 관리 - AOI, 솔더링, PCB 검사",
        "category": "industry",
        "icon": "Cpu",
        "default_enabled": False,
        "requires_subscription": None,
        "display_order": 102,
    },
]


# =============================================================================
# 산업별 프로필 데이터
# =============================================================================

INDUSTRY_PROFILES: List[IndustryProfileDict] = [
    {
        "industry_code": "general",
        "name": "일반 제조",
        "description": "범용 제조업 프로필",
        "default_modules": ["dashboard", "chat", "workflows", "data", "settings"],
        "default_kpis": ["defect_rate", "yield_rate", "downtime", "oee"],
        "sample_rulesets": [],
        "icon": "Factory",
    },
    {
        "industry_code": "pharma",
        "name": "제약/화학",
        "description": "제약, 화학, 바이오 산업 프로필",
        "default_modules": [
            "dashboard", "chat", "rulesets", "quality_pharma",
            "learning", "data", "settings"
        ],
        "default_kpis": [
            "batch_yield", "mixing_ratio", "contamination_rate", "sterility_pass_rate"
        ],
        "sample_rulesets": [
            "pharma_mixing_check",
            "pharma_temp_humidity_control",
            "pharma_batch_release"
        ],
        "icon": "Pill",
    },
    {
        "industry_code": "food",
        "name": "식품/발효",
        "description": "식품, 음료, 발효 산업 프로필",
        "default_modules": [
            "dashboard", "chat", "rulesets", "quality_food", "data", "settings"
        ],
        "default_kpis": [
            "fermentation_level", "salinity", "ph_level", "moisture_content"
        ],
        "sample_rulesets": [
            "food_salinity_check",
            "food_fermentation_control",
            "food_haccp_monitoring"
        ],
        "icon": "UtensilsCrossed",
    },
    {
        "industry_code": "electronics",
        "name": "전자/반도체",
        "description": "전자, 반도체, PCB 산업 프로필",
        "default_modules": [
            "dashboard", "chat", "workflows", "quality_elec",
            "experiments", "data", "settings"
        ],
        "default_kpis": [
            "defect_rate", "yield_rate", "cycle_time", "first_pass_yield"
        ],
        "sample_rulesets": [
            "elec_defect_detection",
            "elec_aoi_check",
            "elec_solder_quality"
        ],
        "icon": "Cpu",
    },
]


# =============================================================================
# 헬퍼 함수
# =============================================================================

def get_module_by_code(module_code: str) -> Optional[ModuleDefinitionDict]:
    """모듈 코드로 모듈 정의 조회"""
    for module in MODULE_DEFINITIONS:
        if module["module_code"] == module_code:
            return module
    return None


def get_profile_by_code(industry_code: str) -> Optional[IndustryProfileDict]:
    """산업 코드로 프로필 조회"""
    for profile in INDUSTRY_PROFILES:
        if profile["industry_code"] == industry_code:
            return profile
    return None


def get_modules_by_category(category: str) -> List[ModuleDefinitionDict]:
    """카테고리별 모듈 목록 조회"""
    return [m for m in MODULE_DEFINITIONS if m["category"] == category]


def get_default_enabled_modules() -> List[str]:
    """기본 활성화 모듈 코드 목록"""
    return [m["module_code"] for m in MODULE_DEFINITIONS if m.get("default_enabled", False)]
