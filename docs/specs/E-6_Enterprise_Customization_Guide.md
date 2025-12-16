# E-6. 기업별 커스터마이징 가이드

## 문서 정보
| 항목 | 내용 |
|------|------|
| 문서명 | 기업별 커스터마이징 가이드 |
| 문서 ID | E-6 |
| 버전 | 2.0 (V7 Intent + Orchestrator) |
| 최종 수정일 | 2025-12-16 |
| 상태 | Active Development |
| 관련 문서 | B-3-3 V7 Intent Router 설계, B-3-4 Orchestrator 설계, B-6 AI/Agent Architecture, E-3 Intent Router Prototype, E-5 Multi-Tenant 권한관리 |

---

## 1. 개요

### 1.1 목적
본 문서는 AI Factory Decision Engine을 다양한 제조 기업에 도입할 때, 각 기업의 특성에 맞게 커스터마이징하는 방법과 실제 구현 계획을 정의합니다.

### 1.2 커스터마이징 범위
```
┌─────────────────────────────────────────────────────────────────┐
│                   기업별 커스터마이징 영역                          │
├─────────────────────────────────────────────────────────────────┤
│  1. Context Engineering     │  기업별 맥락 정보 구성                │
│  2. Prompting Strategy      │  산업/기업 특화 프롬프트              │
│  3. Intent Configuration    │  업무 의도 분류 체계                  │
│  4. Terminology Mapping     │  기업 용어 ↔ 표준 용어 매핑           │
│  5. Response Formatting     │  출력 형식 및 스타일                  │
│  6. Data Access Rules       │  데이터 접근 범위 설정                │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 커스터마이징 접근 방식: 하이브리드

**선택된 아키텍처**: Base Template + DB Override (하이브리드)

```
┌─────────────────────────────────────────────────────────────────┐
│                    하이브리드 커스터마이징 구조                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────┐                                          │
│   │  Base Template  │  ← 공통 템플릿 (YAML 파일)                 │
│   │   (defaults/)   │    - 기본 Context 구조                    │
│   │                 │    - 표준 Intent 정의                     │
│   └────────┬────────┘    - 공통 Prompt 템플릿                   │
│            │                                                    │
│            ▼ 상속 & 오버라이드                                   │
│   ┌─────────────────┐                                          │
│   │   DB Override   │  ← 기업별 설정 (Database)                 │
│   │  (tenant_xxx)   │    - 커스텀 Intent 추가                   │
│   │                 │    - 용어 매핑                            │
│   └────────┬────────┘    - 프롬프트 수정                        │
│            │                                                    │
│            ▼ 최종 병합                                          │
│   ┌─────────────────┐                                          │
│   │  Merged Config  │  ← 런타임 적용 설정                        │
│   │   (Runtime)     │                                          │
│   └─────────────────┘                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**하이브리드 방식 선택 이유**:
| 장점 | 설명 |
|------|------|
| 빠른 온보딩 | Base Template으로 기본 기능 즉시 사용 가능 |
| 유연한 확장 | DB를 통해 기업별 특성 반영 |
| 버전 관리 | Base는 Git, Override는 DB 이력관리 |
| 운영 효율성 | 공통 업데이트는 Base, 개별 설정은 DB |

---

## 2. 데이터 모델

### 2.1 커스터마이징 테이블 구조

```sql
-- ============================================
-- 기업별 Context 설정
-- ============================================
CREATE TABLE tenant_context_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    -- Context Layer 설정
    context_layer VARCHAR(50) NOT NULL,  -- system, task, session, query

    -- 설정 내용
    config_key VARCHAR(100) NOT NULL,
    config_value JSONB NOT NULL,

    -- 우선순위 (낮을수록 먼저 로드)
    priority INTEGER DEFAULT 100,

    -- 토큰 제한
    max_tokens INTEGER DEFAULT 500,

    -- 활성화 조건
    activation_conditions JSONB DEFAULT '{}',

    -- 메타데이터
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),

    UNIQUE(tenant_id, context_layer, config_key)
);

-- 예시 데이터
INSERT INTO tenant_context_config (tenant_id, context_layer, config_key, config_value, priority)
VALUES
-- A기업: 자동차 부품 제조사
('tenant-a-uuid', 'system', 'industry_context', '{
    "industry": "automotive_parts",
    "main_products": ["엔진 부품", "변속기 부품", "브레이크 시스템"],
    "quality_standards": ["IATF 16949", "ISO 9001"],
    "key_metrics": ["PPM", "Cpk", "OEE"]
}', 10),

-- A기업: 생산 시스템 정보
('tenant-a-uuid', 'system', 'production_system', '{
    "mes_system": "SAP ME",
    "erp_system": "SAP S/4HANA",
    "shift_pattern": "3교대",
    "lines": ["SMT-1", "SMT-2", "조립-A", "조립-B"]
}', 20);


-- ============================================
-- 기업별 Intent 정의
-- ============================================
CREATE TABLE tenant_intents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    -- Intent 정보
    intent_code VARCHAR(100) NOT NULL,
    intent_name VARCHAR(200) NOT NULL,
    intent_category VARCHAR(100),

    -- Intent 설명 및 예시
    description TEXT,
    example_queries JSONB DEFAULT '[]',

    -- 분류 설정
    keywords JSONB DEFAULT '[]',
    patterns JSONB DEFAULT '[]',
    confidence_threshold DECIMAL(3,2) DEFAULT 0.7,

    -- 라우팅 설정
    agent_type VARCHAR(100),
    required_data_sources JSONB DEFAULT '[]',

    -- 권한 설정
    min_role_level INTEGER DEFAULT 5,  -- 1=executive ~ 5=operator
    allowed_roles JSONB DEFAULT '[]',

    -- 프롬프트 템플릿 참조
    prompt_template_id UUID REFERENCES tenant_prompts(id),

    -- 메타데이터
    is_active BOOLEAN DEFAULT true,
    is_custom BOOLEAN DEFAULT true,  -- false면 base에서 상속
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tenant_id, intent_code)
);

-- 예시: A기업 커스텀 Intent
INSERT INTO tenant_intents (tenant_id, intent_code, intent_name, intent_category,
                           example_queries, keywords, agent_type, min_role_level)
VALUES
('tenant-a-uuid', 'cpk_analysis', 'Cpk 분석 요청', 'quality',
 '["SMT-1 라인 Cpk 어때?", "이번 주 공정능력 보여줘", "불량률 트렌드 분석해줘"]',
 '["Cpk", "공정능력", "불량률", "품질"]',
 'quality_analytics', 4),

('tenant-a-uuid', 'customer_claim_search', '고객 클레임 조회', 'quality',
 '["현대차 클레임 현황", "이번 달 고객 불만 건수", "클레임 이력 조회"]',
 '["클레임", "고객불만", "품질이슈", "반품"]',
 'crm_search', 3);


-- ============================================
-- 기업별 용어 매핑
-- ============================================
CREATE TABLE tenant_terminology (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    -- 용어 매핑
    company_term VARCHAR(200) NOT NULL,      -- 기업 내부 용어
    standard_term VARCHAR(200) NOT NULL,     -- 표준 용어
    term_category VARCHAR(100),              -- 분류

    -- 동의어 및 약어
    synonyms JSONB DEFAULT '[]',
    abbreviations JSONB DEFAULT '[]',

    -- 컨텍스트 힌트
    usage_context TEXT,
    examples JSONB DEFAULT '[]',

    -- 메타데이터
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tenant_id, company_term, standard_term)
);

-- 예시: A기업 용어 매핑
INSERT INTO tenant_terminology (tenant_id, company_term, standard_term, term_category, synonyms)
VALUES
('tenant-a-uuid', 'SMT', 'Surface Mount Technology', 'equipment', '["표면실장", "SMT라인"]'),
('tenant-a-uuid', 'AOI', 'Automated Optical Inspection', 'equipment', '["광학검사", "자동검사"]'),
('tenant-a-uuid', '현대향', '현대자동차 납품용', 'customer', '["HMC향", "현대차용"]'),
('tenant-a-uuid', '인라인', '생산라인 내 공정', 'process', '["라인 내", "인라인검사"]');


-- ============================================
-- 기업별 Few-shot 예시
-- ============================================
CREATE TABLE tenant_few_shots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    -- Few-shot 정보
    intent_code VARCHAR(100) NOT NULL,

    -- 예시 쌍
    user_query TEXT NOT NULL,
    assistant_response TEXT NOT NULL,

    -- 품질 메트릭
    quality_score DECIMAL(3,2) DEFAULT 0.8,
    usage_count INTEGER DEFAULT 0,

    -- 태그 및 조건
    tags JSONB DEFAULT '[]',
    applicable_roles JSONB DEFAULT '[]',

    -- 메타데이터
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_tenant_intent (tenant_id, intent_code)
);

-- 예시: A기업 Few-shot
INSERT INTO tenant_few_shots (tenant_id, intent_code, user_query, assistant_response, tags)
VALUES
('tenant-a-uuid', 'production_status',
 'SMT-1 라인 오늘 생산 현황 어때?',
 '## SMT-1 라인 금일 생산 현황\n\n| 항목 | 수치 | 목표 대비 |\n|------|------|----------|\n| 생산량 | 12,450개 | 98.4% |\n| 불량률 | 0.12% | 양호 |\n| OEE | 87.3% | 목표 초과 |\n\n특이사항: 14시 30분 설비 점검으로 15분 정지',
 '["생산현황", "SMT", "일일리포트"]'),

('tenant-a-uuid', 'quality_analysis',
 'Cpk가 1.33 미만인 공정 알려줘',
 '## 공정능력 미달 공정 현황\n\n현재 Cpk 1.33 미만 공정 **3건** 식별:\n\n| 공정 | 현재 Cpk | 상태 | 조치사항 |\n|------|----------|------|----------|\n| SMT-1 리플로우 | 1.21 | ⚠️ 주의 | 온도 프로파일 재설정 권장 |\n| 조립-A 체결 | 1.15 | 🔴 관리 | 토크 설정값 점검 필요 |\n| AOI-2 | 1.28 | ⚠️ 주의 | 조명 교정 예정 |',
 '["품질", "Cpk", "공정능력"]');


-- ============================================
-- 기업별 프롬프트 템플릿
-- ============================================
CREATE TABLE tenant_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    -- 프롬프트 식별
    prompt_code VARCHAR(100) NOT NULL,
    prompt_name VARCHAR(200) NOT NULL,
    prompt_type VARCHAR(50) NOT NULL,  -- system, task, response_format

    -- 프롬프트 내용
    prompt_template TEXT NOT NULL,

    -- 변수 정의
    variables JSONB DEFAULT '[]',

    -- 버전 관리
    version VARCHAR(20) DEFAULT '1.0.0',
    parent_version_id UUID REFERENCES tenant_prompts(id),

    -- A/B 테스트
    ab_test_group VARCHAR(50),
    ab_test_weight DECIMAL(3,2) DEFAULT 1.0,

    -- 성능 메트릭
    avg_response_quality DECIMAL(3,2),
    usage_count INTEGER DEFAULT 0,

    -- 메타데이터
    is_active BOOLEAN DEFAULT true,
    effective_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id),

    UNIQUE(tenant_id, prompt_code, version)
);

-- 예시: A기업 시스템 프롬프트
INSERT INTO tenant_prompts (tenant_id, prompt_code, prompt_name, prompt_type, prompt_template, variables)
VALUES
('tenant-a-uuid', 'system_base', '기본 시스템 프롬프트', 'system',
'당신은 {{company_name}}의 AI 생산관리 어시스턴트입니다.

## 회사 정보
- 산업: {{industry}}
- 주요 제품: {{main_products}}
- 품질 기준: {{quality_standards}}

## 역할
사용자의 질문에 대해 정확하고 실용적인 답변을 제공합니다.
현재 사용자 역할: {{user_role}}
접근 가능 데이터: {{accessible_data}}

## 응답 원칙
1. 데이터 기반의 객관적 분석 제공
2. 실행 가능한 권고사항 포함
3. 권한 범위 내 정보만 제공
4. 불확실한 경우 명시적으로 표현',
'["company_name", "industry", "main_products", "quality_standards", "user_role", "accessible_data"]');


-- ============================================
-- 기업별 응답 포맷 설정
-- ============================================
CREATE TABLE tenant_response_formats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    -- 포맷 정보
    format_code VARCHAR(100) NOT NULL,
    format_name VARCHAR(200) NOT NULL,
    intent_category VARCHAR(100),

    -- 포맷 템플릿
    format_template TEXT NOT NULL,

    -- 스타일 설정
    style_config JSONB DEFAULT '{
        "use_tables": true,
        "use_charts": false,
        "max_sections": 5,
        "summary_first": true,
        "include_recommendations": true
    }',

    -- 역할별 변형
    role_variations JSONB DEFAULT '{}',

    -- 메타데이터
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tenant_id, format_code)
);

-- 예시: A기업 응답 포맷
INSERT INTO tenant_response_formats (tenant_id, format_code, format_name, intent_category,
                                     format_template, role_variations)
VALUES
('tenant-a-uuid', 'production_report', '생산 현황 리포트', 'production',
'## {{title}}

### 요약
{{summary}}

### 상세 현황
{{details_table}}

### 특이사항
{{issues}}

### 권고사항
{{recommendations}}

---
*기준시각: {{timestamp}} | 데이터 출처: {{data_source}}*',
'{
    "executive": {
        "max_sections": 3,
        "focus": ["summary", "recommendations"],
        "detail_level": "high-level"
    },
    "operator": {
        "max_sections": 2,
        "focus": ["details_table", "issues"],
        "detail_level": "operational"
    }
}');
```

