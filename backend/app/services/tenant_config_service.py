"""
Tenant Configuration Service
테넌트별 모듈 설정 및 기능 플래그 관리

Multi-Tenant Customization 전략의 핵심 서비스:
- 모듈 활성화/비활성화
- 산업 프로필 기반 초기화
- 구독 플랜 기반 기능 플래그
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.core import Tenant
from app.models.tenant_config import ModuleDefinition, TenantModule, IndustryProfile


class TenantConfigService:
    """테넌트 설정 관리 서비스"""

    def __init__(self, db: Session):
        self.db = db

    # =====================================================
    # 모듈 조회
    # =====================================================

    def get_enabled_modules(self, tenant_id: UUID) -> List[str]:
        """테넌트의 활성화된 모듈 코드 목록 조회

        tenant_modules 테이블이 없거나 비어있으면 빈 리스트 반환
        (get_tenant_config에서 기본값 처리)
        """
        try:
            modules = self.db.query(TenantModule).filter(
                TenantModule.tenant_id == tenant_id,
                TenantModule.is_enabled == True  # noqa: E712
            ).all()

            # 결과가 비어있으면 빈 리스트 반환 (get_tenant_config에서 기본값 사용)
            if not modules:
                return []

            return [m.module_code for m in modules]
        except Exception:
            # 테이블이 없는 경우 빈 리스트 반환
            return []

    def get_all_modules(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """테넌트의 모든 모듈 목록 (활성화 여부 포함)"""
        # 모든 모듈 정의 조회
        all_modules = self.db.query(ModuleDefinition).order_by(
            ModuleDefinition.display_order
        ).all()

        # 테넌트별 모듈 설정 조회
        tenant_modules = self.db.query(TenantModule).filter(
            TenantModule.tenant_id == tenant_id
        ).all()
        tenant_module_map = {tm.module_code: tm for tm in tenant_modules}

        result = []
        for module in all_modules:
            tm = tenant_module_map.get(module.module_code)
            result.append({
                "module_code": module.module_code,
                "name": module.name,
                "description": module.description,
                "category": module.category,
                "icon": module.icon,
                "default_enabled": module.default_enabled,
                "requires_subscription": module.requires_subscription,
                "display_order": module.display_order,
                "is_enabled": tm.is_enabled if tm else module.default_enabled,
                "config": tm.config if tm else {},
            })

        return result

    def get_tenant_config(self, tenant_id: UUID) -> Optional[Dict[str, Any]]:
        """프론트엔드용 전체 설정 조회

        테넌트 모듈 테이블이 아직 없는 경우(마이그레이션 미실행)에도
        기본 모듈을 반환하여 UI가 정상 동작하도록 함
        """
        # 기본 Tenant 정보만 조회 (관계 로딩 없이)
        tenant = self.db.query(Tenant).filter(
            Tenant.tenant_id == tenant_id
        ).first()

        if not tenant:
            return None

        # 테이블 존재 여부 확인 후 모듈 조회 시도
        enabled_modules = []
        module_configs = {}
        industry = None

        try:
            # tenant_modules 테이블이 있는 경우
            enabled_modules = self.get_enabled_modules(tenant_id)

            # 모듈별 설정 조회
            if hasattr(tenant, 'modules') and tenant.modules:
                for tm in tenant.modules:
                    if tm.is_enabled:
                        module_configs[tm.module_code] = tm.config

            # 산업 프로필 조회
            if hasattr(tenant, 'industry_profile') and tenant.industry_profile:
                industry = {
                    "code": tenant.industry_code,
                    "name": tenant.industry_profile.name,
                    "icon": tenant.industry_profile.icon,
                    "default_kpis": tenant.industry_profile.default_kpis or [],
                }
        except Exception:
            # 테이블이 없거나 조회 실패 시 기본 모듈 사용
            enabled_modules = []

        # enabled_modules가 비어있으면 구독 플랜 기반 기본값 설정
        if not enabled_modules:
            # Core 모듈은 항상 활성화
            enabled_modules = ["chat", "dashboard", "workflows", "data", "settings"]

            # standard 이상 플랜이면 rulesets 활성화
            if tenant.subscription_plan in ["standard", "enterprise", "custom"]:
                enabled_modules.append("rulesets")
            # enterprise/custom 플랜이면 추가 모듈도 기본 활성화
            if tenant.subscription_plan in ["enterprise", "custom"]:
                enabled_modules.extend(["experiments", "learning"])

        return {
            "tenant_id": str(tenant_id),
            "tenant_name": tenant.name,
            "subscription_plan": tenant.subscription_plan,
            "enabled_modules": enabled_modules,
            "module_configs": module_configs,
            "industry": industry,
            "features": self._get_feature_flags(tenant),
        }

    def _get_feature_flags(self, tenant: Tenant) -> Dict[str, Any]:
        """구독 플랜 기반 기능 플래그"""
        plan = tenant.subscription_plan

        return {
            "can_use_rulesets": plan in ["standard", "enterprise", "custom"],
            "can_use_experiments": plan in ["enterprise", "custom"],
            "can_use_learning": plan in ["enterprise", "custom"],
            "can_use_mcp": plan in ["enterprise", "custom"],
            "max_workflows": tenant.max_workflows,
            "max_judgments_per_day": tenant.max_judgments_per_day,
            "max_users": tenant.max_users,
        }

    # =====================================================
    # 모듈 활성화/비활성화
    # =====================================================

    def enable_module(
        self,
        tenant_id: UUID,
        module_code: str,
        user_id: Optional[UUID] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> TenantModule:
        """모듈 활성화"""
        # 모듈 정의 확인
        module_def = self.db.query(ModuleDefinition).filter(
            ModuleDefinition.module_code == module_code
        ).first()

        if not module_def:
            raise ValueError(f"Unknown module: {module_code}")

        # 구독 플랜 체크
        if module_def.requires_subscription:
            tenant = self.db.query(Tenant).filter(
                Tenant.tenant_id == tenant_id
            ).first()
            if not tenant:
                raise ValueError(f"Tenant not found: {tenant_id}")

            if not self._check_subscription(tenant, module_def.requires_subscription):
                raise ValueError(
                    f"Module '{module_code}' requires '{module_def.requires_subscription}' subscription"
                )

        # 기존 레코드 확인
        tm = self.db.query(TenantModule).filter(
            TenantModule.tenant_id == tenant_id,
            TenantModule.module_code == module_code
        ).first()

        if tm:
            tm.is_enabled = True
            tm.enabled_at = datetime.utcnow()
            tm.disabled_at = None
            tm.enabled_by = user_id
            if config:
                tm.config = config
        else:
            tm = TenantModule(
                tenant_id=tenant_id,
                module_code=module_code,
                is_enabled=True,
                config=config or {},
                enabled_at=datetime.utcnow(),
                enabled_by=user_id
            )
            self.db.add(tm)

        self.db.commit()
        self.db.refresh(tm)
        return tm

    def disable_module(
        self,
        tenant_id: UUID,
        module_code: str
    ) -> bool:
        """모듈 비활성화

        Core 모듈(dashboard, chat, data, settings)은 비활성화 불가
        """
        # Core 모듈 체크
        module_def = self.db.query(ModuleDefinition).filter(
            ModuleDefinition.module_code == module_code
        ).first()

        if module_def and module_def.category == "core":
            raise ValueError(f"Core module '{module_code}' cannot be disabled")

        tm = self.db.query(TenantModule).filter(
            TenantModule.tenant_id == tenant_id,
            TenantModule.module_code == module_code
        ).first()

        if tm:
            tm.is_enabled = False
            tm.disabled_at = datetime.utcnow()
            self.db.commit()
            return True
        return False

    def update_module_config(
        self,
        tenant_id: UUID,
        module_code: str,
        config: Dict[str, Any]
    ) -> Optional[TenantModule]:
        """모듈 설정 업데이트"""
        tm = self.db.query(TenantModule).filter(
            TenantModule.tenant_id == tenant_id,
            TenantModule.module_code == module_code
        ).first()

        if tm:
            # 기존 설정과 병합
            current_config = tm.config or {}
            current_config.update(config)
            tm.config = current_config
            self.db.commit()
            self.db.refresh(tm)
            return tm
        return None

    def _check_subscription(self, tenant: Tenant, required: str) -> bool:
        """구독 플랜이 요구 조건을 충족하는지 확인"""
        plan_hierarchy = {
            "trial": 0,
            "standard": 1,
            "enterprise": 2,
            "custom": 3,
        }

        tenant_level = plan_hierarchy.get(tenant.subscription_plan, 0)
        required_level = plan_hierarchy.get(required, 0)

        return tenant_level >= required_level

    # =====================================================
    # 테넌트 초기화
    # =====================================================

    def initialize_tenant_modules(
        self,
        tenant_id: UUID,
        industry_code: str = "general",
        user_id: Optional[UUID] = None
    ) -> List[TenantModule]:
        """산업 프로필 기반으로 테넌트 모듈 초기화

        새 테넌트 생성 시 또는 산업 프로필 변경 시 호출
        """
        profile = self.db.query(IndustryProfile).filter(
            IndustryProfile.industry_code == industry_code
        ).first()

        if not profile:
            profile = self.db.query(IndustryProfile).filter(
                IndustryProfile.industry_code == "general"
            ).first()

        # 테넌트에 산업 코드 설정
        tenant = self.db.query(Tenant).filter(
            Tenant.tenant_id == tenant_id
        ).first()

        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")

        tenant.industry_code = industry_code if profile else "general"

        # 기본 모듈 활성화
        enabled_modules = []
        default_modules = profile.default_modules if profile else []

        for module_code in default_modules:
            try:
                tm = self.enable_module(tenant_id, module_code, user_id)
                enabled_modules.append(tm)
            except ValueError:
                # 구독 플랜 제한으로 활성화 불가한 모듈은 건너뜀
                continue

        self.db.commit()
        return enabled_modules

    def change_industry_profile(
        self,
        tenant_id: UUID,
        industry_code: str,
        user_id: Optional[UUID] = None,
        reset_modules: bool = False
    ) -> Dict[str, Any]:
        """테넌트의 산업 프로필 변경

        Args:
            tenant_id: 테넌트 ID
            industry_code: 새 산업 프로필 코드
            user_id: 변경 수행자 ID
            reset_modules: True이면 기존 모듈 설정 초기화

        Returns:
            변경 결과 정보
        """
        profile = self.db.query(IndustryProfile).filter(
            IndustryProfile.industry_code == industry_code
        ).first()

        if not profile:
            raise ValueError(f"Unknown industry profile: {industry_code}")

        tenant = self.db.query(Tenant).filter(
            Tenant.tenant_id == tenant_id
        ).first()

        if not tenant:
            raise ValueError(f"Tenant not found: {tenant_id}")

        old_industry = tenant.industry_code
        tenant.industry_code = industry_code

        if reset_modules:
            # 기존 모듈 설정 삭제
            self.db.query(TenantModule).filter(
                TenantModule.tenant_id == tenant_id
            ).delete()

            # 새 프로필 기반으로 모듈 초기화
            self.initialize_tenant_modules(tenant_id, industry_code, user_id)

        self.db.commit()

        return {
            "tenant_id": str(tenant_id),
            "old_industry": old_industry,
            "new_industry": industry_code,
            "modules_reset": reset_modules,
        }

    # =====================================================
    # 조회 헬퍼
    # =====================================================

    def get_module_definition(self, module_code: str) -> Optional[ModuleDefinition]:
        """모듈 정의 조회"""
        return self.db.query(ModuleDefinition).filter(
            ModuleDefinition.module_code == module_code
        ).first()

    def get_all_module_definitions(self) -> List[ModuleDefinition]:
        """모든 모듈 정의 조회"""
        return self.db.query(ModuleDefinition).order_by(
            ModuleDefinition.display_order
        ).all()

    def get_industry_profile(self, industry_code: str) -> Optional[IndustryProfile]:
        """산업 프로필 조회"""
        return self.db.query(IndustryProfile).filter(
            IndustryProfile.industry_code == industry_code
        ).first()

    def get_all_industry_profiles(self) -> List[IndustryProfile]:
        """모든 산업 프로필 조회"""
        return self.db.query(IndustryProfile).all()

    def is_module_enabled(self, tenant_id: UUID, module_code: str) -> bool:
        """특정 모듈이 활성화되어 있는지 확인"""
        tm = self.db.query(TenantModule).filter(
            TenantModule.tenant_id == tenant_id,
            TenantModule.module_code == module_code,
            TenantModule.is_enabled == True  # noqa: E712
        ).first()

        return tm is not None
