"""
Domain Registry Service
모듈의 도메인 키워드를 자동으로 인식하여 Intent 라우팅 및 스키마 관리
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DomainConfig:
    """모듈의 도메인 설정"""
    module_code: str              # 모듈 코드 (예: "korea_biopharm")
    name: str                     # 모듈 이름 (예: "한국바이오팜")
    keywords: List[str]           # 도메인 키워드 (예: ["비타민", "배합비"])
    schema_name: Optional[str]    # DB 스키마 이름
    tables: List[str]             # 테이블 목록
    route_to: str                 # 라우팅 대상 (기본: "BI_GUIDE")
    sample_queries: List[str]     # 예시 쿼리
    description: Optional[str]    # 설명


class DomainRegistry:
    """
    동적 도메인 레지스트리

    modules/_registry.json에서 도메인 키워드를 로드하여
    AI 채팅에서 자동으로 모듈 데이터를 인식하도록 함.

    사용 예:
        registry = get_domain_registry()
        domain = registry.match_domain("비타민C 포함 제품")
        if domain:
            # korea_biopharm 도메인 매칭됨
            schema = domain.schema_name  # "korea_biopharm"
    """

    _instance = None  # Singleton

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.domains: Dict[str, DomainConfig] = {}
        self._load_from_modules()
        self._initialized = True

    def _load_from_modules(self):
        """modules/_registry.json에서 도메인 설정 로드"""
        registry_path = Path(__file__).parent.parent.parent.parent / "modules" / "_registry.json"

        if not registry_path.exists():
            logger.warning(f"Module registry not found: {registry_path}")
            return

        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry_data = json.load(f)

            # modules 배열에서 로드
            modules = registry_data.get("modules", [])

            loaded_count = 0
            for config in modules:
                module_code = config.get("module_code")
                if not module_code:
                    continue

                # domain_config가 있는 모듈만 로드
                if "domain_config" in config:
                    dc = config["domain_config"]
                    self.domains[module_code] = DomainConfig(
                        module_code=module_code,
                        name=config.get("name", module_code),
                        keywords=dc.get("keywords", []),
                        schema_name=dc.get("schema_name"),
                        tables=dc.get("tables", []),
                        route_to=dc.get("route_to", "BI_GUIDE"),
                        sample_queries=dc.get("sample_queries", []),
                        description=dc.get("description"),
                    )
                    loaded_count += 1

            logger.info(f"DomainRegistry loaded {loaded_count} domain configs from {len(modules)} modules")

        except Exception as e:
            logger.error(f"Failed to load domain registry: {e}")

    def match_domain(self, user_input: str) -> Optional[DomainConfig]:
        """
        사용자 입력에서 도메인 매칭 (키워드 기반)

        Args:
            user_input: 사용자 입력 텍스트

        Returns:
            DomainConfig: 매칭된 도메인 (키워드가 발견되면)
            None: 매칭 실패
        """
        if not user_input:
            return None

        user_input_lower = user_input.lower()

        # 모든 도메인의 키워드 확인
        for domain_code, config in self.domains.items():
            for keyword in config.keywords:
                if keyword.lower() in user_input_lower:
                    logger.info(
                        f"[DomainRegistry] Matched domain '{domain_code}' "
                        f"(keyword: '{keyword}' in '{user_input[:50]}...')"
                    )
                    return config

        return None

    def get_all_schemas(self) -> List[str]:
        """
        모든 모듈의 스키마 목록 반환 (동적)

        Returns:
            스키마 이름 리스트 (core, bi, rag, audit + 모듈 스키마들)
        """
        base_schemas = ['core', 'bi', 'rag', 'audit']
        module_schemas = [
            d.schema_name for d in self.domains.values()
            if d.schema_name
        ]
        return base_schemas + module_schemas

    def generate_schema_docs(self) -> str:
        """
        BIPlannerAgent용 스키마 문서 자동 생성

        Returns:
            마크다운 형식의 스키마 문서
        """
        if not self.domains:
            return ""

        docs = []
        for domain in self.domains.values():
            if not domain.schema_name:
                continue

            doc = f"""
### {domain.name} Schema ({domain.schema_name})

**도메인 키워드**: {", ".join(domain.keywords)}
**테이블**: {", ".join(domain.tables)}

{domain.description or ""}

**예시 쿼리**:
"""
            for i, query in enumerate(domain.sample_queries[:3], 1):
                doc += f"{i}. {query}\n"

            docs.append(doc)

        return "\n".join(docs)

    def get_domain(self, module_code: str) -> Optional[DomainConfig]:
        """특정 모듈의 도메인 설정 반환"""
        return self.domains.get(module_code)


# 전역 인스턴스 (Singleton)
_registry_instance = None


def get_domain_registry() -> DomainRegistry:
    """
    DomainRegistry 싱글톤 인스턴스 반환

    사용 예:
        registry = get_domain_registry()
        domain = registry.match_domain("비타민C 포함 제품")
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = DomainRegistry()
    return _registry_instance