### 2.2 Entity Relationship Diagram

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│     tenants      │     │      users       │     │   user_roles     │
├──────────────────┤     ├──────────────────┤     ├──────────────────┤
│ id (PK)          │◄────┤ tenant_id (FK)   │────►│ user_id (FK)     │
│ name             │     │ id (PK)          │     │ role_id (FK)     │
│ config           │     │ name             │     │ tenant_id        │
└────────┬─────────┘     └──────────────────┘     └──────────────────┘
         │
         │ 1:N
         ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│tenant_context    │     │ tenant_intents   │     │tenant_terminology│
│    _config       │     ├──────────────────┤     ├──────────────────┤
├──────────────────┤     │ tenant_id (FK)   │     │ tenant_id (FK)   │
│ tenant_id (FK)   │     │ intent_code      │     │ company_term     │
│ context_layer    │     │ prompt_template  │     │ standard_term    │
│ config_key       │     │   _id (FK)───────┼──┐  │ synonyms         │
│ config_value     │     └──────────────────┘  │  └──────────────────┘
└──────────────────┘                           │
                                               │
┌──────────────────┐     ┌──────────────────┐  │  ┌──────────────────┐
│tenant_few_shots  │     │ tenant_prompts   │◄─┘  │tenant_response   │
├──────────────────┤     ├──────────────────┤     │    _formats      │
│ tenant_id (FK)   │     │ id (PK)          │     ├──────────────────┤
│ intent_code      │     │ tenant_id (FK)   │     │ tenant_id (FK)   │
│ user_query       │     │ prompt_code      │     │ format_code      │
│ assistant_resp   │     │ prompt_template  │     │ format_template  │
└──────────────────┘     │ version          │     │ role_variations  │
                         └──────────────────┘     └──────────────────┘
```

---

## 3. 커스터마이징 서비스 구현

### 3.1 Tenant Configuration Loader

```python
# services/tenant_config_loader.py

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from functools import lru_cache
import yaml
import json

@dataclass
class TenantConfig:
    """기업별 통합 설정"""
    tenant_id: str
    context_config: Dict[str, Any]
    intents: List[Dict[str, Any]]
    terminology: Dict[str, str]
    few_shots: Dict[str, List[Dict]]
    prompts: Dict[str, str]
    response_formats: Dict[str, Any]


class TenantConfigLoader:
    """
    하이브리드 방식의 기업별 설정 로더
    Base Template + DB Override 패턴 구현
    """

    def __init__(self, db_pool, base_config_path: str = "config/defaults/"):
        self.db = db_pool
        self.base_path = base_config_path
        self._cache: Dict[str, TenantConfig] = {}
        self._cache_ttl = 300  # 5분 캐시

    async def load_config(self, tenant_id: str) -> TenantConfig:
        """기업별 설정 로드 (캐시 적용)"""

        # 캐시 확인
        if tenant_id in self._cache:
            return self._cache[tenant_id]

        # 1. Base Template 로드
        base_config = self._load_base_template()

        # 2. DB Override 로드
        db_overrides = await self._load_db_overrides(tenant_id)

        # 3. 설정 병합
        merged_config = self._merge_configs(base_config, db_overrides)

        # 4. TenantConfig 객체 생성
        tenant_config = TenantConfig(
            tenant_id=tenant_id,
            context_config=merged_config.get('context', {}),
            intents=merged_config.get('intents', []),
            terminology=merged_config.get('terminology', {}),
            few_shots=merged_config.get('few_shots', {}),
            prompts=merged_config.get('prompts', {}),
            response_formats=merged_config.get('response_formats', {})
        )

        # 캐시 저장
        self._cache[tenant_id] = tenant_config

        return tenant_config

    def _load_base_template(self) -> Dict[str, Any]:
        """Base Template YAML 파일들 로드"""

        base_config = {}

        # Context 기본 설정
        with open(f"{self.base_path}/context_base.yaml", 'r', encoding='utf-8') as f:
            base_config['context'] = yaml.safe_load(f)

        # Intent 기본 정의
        with open(f"{self.base_path}/intents_base.yaml", 'r', encoding='utf-8') as f:
            base_config['intents'] = yaml.safe_load(f)

        # 프롬프트 기본 템플릿
        with open(f"{self.base_path}/prompts_base.yaml", 'r', encoding='utf-8') as f:
            base_config['prompts'] = yaml.safe_load(f)

        # 응답 포맷 기본값
        with open(f"{self.base_path}/response_formats_base.yaml", 'r', encoding='utf-8') as f:
            base_config['response_formats'] = yaml.safe_load(f)

        return base_config

    async def _load_db_overrides(self, tenant_id: str) -> Dict[str, Any]:
        """DB에서 기업별 오버라이드 설정 로드"""

        overrides = {}

        # Context 오버라이드
        context_rows = await self.db.fetch("""
            SELECT context_layer, config_key, config_value, priority
            FROM tenant_context_config
            WHERE tenant_id = $1 AND is_active = true
            ORDER BY priority ASC
        """, tenant_id)

        overrides['context'] = {}
        for row in context_rows:
            layer = row['context_layer']
            if layer not in overrides['context']:
                overrides['context'][layer] = {}
            overrides['context'][layer][row['config_key']] = row['config_value']

        # Intent 오버라이드
        intent_rows = await self.db.fetch("""
            SELECT intent_code, intent_name, intent_category,
                   example_queries, keywords, patterns,
                   agent_type, min_role_level, is_custom
            FROM tenant_intents
            WHERE tenant_id = $1 AND is_active = true
        """, tenant_id)

        overrides['intents'] = [dict(row) for row in intent_rows]

        # 용어 매핑
        term_rows = await self.db.fetch("""
            SELECT company_term, standard_term, synonyms
            FROM tenant_terminology
            WHERE tenant_id = $1 AND is_active = true
        """, tenant_id)

        overrides['terminology'] = {}
        for row in term_rows:
            overrides['terminology'][row['company_term']] = {
                'standard': row['standard_term'],
                'synonyms': row['synonyms'] or []
            }

        # Few-shot 예시
        few_shot_rows = await self.db.fetch("""
            SELECT intent_code, user_query, assistant_response,
                   quality_score, tags
            FROM tenant_few_shots
            WHERE tenant_id = $1 AND is_active = true
            ORDER BY quality_score DESC
        """, tenant_id)

        overrides['few_shots'] = {}
        for row in few_shot_rows:
            intent = row['intent_code']
            if intent not in overrides['few_shots']:
                overrides['few_shots'][intent] = []
            overrides['few_shots'][intent].append({
                'query': row['user_query'],
                'response': row['assistant_response'],
                'score': float(row['quality_score']),
                'tags': row['tags']
            })

        # 프롬프트 템플릿
        prompt_rows = await self.db.fetch("""
            SELECT prompt_code, prompt_type, prompt_template, variables
            FROM tenant_prompts
            WHERE tenant_id = $1 AND is_active = true
            AND (effective_to IS NULL OR effective_to > NOW())
            ORDER BY effective_from DESC
        """, tenant_id)

        overrides['prompts'] = {}
        for row in prompt_rows:
            overrides['prompts'][row['prompt_code']] = {
                'type': row['prompt_type'],
                'template': row['prompt_template'],
                'variables': row['variables']
            }

        # 응답 포맷
        format_rows = await self.db.fetch("""
            SELECT format_code, format_template, style_config, role_variations
            FROM tenant_response_formats
            WHERE tenant_id = $1 AND is_active = true
        """, tenant_id)

        overrides['response_formats'] = {}
        for row in format_rows:
            overrides['response_formats'][row['format_code']] = {
                'template': row['format_template'],
                'style': row['style_config'],
                'role_variations': row['role_variations']
            }

        return overrides

    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """Base와 Override 설정 병합 (Deep Merge)"""

        result = {}

        for key in set(list(base.keys()) + list(override.keys())):
            base_val = base.get(key)
            override_val = override.get(key)

            if override_val is None:
                result[key] = base_val
            elif base_val is None:
                result[key] = override_val
            elif isinstance(base_val, dict) and isinstance(override_val, dict):
                # Dict는 재귀적 병합
                result[key] = self._merge_configs(base_val, override_val)
            elif isinstance(base_val, list) and isinstance(override_val, list):
                # List는 override 우선, is_custom=False인 base 항목 유지
                if key == 'intents':
                    result[key] = self._merge_intents(base_val, override_val)
                else:
                    result[key] = override_val + [
                        item for item in base_val
                        if item not in override_val
                    ]
            else:
                # 기타는 override 우선
                result[key] = override_val

        return result

    def _merge_intents(self, base_intents: List, override_intents: List) -> List:
        """Intent 목록 병합 (커스텀 + 기본)"""

        # Override intent codes
        override_codes = {i.get('intent_code') for i in override_intents}

        # Base 중 override되지 않은 것 + Override 모두
        merged = [
            intent for intent in base_intents
            if intent.get('intent_code') not in override_codes
        ]
        merged.extend(override_intents)

        return merged

    def invalidate_cache(self, tenant_id: str = None):
        """캐시 무효화"""
        if tenant_id:
            self._cache.pop(tenant_id, None)
        else:
            self._cache.clear()
```

### 3.2 Tenant-Aware Context Builder

```python
# services/tenant_context_builder.py

from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ContextBudget:
    """Context 토큰 예산"""
    system: int = 500
    task: int = 400
    session: int = 300
    query: int = 200
    few_shot: int = 600
    total_limit: int = 2000


class TenantContextBuilder:
    """
    기업별 Context 구성기
    4-Layer Context + 토큰 예산 관리
    """

    def __init__(self, config_loader: TenantConfigLoader):
        self.config_loader = config_loader
        self.default_budget = ContextBudget()

    async def build_context(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        intent: str,
        query: str,
        session_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        기업별 맞춤 Context 구성

        Returns:
            {
                "system_context": str,
                "task_context": str,
                "session_context": str,
                "query_context": str,
                "few_shots": List[Dict],
                "metadata": Dict
            }
        """

        # 기업 설정 로드
        config = await self.config_loader.load_config(tenant_id)

        # 1. System Context 구성
        system_context = await self._build_system_context(
            config, user_role, self.default_budget.system
        )

        # 2. Task Context 구성 (Intent 기반)
        task_context = await self._build_task_context(
            config, intent, user_role, self.default_budget.task
        )

        # 3. Session Context 구성
        session_ctx = self._build_session_context(
            session_context, self.default_budget.session
        )

        # 4. Query Context 구성 (용어 정규화 포함)
        query_context = await self._build_query_context(
            config, query, self.default_budget.query
        )

        # 5. Few-shot 예시 선택
        few_shots = self._select_few_shots(
            config, intent, user_role, self.default_budget.few_shot
        )

        return {
            "system_context": system_context,
            "task_context": task_context,
            "session_context": session_ctx,
            "query_context": query_context,
            "few_shots": few_shots,
            "metadata": {
                "tenant_id": tenant_id,
                "user_role": user_role,
                "intent": intent,
                "tokens_used": self._estimate_tokens(
                    system_context, task_context, session_ctx,
                    query_context, few_shots
                )
            }
        }

    async def _build_system_context(
        self,
        config: TenantConfig,
        user_role: str,
        max_tokens: int
    ) -> str:
        """System Context 구성"""

        ctx_config = config.context_config.get('system', {})

        # 기업 기본 정보
        company_info = ctx_config.get('company_info', {})
        industry_context = ctx_config.get('industry_context', {})
        production_system = ctx_config.get('production_system', {})

        # 역할별 권한 정보
        role_permissions = self._get_role_permissions(user_role)

        system_prompt = f"""
## 기업 정보
- 산업: {industry_context.get('industry', '제조업')}
- 주요 제품: {', '.join(industry_context.get('main_products', []))}
- 품질 기준: {', '.join(industry_context.get('quality_standards', []))}

## 생산 시스템
- MES: {production_system.get('mes_system', 'N/A')}
- ERP: {production_system.get('erp_system', 'N/A')}
- 운영 패턴: {production_system.get('shift_pattern', 'N/A')}

## 사용자 권한
- 역할: {user_role}
- 데이터 접근: {role_permissions.get('data_scope', 'limited')}
- 기능 접근: {', '.join(role_permissions.get('allowed_features', []))}
"""

        return self._truncate_to_tokens(system_prompt, max_tokens)

    async def _build_task_context(
        self,
        config: TenantConfig,
        intent: str,
        user_role: str,
        max_tokens: int
    ) -> str:
        """Task Context 구성 (Intent 기반)"""

        # 해당 Intent 찾기
        intent_config = None
        for i in config.intents:
            if i.get('intent_code') == intent:
                intent_config = i
                break

        if not intent_config:
            return ""

        task_prompt = f"""
## 작업 유형: {intent_config.get('intent_name', intent)}
카테고리: {intent_config.get('intent_category', 'general')}

## 응답 가이드
- 필요 데이터: {', '.join(intent_config.get('required_data_sources', []))}
- 분석 에이전트: {intent_config.get('agent_type', 'general')}
"""

        return self._truncate_to_tokens(task_prompt, max_tokens)

    def _build_session_context(
        self,
        session_context: Dict[str, Any],
        max_tokens: int
    ) -> str:
        """Session Context 구성"""

        if not session_context:
            return ""

        recent_topics = session_context.get('recent_topics', [])
        referenced_entities = session_context.get('entities', [])

        session_prompt = f"""
## 세션 컨텍스트
- 최근 주제: {', '.join(recent_topics[-3:])}
- 참조 엔티티: {', '.join(referenced_entities[-5:])}
"""

        return self._truncate_to_tokens(session_prompt, max_tokens)

    async def _build_query_context(
        self,
        config: TenantConfig,
        query: str,
        max_tokens: int
    ) -> str:
        """Query Context 구성 (용어 정규화 포함)"""

        # 기업 용어 → 표준 용어 변환
        normalized_query = query
        term_mappings = []

        for company_term, mapping in config.terminology.items():
            if company_term.lower() in query.lower():
                standard = mapping.get('standard', company_term)
                normalized_query = normalized_query.replace(
                    company_term, f"{company_term}({standard})"
                )
                term_mappings.append(f"{company_term} → {standard}")

        query_prompt = f"""
## 원본 질의
{query}

## 용어 매핑
{chr(10).join(term_mappings) if term_mappings else '없음'}
"""

        return self._truncate_to_tokens(query_prompt, max_tokens)

    def _select_few_shots(
        self,
        config: TenantConfig,
        intent: str,
        user_role: str,
        max_tokens: int
    ) -> list:
        """Few-shot 예시 선택"""

        # 해당 Intent의 few-shot
        intent_shots = config.few_shots.get(intent, [])

        if not intent_shots:
            return []

        # 품질 점수순 정렬
        sorted_shots = sorted(
            intent_shots,
            key=lambda x: x.get('score', 0),
            reverse=True
        )

        # 토큰 제한 내에서 선택
        selected = []
        current_tokens = 0

        for shot in sorted_shots:
            shot_tokens = self._estimate_single_tokens(
                shot['query'] + shot['response']
            )

            if current_tokens + shot_tokens <= max_tokens:
                selected.append({
                    'user': shot['query'],
                    'assistant': shot['response']
                })
                current_tokens += shot_tokens

            if len(selected) >= 3:  # 최대 3개
                break

        return selected

    def _get_role_permissions(self, role: str) -> Dict[str, Any]:
        """역할별 권한 정보 반환"""

        permissions = {
            'executive': {
                'data_scope': 'organization_wide',
                'allowed_features': ['전체 대시보드', '경영 분석', '전략 리포트']
            },
            'manager': {
                'data_scope': 'department',
                'allowed_features': ['부서 현황', '성과 분석', '리소스 관리']
            },
            'supervisor': {
                'data_scope': 'team',
                'allowed_features': ['팀 현황', '일일 리포트', '이슈 관리']
            },
            'office_worker': {
                'data_scope': 'assigned_area',
                'allowed_features': ['업무 현황', '기본 조회', '데이터 입력']
            },
            'operator': {
                'data_scope': 'workstation',
                'allowed_features': ['작업 지시', '실적 입력', '이상 신고']
            }
        }

        return permissions.get(role, permissions['operator'])

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """토큰 제한에 맞게 텍스트 자르기"""
        # 간단한 추정: 한글 1자 ≈ 2토큰, 영문 1단어 ≈ 1토큰
        estimated = len(text) * 1.5
        if estimated <= max_tokens:
            return text

        ratio = max_tokens / estimated
        return text[:int(len(text) * ratio)]

    def _estimate_tokens(self, *texts) -> int:
        """토큰 수 추정"""
        total = 0
        for text in texts:
            if isinstance(text, str):
                total += int(len(text) * 1.5)
            elif isinstance(text, list):
                for item in text:
                    total += int(len(str(item)) * 1.5)
        return total

    def _estimate_single_tokens(self, text: str) -> int:
        return int(len(text) * 1.5)
```

### 3.3 Tenant-Aware Prompt Builder

```python
# services/tenant_prompt_builder.py

from typing import Dict, Any, List
from string import Template
import re


class TenantPromptBuilder:
    """
    기업별 프롬프트 빌더
    템플릿 기반 프롬프트 생성 + 역할별 변형
    """

    def __init__(self, config_loader: TenantConfigLoader):
        self.config_loader = config_loader

    async def build_prompt(
        self,
        tenant_id: str,
        prompt_code: str,
        variables: Dict[str, Any],
        user_role: str = None
    ) -> str:
        """
        기업별 프롬프트 생성

        Args:
            tenant_id: 기업 ID
            prompt_code: 프롬프트 코드 (예: 'system_base', 'response_production')
            variables: 템플릿 변수
            user_role: 역할별 변형 적용 시 사용
        """

        config = await self.config_loader.load_config(tenant_id)

        # 프롬프트 템플릿 가져오기
        prompt_info = config.prompts.get(prompt_code)

        if not prompt_info:
            raise ValueError(f"Prompt not found: {prompt_code}")

        template = prompt_info.get('template', '')

        # 역할별 변형 적용
        if user_role:
            template = self._apply_role_variation(template, user_role, config)

        # 변수 치환
        rendered = self._render_template(template, variables)

        return rendered

    async def build_full_prompt(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        intent: str,
        query: str,
        context_builder: TenantContextBuilder,
        session_context: Dict = None
    ) -> Dict[str, Any]:
        """
        완전한 프롬프트 패키지 생성

        Returns:
            {
                "system_prompt": str,
                "user_prompt": str,
                "few_shots": List[Dict],
                "metadata": Dict
            }
        """

        # Context 구성
        context = await context_builder.build_context(
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            intent=intent,
            query=query,
            session_context=session_context
        )

        config = await self.config_loader.load_config(tenant_id)

        # System Prompt 구성
        system_vars = {
            'system_context': context['system_context'],
            'task_context': context['task_context'],
            'user_role': user_role
        }

        system_prompt = await self.build_prompt(
            tenant_id=tenant_id,
            prompt_code='system_base',
            variables=system_vars,
            user_role=user_role
        )

        # User Prompt 구성
        user_prompt = f"""
{context['session_context']}

{context['query_context']}

질문: {query}
"""

        # 응답 포맷 가이드 추가
        response_format = self._get_response_format(config, intent, user_role)
        if response_format:
            user_prompt += f"\n\n응답 형식:\n{response_format}"

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "few_shots": context['few_shots'],
            "metadata": {
                **context['metadata'],
                "prompt_version": config.prompts.get('system_base', {}).get('version', '1.0')
            }
        }

    def _render_template(self, template: str, variables: Dict[str, Any]) -> str:
        """템플릿 변수 치환"""

        # {{variable}} 형식 처리
        pattern = r'\{\{(\w+)\}\}'

        def replace(match):
            var_name = match.group(1)
            value = variables.get(var_name, '')

            # 리스트는 쉼표로 연결
            if isinstance(value, list):
                return ', '.join(str(v) for v in value)

            return str(value)

        return re.sub(pattern, replace, template)

    def _apply_role_variation(
        self,
        template: str,
        user_role: str,
        config: TenantConfig
    ) -> str:
        """역할별 프롬프트 변형 적용"""

        # 역할별 강조점 추가
        role_emphasis = {
            'executive': "\n\n## 경영진 관점\n- 전략적 시사점 중심\n- KPI 영향도 명시\n- 의사결정 지원 정보 제공",
            'manager': "\n\n## 관리자 관점\n- 부서 성과 연계\n- 리소스 활용 현황\n- 개선 액션 아이템 제시",
            'supervisor': "\n\n## 현장 감독 관점\n- 즉시 조치 가능한 정보\n- 팀 성과 및 이슈\n- 일일 운영 중심",
            'office_worker': "\n\n## 사무직 관점\n- 담당 업무 관련 정보\n- 처리 현황 및 진행 상태",
            'operator': "\n\n## 현장 작업자 관점\n- 작업 지시 명확화\n- 안전 주의사항\n- 간결한 정보 제공"
        }

        emphasis = role_emphasis.get(user_role, '')

        return template + emphasis

    def _get_response_format(
        self,
        config: TenantConfig,
        intent: str,
        user_role: str
    ) -> str:
        """응답 포맷 가이드 생성"""

        # Intent 카테고리로 포맷 찾기
        intent_info = None
        for i in config.intents:
            if i.get('intent_code') == intent:
                intent_info = i
                break

        if not intent_info:
            return None

        category = intent_info.get('intent_category', 'general')

        # 해당 카테고리의 포맷 찾기
        for format_code, format_info in config.response_formats.items():
            if category in format_code:
                template = format_info.get('template', '')

                # 역할별 변형 적용
                role_vars = format_info.get('role_variations', {}).get(user_role, {})
                if role_vars:
                    template += f"\n\n[{user_role} 특화]\n"
                    template += f"- 포커스: {', '.join(role_vars.get('focus', []))}\n"
                    template += f"- 상세도: {role_vars.get('detail_level', 'standard')}"

                return template

        return None
```

---

## 4. 기업 온보딩 프로세스

### 4.1 온보딩 단계 개요

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      기업 온보딩 프로세스 (4주)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Week 1: 사전 분석                                                       │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │ □ 기업 현황 파악 (산업, 규모, 시스템)                          │       │
│  │ □ 핵심 업무 프로세스 분석                                     │       │
│  │ □ 사용자 역할 및 권한 체계 정의                               │       │
│  │ □ 데이터 연동 범위 확정                                       │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                              ▼                                          │
│  Week 2: 기본 설정                                                       │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │ □ Tenant 생성 및 기본 권한 설정                               │       │
│  │ □ Context 기본 정보 입력                                      │       │
│  │ □ 표준 Intent 활성화/비활성화                                 │       │
│  │ □ 기업 용어 매핑 초기 등록                                    │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                              ▼                                          │
│  Week 3: 맞춤 설정                                                       │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │ □ 커스텀 Intent 추가                                          │       │
│  │ □ Few-shot 예시 작성                                          │       │
│  │ □ 프롬프트 템플릿 수정                                        │       │
│  │ □ 응답 포맷 커스터마이징                                      │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                              ▼                                          │
│  Week 4: 검증 및 배포                                                    │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │ □ 파일럿 사용자 테스트                                        │       │
│  │ □ 응답 품질 검증                                              │       │
│  │ □ 성능 튜닝                                                   │       │
│  │ □ 전체 배포 및 교육                                           │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 상세 온보딩 체크리스트

#### Phase 1: 사전 분석 (Week 1)

```yaml
# onboarding/phase1_analysis_checklist.yaml

phase: "사전 분석"
duration: "1주"
owner: "컨설턴트 + 고객 담당자"

tasks:
  - id: "P1-01"
    name: "기업 기본 정보 수집"
    description: "기업의 산업, 규모, 조직구조 파악"
    deliverables:
      - 기업 프로필 문서
      - 조직도
      - 시스템 현황표
    inputs:
      - company_name: "회사명"
      - industry: "산업군 (자동차, 전자, 화학 등)"
      - employee_count: "직원 수"
      - annual_revenue: "연매출 규모"
      - manufacturing_type: "생산 유형 (연속/이산/배치)"

  - id: "P1-02"
    name: "IT 시스템 현황 분석"
    description: "연동 대상 시스템 파악 및 데이터 흐름 분석"
    deliverables:
      - 시스템 연동 다이어그램
      - 데이터 흐름도
      - API 명세 목록
    inputs:
      - mes_system: "MES 시스템명 및 버전"
      - erp_system: "ERP 시스템명"
      - scada_plc: "SCADA/PLC 현황"
      - existing_analytics: "기존 분석 도구"

  - id: "P1-03"
    name: "핵심 업무 프로세스 분석"
    description: "AI 어시스턴트가 지원할 핵심 업무 식별"
    deliverables:
      - 업무 프로세스 맵
      - 사용자 여정 문서
      - 핵심 질의 목록
    activities:
      - 현장 인터뷰 (역할별 3-5명)
      - 업무 관찰 (1-2일)
      - 기존 보고서/대시보드 분석

  - id: "P1-04"
    name: "사용자 역할 정의"
    description: "사용자 역할 체계 및 권한 요구사항 정의"
    deliverables:
      - 역할 정의서
      - 권한 매트릭스
      - 조직-역할 매핑
    role_template:
      - role_name: "역할명"
      - role_level: "권한 레벨 (1-5)"
      - data_access: "접근 가능 데이터"
      - features: "사용 가능 기능"
      - user_count: "예상 사용자 수"
```

#### Phase 2: 기본 설정 (Week 2)

```yaml
# onboarding/phase2_basic_setup.yaml

phase: "기본 설정"
duration: "1주"
owner: "플랫폼 관리자 + 컨설턴트"

tasks:
  - id: "P2-01"
    name: "Tenant 생성"
    description: "기업 전용 테넌트 환경 구성"
    actions:
      - tenant 레코드 생성
      - 관리자 계정 설정
      - 기본 설정 파일 복사
    sql_example: |
      INSERT INTO tenants (id, name, industry, config)
      VALUES (
        gen_random_uuid(),
        '{{company_name}}',
        '{{industry}}',
        '{
          "timezone": "Asia/Seoul",
          "language": "ko",
          "data_retention_days": 365
        }'
      );

  - id: "P2-02"
    name: "권한 체계 설정"
    description: "역할 및 권한 구조 구성"
    actions:
      - 역할 템플릿 적용
      - 커스텀 역할 추가
      - 조직 단위 설정
    reference: "E-5_Multi_Tenant_Authorization.md"

  - id: "P2-03"
    name: "기본 Context 설정"
    description: "기업 기본 정보를 Context로 등록"
    config_items:
      system_context:
        - company_info: "기업 기본 정보"
        - industry_context: "산업 특화 정보"
        - production_system: "생산 시스템 정보"
        - quality_standards: "품질 기준"
      task_context:
        - kpi_definitions: "핵심 KPI 정의"
        - reporting_cycles: "보고 주기"

  - id: "P2-04"
    name: "표준 Intent 활성화"
    description: "Base Intent 중 사용할 항목 선택"
    base_intents:
      production:
        - production_status: "생산 현황 조회"
        - line_efficiency: "라인 효율 분석"
        - schedule_inquiry: "생산 계획 조회"
      quality:
        - quality_status: "품질 현황 조회"
        - defect_analysis: "불량 분석"
        - spc_monitoring: "SPC 모니터링"
      equipment:
        - equipment_status: "설비 상태 조회"
        - maintenance_schedule: "보전 일정"
        - alarm_history: "알람 이력"
```

#### Phase 3: 맞춤 설정 (Week 3)

```yaml
# onboarding/phase3_customization.yaml

phase: "맞춤 설정"
duration: "1주"
owner: "컨설턴트 + 고객 현업"

tasks:
  - id: "P3-01"
    name: "기업 용어 매핑"
    description: "기업 고유 용어를 표준 용어로 매핑"
    process:
      1. 현업 인터뷰로 용어 수집
      2. 표준 용어 매칭
      3. 동의어/약어 등록
      4. 검증 및 보완
    example_mappings:
      - company_term: "1공장"
        standard_term: "Factory A"
        synonyms: ["일공", "메인공장"]
      - company_term: "양품률"
        standard_term: "First Pass Yield"
        synonyms: ["FPY", "직행률"]

  - id: "P3-02"
    name: "커스텀 Intent 추가"
    description: "기업 특화 질의 유형 정의"
    template:
      intent_code: "고유 코드"
      intent_name: "표시 이름"
      category: "분류"
      example_queries:
        - "예시 질문 1"
        - "예시 질문 2"
      keywords: ["키워드1", "키워드2"]
      agent_type: "처리 에이전트"
      min_role_level: "최소 권한 레벨"

  - id: "P3-03"
    name: "Few-shot 예시 작성"
    description: "Intent별 모범 응답 예시 작성"
    guidelines:
      - 실제 업무 상황 반영
      - 역할별 적절한 상세도
      - 기업 용어 사용
      - 포맷 일관성 유지
    quality_criteria:
      - 정확성: "데이터/수치의 정확성"
      - 완결성: "필요 정보 포함 여부"
      - 실용성: "실제 의사결정 지원 가능성"

  - id: "P3-04"
    name: "응답 포맷 커스터마이징"
    description: "기업 선호 응답 형식 설정"
    format_options:
      table_style: "테이블 사용 여부/스타일"
      chart_preference: "차트 포함 여부"
      summary_position: "요약 위치 (상단/하단)"
      recommendation_style: "권고사항 표현 방식"
      language_formality: "경어체/평어체"
```

#### Phase 4: 검증 및 배포 (Week 4)

```yaml
# onboarding/phase4_validation.yaml

phase: "검증 및 배포"
duration: "1주"
owner: "QA + 고객 현업"

tasks:
  - id: "P4-01"
    name: "파일럿 테스트"
    description: "선별된 사용자 그룹으로 테스트"
    test_plan:
      pilot_users: "역할별 2-3명씩 (총 10-15명)"
      duration: "3일"
      scenarios:
        - 일상 업무 질의
        - 복잡한 분석 요청
        - 권한 경계 테스트
        - 오류 상황 테스트

  - id: "P4-02"
    name: "응답 품질 검증"
    description: "AI 응답 품질 평가 및 개선"
    evaluation_criteria:
      accuracy: "정보 정확성 (목표: 95%+)"
      relevance: "질문 관련성 (목표: 90%+)"
      completeness: "답변 완결성 (목표: 85%+)"
      format: "포맷 적절성 (목표: 90%+)"
    improvement_process:
      1. 문제 응답 수집
      2. 원인 분석 (Context/Intent/Prompt)
      3. 설정 수정
      4. 재테스트

  - id: "P4-03"
    name: "성능 최적화"
    description: "응답 속도 및 리소스 최적화"
    targets:
      response_time: "< 3초 (90th percentile)"
      token_efficiency: "평균 토큰 < 2000"
    optimization_areas:
      - Context 압축
      - Few-shot 선별
      - 캐싱 전략

  - id: "P4-04"
    name: "전체 배포"
    description: "전사 배포 및 사용자 교육"
    rollout_plan:
      wave_1: "관리자 및 파워유저 (Day 1-2)"
      wave_2: "부서별 확대 (Day 3-5)"
      wave_3: "전사 오픈 (Day 6-7)"
    training:
      - 사용자 가이드 배포
      - 온라인 교육 세션
      - FAQ 및 도움말 제공
```

---

## 5. 관리자 인터페이스

### 5.1 Admin UI 구성

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        기업 커스터마이징 관리 콘솔                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │   Context   │ │   Intent    │ │   용어      │ │  프롬프트   │       │
│  │    설정     │ │    관리     │ │   매핑      │ │    관리     │       │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │                     주요 기능 영역                            │       │
│  ├─────────────────────────────────────────────────────────────┤       │
│  │                                                              │       │
│  │  📊 Context 설정                                             │       │
│  │  ├── System Context (기업 기본 정보)                         │       │
│  │  ├── Task Context (업무별 설정)                              │       │
│  │  └── 토큰 예산 관리                                          │       │
│  │                                                              │       │
│  │  🎯 Intent 관리                                              │       │
│  │  ├── 표준 Intent 활성화/비활성화                             │       │
│  │  ├── 커스텀 Intent 추가/수정                                 │       │
│  │  └── Intent-권한 매핑                                        │       │
│  │                                                              │       │
│  │  📝 용어 매핑                                                │       │
│  │  ├── 용어 등록/수정/삭제                                     │       │
│  │  ├── 동의어/약어 관리                                        │       │
│  │  └── 일괄 업로드 (Excel)                                     │       │
│  │                                                              │       │
│  │  💬 프롬프트 관리                                            │       │
│  │  ├── 템플릿 편집기                                           │       │
│  │  ├── 변수 관리                                               │       │
│  │  ├── 버전 이력                                               │       │
│  │  └── A/B 테스트 설정                                         │       │
│  │                                                              │       │
│  │  📋 Few-shot 관리                                            │       │
│  │  ├── 예시 등록/수정                                          │       │
│  │  ├── 품질 평가                                               │       │
│  │  └── 자동 추천                                               │       │
│  │                                                              │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  🔍 테스트 & 미리보기                                        │       │
│  │  ├── 실시간 프롬프트 미리보기                                │       │
│  │  ├── 테스트 질의 실행                                        │       │
│  │  └── 역할별 응답 비교                                        │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Admin API Endpoints

```python
# api/admin/customization.py

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/admin/customization", tags=["Customization"])


# ============================================
# Context 설정 API
# ============================================

class ContextConfigCreate(BaseModel):
    context_layer: str  # system, task, session, query
    config_key: str
    config_value: dict
    priority: int = 100
    max_tokens: int = 500
    activation_conditions: dict = {}


class ContextConfigUpdate(BaseModel):
    config_value: Optional[dict]
    priority: Optional[int]
    max_tokens: Optional[int]
    is_active: Optional[bool]


@router.get("/{tenant_id}/context")
async def list_context_configs(
    tenant_id: str,
    layer: Optional[str] = None,
    current_user = Depends(get_admin_user)
):
    """기업별 Context 설정 목록 조회"""
    pass


@router.post("/{tenant_id}/context")
async def create_context_config(
    tenant_id: str,
    config: ContextConfigCreate,
    current_user = Depends(get_admin_user)
):
    """Context 설정 추가"""
    pass


@router.put("/{tenant_id}/context/{config_id}")
async def update_context_config(
    tenant_id: str,
    config_id: str,
    config: ContextConfigUpdate,
    current_user = Depends(get_admin_user)
):
    """Context 설정 수정"""
    pass


# ============================================
# Intent 관리 API
# ============================================

class IntentCreate(BaseModel):
    intent_code: str
    intent_name: str
    intent_category: str
    description: Optional[str]
    example_queries: List[str] = []
    keywords: List[str] = []
    patterns: List[str] = []
    agent_type: str
    min_role_level: int = 5
    allowed_roles: List[str] = []


@router.get("/{tenant_id}/intents")
async def list_intents(
    tenant_id: str,
    category: Optional[str] = None,
    include_base: bool = True,
    current_user = Depends(get_admin_user)
):
    """기업별 Intent 목록 조회"""
    pass


@router.post("/{tenant_id}/intents")
async def create_intent(
    tenant_id: str,
    intent: IntentCreate,
    current_user = Depends(get_admin_user)
):
    """커스텀 Intent 추가"""
    pass


@router.put("/{tenant_id}/intents/{intent_id}")
async def update_intent(
    tenant_id: str,
    intent_id: str,
    intent: IntentCreate,
    current_user = Depends(get_admin_user)
):
    """Intent 수정"""
    pass


@router.post("/{tenant_id}/intents/{intent_code}/toggle")
async def toggle_base_intent(
    tenant_id: str,
    intent_code: str,
    is_active: bool,
    current_user = Depends(get_admin_user)
):
    """기본 Intent 활성화/비활성화"""
    pass


# ============================================
# 용어 매핑 API
# ============================================

class TerminologyCreate(BaseModel):
    company_term: str
    standard_term: str
    term_category: Optional[str]
    synonyms: List[str] = []
    abbreviations: List[str] = []
    usage_context: Optional[str]


@router.get("/{tenant_id}/terminology")
async def list_terminology(
    tenant_id: str,
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user = Depends(get_admin_user)
):
    """용어 매핑 목록 조회"""
    pass


@router.post("/{tenant_id}/terminology")
async def create_terminology(
    tenant_id: str,
    term: TerminologyCreate,
    current_user = Depends(get_admin_user)
):
    """용어 매핑 추가"""
    pass


@router.post("/{tenant_id}/terminology/bulk")
async def bulk_upload_terminology(
    tenant_id: str,
    file: UploadFile,  # Excel/CSV 파일
    current_user = Depends(get_admin_user)
):
    """용어 매핑 일괄 업로드"""
    pass


# ============================================
# 프롬프트 관리 API
# ============================================

class PromptCreate(BaseModel):
    prompt_code: str
    prompt_name: str
    prompt_type: str  # system, task, response_format
    prompt_template: str
    variables: List[str] = []
    ab_test_group: Optional[str]
    ab_test_weight: float = 1.0


@router.get("/{tenant_id}/prompts")
async def list_prompts(
    tenant_id: str,
    prompt_type: Optional[str] = None,
    current_user = Depends(get_admin_user)
):
    """프롬프트 템플릿 목록 조회"""
    pass


@router.post("/{tenant_id}/prompts")
async def create_prompt(
    tenant_id: str,
    prompt: PromptCreate,
    current_user = Depends(get_admin_user)
):
    """프롬프트 템플릿 생성"""
    pass


@router.get("/{tenant_id}/prompts/{prompt_id}/versions")
async def list_prompt_versions(
    tenant_id: str,
    prompt_id: str,
    current_user = Depends(get_admin_user)
):
    """프롬프트 버전 이력 조회"""
    pass


# ============================================
# Few-shot 관리 API
# ============================================

class FewShotCreate(BaseModel):
    intent_code: str
    user_query: str
    assistant_response: str
    quality_score: float = 0.8
    tags: List[str] = []
    applicable_roles: List[str] = []


@router.get("/{tenant_id}/few-shots")
async def list_few_shots(
    tenant_id: str,
    intent_code: Optional[str] = None,
    min_quality: float = 0.0,
    current_user = Depends(get_admin_user)
):
    """Few-shot 예시 목록 조회"""
    pass


@router.post("/{tenant_id}/few-shots")
async def create_few_shot(
    tenant_id: str,
    few_shot: FewShotCreate,
    current_user = Depends(get_admin_user)
):
    """Few-shot 예시 추가"""
    pass


@router.post("/{tenant_id}/few-shots/{few_shot_id}/evaluate")
async def evaluate_few_shot(
    tenant_id: str,
    few_shot_id: str,
    score: float,
    feedback: Optional[str],
    current_user = Depends(get_admin_user)
):
    """Few-shot 품질 평가"""
    pass


# ============================================
# 테스트 API
# ============================================

class TestQueryRequest(BaseModel):
    query: str
    user_role: str
    intent_override: Optional[str]


@router.post("/{tenant_id}/test/preview-prompt")
async def preview_prompt(
    tenant_id: str,
    request: TestQueryRequest,
    current_user = Depends(get_admin_user)
):
    """프롬프트 미리보기 (LLM 호출 없이)"""
    pass


@router.post("/{tenant_id}/test/execute")
async def execute_test_query(
    tenant_id: str,
    request: TestQueryRequest,
    current_user = Depends(get_admin_user)
):
    """테스트 질의 실행"""
    pass


@router.post("/{tenant_id}/test/compare-roles")
async def compare_role_responses(
    tenant_id: str,
    query: str,
    roles: List[str],
    current_user = Depends(get_admin_user)
):
    """역할별 응답 비교"""
    pass
```

---

## 6. 운영 가이드

### 6.1 일상 운영 체크리스트

```yaml
# operations/daily_checklist.yaml

daily_tasks:
  - id: "D-01"
    name: "응답 품질 모니터링"
    frequency: "매일"
    description: "AI 응답 품질 지표 확인"
    metrics:
      - 사용자 만족도 (thumbs up/down)
      - 응답 정확도 (샘플링 검증)
      - 평균 응답 시간
    threshold:
      satisfaction: "> 85%"
      accuracy: "> 90%"
      response_time: "< 3초"

  - id: "D-02"
    name: "실패 쿼리 분석"
    frequency: "매일"
    description: "Intent 분류 실패 또는 낮은 신뢰도 쿼리 분석"
    actions:
      - 실패 쿼리 목록 확인
      - 패턴 분석
      - Intent/키워드 보완 검토

weekly_tasks:
  - id: "W-01"
    name: "Few-shot 품질 검토"
    frequency: "주 1회"
    description: "사용 빈도 높은 Few-shot 품질 재검토"

  - id: "W-02"
    name: "용어 매핑 검토"
    frequency: "주 1회"
    description: "새로운 용어 또는 누락된 매핑 확인"

  - id: "W-03"
    name: "사용 통계 리뷰"
    frequency: "주 1회"
    description: "Intent별, 역할별 사용 패턴 분석"

monthly_tasks:
  - id: "M-01"
    name: "프롬프트 성능 분석"
    frequency: "월 1회"
    description: "프롬프트 버전별 성능 비교"

  - id: "M-02"
    name: "A/B 테스트 결과 검토"
    frequency: "월 1회"
    description: "진행 중인 A/B 테스트 결과 분석 및 적용"

  - id: "M-03"
    name: "토큰 사용량 최적화"
    frequency: "월 1회"
    description: "Context/Few-shot 토큰 효율성 검토"
```

### 6.2 트러블슈팅 가이드

```yaml
# operations/troubleshooting.yaml

issues:
  - symptom: "Intent 분류 정확도 저하"
    possible_causes:
      - 새로운 용어/표현 등장
      - 기존 키워드 중복
      - 예시 쿼리 부족
    diagnosis:
      - 실패 쿼리 로그 분석
      - 키워드 충돌 검사
      - 신뢰도 분포 확인
    solutions:
      - 키워드/패턴 추가
      - 예시 쿼리 보강
      - Intent 세분화 검토

  - symptom: "응답 품질 불만족"
    possible_causes:
      - Context 정보 부족
      - Few-shot 품질 낮음
      - 프롬프트 지시 모호
    diagnosis:
      - 실제 프롬프트 확인
      - Few-shot 적합성 검토
      - 역할별 응답 비교
    solutions:
      - Context 정보 보강
      - Few-shot 교체/추가
      - 프롬프트 명확화

  - symptom: "응답 시간 지연"
    possible_causes:
      - Context 토큰 과다
      - Few-shot 과다 선택
      - 복잡한 Intent 처리
    diagnosis:
      - 토큰 사용량 분석
      - 처리 단계별 시간 측정
    solutions:
      - Context 압축
      - Few-shot 수 제한
      - 캐싱 전략 적용

  - symptom: "권한 오류 발생"
    possible_causes:
      - 역할-Intent 매핑 오류
      - 데이터 범위 설정 오류
      - 조직 구조 변경 미반영
    diagnosis:
      - 권한 설정 확인
      - 사용자 역할 매핑 확인
      - 감사 로그 분석
    solutions:
      - Intent 권한 재설정
      - 역할 데이터 범위 수정
      - 조직 구조 동기화
```

### 6.3 버전 관리 정책

```yaml
# operations/versioning_policy.yaml

versioning:
  prompt_versions:
    format: "major.minor.patch"
    rules:
      major: "프롬프트 구조 변경"
      minor: "내용 수정 (로직 변경)"
      patch: "오타/문구 수정"
    retention: "최근 10개 버전 유지"
    rollback: "이전 버전 즉시 롤백 가능"

  config_versions:
    tracking: "모든 변경 이력 저장"
    audit: "변경자, 시간, 변경 내용 기록"
    comparison: "버전간 diff 제공"

  base_template_sync:
    notification: "Base 템플릿 업데이트 시 알림"
    review: "Override 영향 분석"
    merge_strategy: "수동 검토 후 적용"

change_management:
  approval_required:
    - 프롬프트 major 변경
    - Intent 추가/삭제
    - 권한 체계 변경

  testing_required:
    - 모든 프롬프트 변경
    - 새로운 Intent 추가
    - Few-shot 대량 변경

  documentation_required:
    - 모든 변경사항
    - 변경 사유 기록
    - 영향 범위 명시
```

---

## 7. 성능 최적화

### 7.1 캐싱 전략

```python
# services/caching_strategy.py

from typing import Dict, Any
from datetime import timedelta
import redis
import hashlib
import json


class CustomizationCache:
    """커스터마이징 설정 캐싱"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = "tenant_config"

        # TTL 설정
        self.ttl_config = {
            'context': timedelta(minutes=5),
            'intents': timedelta(minutes=10),
            'terminology': timedelta(minutes=30),
            'prompts': timedelta(minutes=5),
            'few_shots': timedelta(minutes=15)
        }

    def _cache_key(self, tenant_id: str, config_type: str) -> str:
        return f"{self.prefix}:{tenant_id}:{config_type}"

    async def get_cached_config(
        self,
        tenant_id: str,
        config_type: str
    ) -> Dict[str, Any]:
        """캐시된 설정 조회"""

        key = self._cache_key(tenant_id, config_type)
        cached = self.redis.get(key)

        if cached:
            return json.loads(cached)

        return None

    async def set_cached_config(
        self,
        tenant_id: str,
        config_type: str,
        config: Dict[str, Any]
    ):
        """설정 캐싱"""

        key = self._cache_key(tenant_id, config_type)
        ttl = self.ttl_config.get(config_type, timedelta(minutes=5))

        self.redis.setex(
            key,
            ttl,
            json.dumps(config, ensure_ascii=False)
        )

    async def invalidate_config(
        self,
        tenant_id: str,
        config_type: str = None
    ):
        """캐시 무효화"""

        if config_type:
            key = self._cache_key(tenant_id, config_type)
            self.redis.delete(key)
        else:
            # 해당 테넌트의 모든 캐시 삭제
            pattern = f"{self.prefix}:{tenant_id}:*"
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)

    def _hash_query(self, query: str, context: Dict) -> str:
        """쿼리+컨텍스트 해시 생성"""
        content = f"{query}:{json.dumps(context, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()


class ResponseCache:
    """AI 응답 캐싱 (동일 질의 패턴)"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = "response_cache"
        self.ttl = timedelta(hours=1)

    async def get_cached_response(
        self,
        tenant_id: str,
        query_hash: str,
        user_role: str
    ) -> str:
        """캐시된 응답 조회"""

        key = f"{self.prefix}:{tenant_id}:{user_role}:{query_hash}"
        return self.redis.get(key)

    async def cache_response(
        self,
        tenant_id: str,
        query_hash: str,
        user_role: str,
        response: str,
        ttl: timedelta = None
    ):
        """응답 캐싱"""

        key = f"{self.prefix}:{tenant_id}:{user_role}:{query_hash}"
        self.redis.setex(
            key,
            ttl or self.ttl,
            response
        )
```

### 7.2 토큰 최적화

```python
# services/token_optimizer.py

from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class TokenBudget:
    """토큰 예산 설정"""
    system_context: int = 500
    task_context: int = 400
    session_context: int = 300
    query_context: int = 200
    few_shot_per_example: int = 200
    max_few_shots: int = 3
    total_limit: int = 2000
    reserve: int = 200  # 안전 마진


class TokenOptimizer:
    """토큰 사용량 최적화"""

    def __init__(self, budget: TokenBudget = None):
        self.budget = budget or TokenBudget()

    def optimize_context(
        self,
        context: Dict[str, Any],
        current_usage: int
    ) -> Dict[str, Any]:
        """컨텍스트 최적화"""

        if current_usage <= self.budget.total_limit - self.budget.reserve:
            return context

        optimized = {}

        # 우선순위별 할당
        priority_order = [
            ('system_context', self.budget.system_context),
            ('query_context', self.budget.query_context),
            ('task_context', self.budget.task_context),
            ('session_context', self.budget.session_context)
        ]

        remaining = self.budget.total_limit - self.budget.reserve

        for ctx_type, max_tokens in priority_order:
            if ctx_type in context:
                allocated = min(max_tokens, remaining)
                optimized[ctx_type] = self._truncate_text(
                    context[ctx_type],
                    allocated
                )
                remaining -= allocated

        return optimized

    def optimize_few_shots(
        self,
        few_shots: List[Dict],
        available_tokens: int
    ) -> List[Dict]:
        """Few-shot 최적화"""

        if not few_shots:
            return []

        optimized = []
        used_tokens = 0

        for shot in few_shots[:self.budget.max_few_shots]:
            shot_tokens = self._estimate_tokens(
                shot['user'] + shot['assistant']
            )

            if used_tokens + shot_tokens <= available_tokens:
                optimized.append(shot)
                used_tokens += shot_tokens
            else:
                # 마지막 가능한 shot 압축 시도
                remaining = available_tokens - used_tokens
                if remaining > 100:  # 최소 토큰
                    compressed = self._compress_few_shot(shot, remaining)
                    if compressed:
                        optimized.append(compressed)
                break

        return optimized

    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """토큰 제한에 맞게 텍스트 자르기"""
        estimated = self._estimate_tokens(text)

        if estimated <= max_tokens:
            return text

        ratio = max_tokens / estimated
        return text[:int(len(text) * ratio * 0.9)]  # 10% 마진

    def _compress_few_shot(
        self,
        shot: Dict,
        max_tokens: int
    ) -> Dict:
        """Few-shot 압축"""

        # 응답 부분만 압축
        response = shot['assistant']
        user = shot['user']

        user_tokens = self._estimate_tokens(user)
        response_budget = max_tokens - user_tokens - 10

        if response_budget < 50:
            return None

        compressed_response = self._truncate_text(response, response_budget)

        return {
            'user': user,
            'assistant': compressed_response + "..."
        }

    def _estimate_tokens(self, text: str) -> int:
        """토큰 수 추정 (한글: 2, 영문: 0.75)"""
        korean_chars = sum(1 for c in text if ord('가') <= ord(c) <= ord('힣'))
        other_chars = len(text) - korean_chars

        return int(korean_chars * 2 + other_chars * 0.75)
```

---

## 8. 부록

### 8.1 Base Template 예시

```yaml
# config/defaults/context_base.yaml

system:
  company_info:
    name: "{{company_name}}"
    timezone: "Asia/Seoul"
    language: "ko"

  industry_context:
    industry: "manufacturing"
    quality_standards:
      - "ISO 9001"

  production_system:
    shift_pattern: "standard"

task:
  default_kpis:
    - name: "OEE"
      threshold: 85
    - name: "불량률"
      threshold: 0.5
```

```yaml
# config/defaults/intents_base.yaml

intents:
  - intent_code: "production_status"
    intent_name: "생산 현황 조회"
    intent_category: "production"
    example_queries:
      - "오늘 생산 현황 어때?"
      - "현재 생산량 알려줘"
    keywords:
      - "생산"
      - "현황"
      - "생산량"
    agent_type: "production_analytics"
    min_role_level: 5

  - intent_code: "quality_status"
    intent_name: "품질 현황 조회"
    intent_category: "quality"
    example_queries:
      - "오늘 불량률 어때?"
      - "품질 현황 보여줘"
    keywords:
      - "품질"
      - "불량"
      - "불량률"
    agent_type: "quality_analytics"
    min_role_level: 4
```

### 8.2 커스터마이징 예시: A자동차부품

```yaml
# examples/tenant_a_automotive.yaml

tenant_info:
  name: "A자동차부품(주)"
  industry: "automotive_parts"

context_overrides:
  system:
    industry_context:
      industry: "automotive_parts"
      main_products:
        - "엔진 부품"
        - "변속기 부품"
        - "브레이크 시스템"
      quality_standards:
        - "IATF 16949"
        - "ISO 9001"
        - "VDA 6.3"
      main_customers:
        - "현대자동차"
        - "기아자동차"
        - "GM"

    production_system:
      mes_system: "SAP ME"
      erp_system: "SAP S/4HANA"
      shift_pattern: "3교대"
      lines:
        - name: "SMT-1"
          type: "SMT"
          capacity: 5000
        - name: "SMT-2"
          type: "SMT"
          capacity: 4500

custom_intents:
  - intent_code: "customer_claim_analysis"
    intent_name: "고객 클레임 분석"
    intent_category: "quality"
    example_queries:
      - "현대차 클레임 현황 알려줘"
      - "이번 달 고객 불만 분석해줘"
    agent_type: "crm_analytics"
    min_role_level: 3

terminology:
  - company_term: "현대향"
    standard_term: "현대자동차 납품용"
    synonyms: ["HMC향", "현대차용"]

  - company_term: "인라인"
    standard_term: "생산라인 내 공정"
    synonyms: ["라인 내", "인라인검사"]

few_shots:
  production_status:
    - user: "SMT-1 오늘 실적 어때?"
      assistant: |
        ## SMT-1 라인 금일 생산 실적

        | 항목 | 실적 | 목표 | 달성률 |
        |------|------|------|--------|
        | 생산량 | 4,850개 | 5,000개 | 97.0% |
        | 불량률 | 0.08% | 0.10% | ✅ 양호 |
        | OEE | 89.2% | 85.0% | 104.9% |

        **특이사항**: 09:30 자재 대기로 12분 정지 발생
```

### 8.3 마이그레이션 가이드

```yaml
# migration/upgrade_guide.yaml

from_version: "1.0"
to_version: "2.0"

breaking_changes:
  - change: "context_config 테이블 구조 변경"
    action: "마이그레이션 스크립트 실행 필요"
    script: "migrations/v2_context_config.sql"

  - change: "Intent 권한 체계 변경"
    action: "역할 매핑 재설정 필요"
    script: "migrations/v2_intent_permissions.sql"

migration_steps:
  1:
    name: "백업"
    command: "pg_dump tenant_db > backup_v1.sql"

  2:
    name: "스키마 마이그레이션"
    command: "psql -f migrations/v2_schema.sql"

  3:
    name: "데이터 마이그레이션"
    command: "python migrate_data.py --from 1.0 --to 2.0"

  4:
    name: "캐시 초기화"
    command: "redis-cli FLUSHDB"

  5:
    name: "검증"
    command: "python verify_migration.py"

rollback:
  command: "psql -f backup_v1.sql"
  note: "데이터 마이그레이션 전 반드시 백업 확인"
```

---

## 9. 문서 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 1.0 | 2024-01 | AI Factory Team | 초기 작성 |
| 2.0 | 2025-12-16 | AI Factory Team | V7 Intent + Orchestrator 커스터마이징 확장: V7 Intent 14개 체계 커스텀 매핑 가이드, Orchestrator Plan 템플릿 커스터마이징, 15노드 타입별 기업 설정, Claude 모델 계열 (Haiku/Sonnet/Opus) 기업별 할당, Legacy Intent 30개→V7 Intent 14개 마이그레이션 가이드 |

---

## 10. 관련 문서

- [E-3. Intent Router 프로토타입](./E-3_Intent_Router_Prototype.md)
- [E-5. Multi-Tenant 권한관리 설계서](./E-5_Multi_Tenant_Authorization.md)
- [B-6. AI Agent 아키텍처](./B-6_AI_Agent_Architecture_Prompt_Spec.md)
