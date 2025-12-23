# ===================================================
# TriFlow AI - Intent Routing Rules (V7)
# V7 Intent 체계 (14개) + Legacy Intent 하위호환
# ===================================================
"""
라우팅 규칙 정의 파일 (V7 체계)

V7 Intent 체계:
- 정보 조회 (4개): CHECK, TREND, COMPARE, RANK
- 분석 (4개): FIND_CAUSE, DETECT_ANOMALY, PREDICT, WHAT_IF
- 액션 (2개): REPORT, NOTIFY
- 대화 제어 (4개): CONTINUE, CLARIFY, STOP, SYSTEM

라우팅 대상:
- DATA_LAYER: CHECK, TREND
- JUDGMENT_ENGINE: COMPARE, RANK, FIND_CAUSE, PREDICT, WHAT_IF
- RULE_ENGINE: DETECT_ANOMALY
- BI_GUIDE: REPORT
- WORKFLOW_GUIDE: NOTIFY
- CONTEXT_DEPENDENT: CONTINUE, STOP
- ASK_BACK: CLARIFY
- DIRECT_RESPONSE: SYSTEM
"""

from typing import Dict, List, Any, Optional
from enum import Enum


class V7Intent(str, Enum):
    """V7 Intent 타입 (14개)"""
    # 정보 조회 (Information) - 4개
    CHECK = "CHECK"              # 단순 현재 상태/수치 조회
    TREND = "TREND"              # 시간에 따른 변화/추이 조회
    COMPARE = "COMPARE"          # 두 개 이상 대상 비교
    RANK = "RANK"                # 순위/최대/최소 조회

    # 분석 (Analysis) - 4개
    FIND_CAUSE = "FIND_CAUSE"    # 원인 분석 (왜?)
    DETECT_ANOMALY = "DETECT_ANOMALY"  # 이상/문제 탐지
    PREDICT = "PREDICT"          # 미래 예측/전망
    WHAT_IF = "WHAT_IF"          # 가정/시뮬레이션

    # 액션 (Action) - 2개
    REPORT = "REPORT"            # 보고서/차트/시각화 생성
    NOTIFY = "NOTIFY"            # 알림/워크플로우 설정

    # 대화 제어 (Conversation) - 4개
    CONTINUE = "CONTINUE"        # 대화 계속
    CLARIFY = "CLARIFY"          # 명확화 필요
    STOP = "STOP"                # 중단/취소
    SYSTEM = "SYSTEM"            # 인사, 도움말, 범위 외


class RouteTarget(str, Enum):
    """라우팅 대상"""
    DATA_LAYER = "DATA_LAYER"
    JUDGMENT_ENGINE = "JUDGMENT_ENGINE"
    RULE_ENGINE = "RULE_ENGINE"
    BI_GUIDE = "BI_GUIDE"
    WORKFLOW_GUIDE = "WORKFLOW_GUIDE"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    ASK_BACK = "ASK_BACK"
    DIRECT_RESPONSE = "DIRECT_RESPONSE"


# V7 Intent → Route Target 매핑
V7_INTENT_TO_ROUTE: Dict[V7Intent, RouteTarget] = {
    V7Intent.CHECK: RouteTarget.DATA_LAYER,
    V7Intent.TREND: RouteTarget.DATA_LAYER,
    V7Intent.COMPARE: RouteTarget.JUDGMENT_ENGINE,
    V7Intent.RANK: RouteTarget.JUDGMENT_ENGINE,
    V7Intent.FIND_CAUSE: RouteTarget.JUDGMENT_ENGINE,
    V7Intent.DETECT_ANOMALY: RouteTarget.RULE_ENGINE,
    V7Intent.PREDICT: RouteTarget.JUDGMENT_ENGINE,
    V7Intent.WHAT_IF: RouteTarget.JUDGMENT_ENGINE,
    V7Intent.REPORT: RouteTarget.BI_GUIDE,
    V7Intent.NOTIFY: RouteTarget.WORKFLOW_GUIDE,
    V7Intent.CONTINUE: RouteTarget.CONTEXT_DEPENDENT,
    V7Intent.CLARIFY: RouteTarget.ASK_BACK,
    V7Intent.STOP: RouteTarget.CONTEXT_DEPENDENT,
    V7Intent.SYSTEM: RouteTarget.DIRECT_RESPONSE,
}

# V7 Intent → Legacy Intent 매핑 (하위호환)
V7_TO_LEGACY_INTENT: Dict[V7Intent, str] = {
    V7Intent.CHECK: "judgment",
    V7Intent.TREND: "judgment",
    V7Intent.COMPARE: "judgment",
    V7Intent.RANK: "bi",
    V7Intent.FIND_CAUSE: "judgment",
    V7Intent.DETECT_ANOMALY: "learning",
    V7Intent.PREDICT: "judgment",
    V7Intent.WHAT_IF: "judgment",
    V7Intent.REPORT: "bi",
    V7Intent.NOTIFY: "workflow",
    V7Intent.CONTINUE: "general",
    V7Intent.CLARIFY: "general",
    V7Intent.STOP: "general",
    V7Intent.SYSTEM: "general",
}

# Legacy Intent 타입 정의 (하위호환)
LEGACY_INTENT_TYPES = [
    "judgment",   # 센서/라인 데이터 조회, 상태 확인
    "bi",         # 차트/그래프 생성, 데이터 분석 시각화
    "workflow",   # 자동화 워크플로우 생성/관리
    "learning",   # 규칙/룰셋 생성, 피드백 학습
    "general",    # 일반 질문/인사
]


# =========================================
# V7 Intent 라우팅 규칙 (14개)
# =========================================
V7_ROUTING_RULES: Dict[str, Dict[str, Any]] = {
    # =========================================
    # 정보 조회 (Information) - 4개
    # =========================================
    "CHECK": {
        "priority": 50,
        "route_to": "DATA_LAYER",
        "description": "단순 현재 상태/수치 조회",
        "patterns": [
            # 상태/수치 조회
            r"(얼마|어때|확인|현황|상태).*(야|줘|해줘)?$",
            r"(현재|지금).*(상태|값|수치|데이터)",
            r"(센서|온도|압력|습도|진동|유량).*(값|데이터).*(보여|조회|확인|알려)",
            r"(센서|온도|압력|습도|진동|유량|생산량|불량률).*(어때|얼마)",
            # 기간 + 데이터 조회 (단순)
            r"(오늘|어제|현재).*(생산량|불량률|수치|값)",
            # 라인/설비 상태
            r"(LINE_|라인|설비|공장).*(상태|현황)",
        ],
        "keywords": ["얼마", "어때", "확인", "현황", "상태", "지금", "현재"],
        "examples": [
            "오늘 생산량 얼마야?",
            "불량률 어때?",
            "현재 온도 확인",
            "A라인 상태 어때?",
        ],
        "slots": {
            "optional": ["metric", "target", "period", "date"],
            "defaults": {"period": "today"},
        },
    },

    "TREND": {
        "priority": 55,
        "route_to": "DATA_LAYER",
        "description": "시간에 따른 변화/추이 조회",
        "patterns": [
            # 추이/변화
            r"(추이|변화|흐름|동향).*(보여|확인|알려)",
            r"(월별|주별|일별|시간별).*(데이터|현황|추이)",
            r".*(추이|트렌드).*",
            # 기간 + 데이터
            r"(지난|이번|저번).*(주|달|월).*(센서|데이터|현황|추이)",
            r"\d+월.*(데이터|현황|추이|변화)",
            r"(최근|요즘).*(변화|추이|데이터)",
        ],
        "keywords": ["추이", "변화", "월별", "주별", "일별", "트렌드", "흐름"],
        "examples": [
            "이번 주 불량률 추이",
            "월별 생산량 변화",
            "온도 추이 보여줘",
            "지난달 데이터 추이",
        ],
        "slots": {
            "required_or": ["metric", "target"],
            "optional": ["period", "targets"],
            "defaults": {"period": "this_week"},
        },
    },

    "COMPARE": {
        "priority": 60,
        "route_to": "JUDGMENT_ENGINE",
        "description": "두 개 이상 대상 비교",
        "patterns": [
            # 비교 명시
            r"(비교|차이|vs|VS).*(해줘|보여줘)?",
            r".*(랑|이랑|와|과).*(비교|차이)",
            r"(뭐가|어디가).*(나아|좋아|높아|낮아)",
            # 대상 비교
            r"(\d+호기|라인).*(랑|이랑|와|과).*(\d+호기|라인)",
            r"(오늘|어제).*(랑|이랑|와|과).*(오늘|어제).*(차이|비교)",
        ],
        "keywords": ["비교", "차이", "vs", "뭐가 나아", "어디가"],
        "examples": [
            "1호기랑 2호기 비교",
            "오늘이랑 어제 차이",
            "A라인 B라인 비교해줘",
            "뭐가 더 나아?",
        ],
        "slots": {
            "required_or": ["targets", "periods"],
            "optional": ["metric", "target"],
        },
    },

    "RANK": {
        "priority": 65,
        "route_to": "JUDGMENT_ENGINE",
        "description": "순위/최대/최소 조회",
        "patterns": [
            # 순위/최대/최소
            r"(제일|가장|최고|최저|최대|최소).*(뭐|어디|어느)",
            r"(순위|순서|랭킹|\btop\b|\bTOP\b|상위|하위)",
            r"(많은|적은|높은|낮은).*(순서|순위|순으로)",
            r"(문제|불량|생산).*(많은|적은).*(설비|라인)",
            # N개
            r"(상위|하위)\s*\d+",
        ],
        "keywords": ["제일", "가장", "최고", "최저", "순위", "top", "상위", "하위"],
        "examples": [
            "제일 문제인 설비",
            "불량 많은 순서대로",
            "생산량 top 5",
            "하위 3개 라인",
        ],
        "slots": {
            "required": ["metric"],
            "optional": ["target", "order", "top_n"],
            "defaults": {"order": "desc", "top_n": 5},
        },
    },

    # =========================================
    # 분석 (Analysis) - 4개
    # =========================================
    "FIND_CAUSE": {
        "priority": 70,
        "route_to": "JUDGMENT_ENGINE",
        "description": "원인 분석 (왜?)",
        "patterns": [
            # 원인/이유
            r"왜.*(늘|줄|올|떨어|증가|감소)",
            r"(원인|이유).*(뭐|무엇|알려)",
            r"(때문|탓).*(에|이야|인가)",
            r".*(이유|원인).*(분석|찾아|알려)",
            # 변화 원인
            r"(늘었|줄었|올랐|떨어졌).*(이유|원인|왜)",
        ],
        "keywords": ["왜", "원인", "때문", "이유"],
        "examples": [
            "왜 불량이 늘었어?",
            "생산량 떨어진 원인",
            "불량 원인 분석해줘",
            "이유가 뭐야?",
        ],
        "slots": {
            "optional": ["metric", "target", "direction", "period"],
            "defaults": {"period": "recent"},
        },
    },

    "DETECT_ANOMALY": {
        "priority": 72,
        "route_to": "RULE_ENGINE",
        "description": "이상/문제 탐지",
        "patterns": [
            # 이상/문제
            r"(이상|문제|경고|비정상|위험).*(있어|없어|뜬|확인)",
            r"(뭔가|혹시).*(이상|문제).*(없어|있어)",
            r"(경고|알림|알람).*(뜬|있어|확인)",
            # 탐지
            r"(이상|비정상).*(탐지|감지|찾아)",
        ],
        "keywords": ["이상", "문제", "경고", "비정상", "위험"],
        "examples": [
            "뭔가 이상한 거 없어?",
            "경고 뜬 설비 있어?",
            "이상 탐지해줘",
            "비정상인 거 찾아줘",
        ],
        "slots": {
            "optional": ["target", "metric"],
            "defaults": {"target": "all"},
        },
    },

    "PREDICT": {
        "priority": 68,
        "route_to": "JUDGMENT_ENGINE",
        "description": "미래 예측/전망",
        "patterns": [
            # 예측/전망
            r"(예상|예측|전망|가능해|될까|맞출 수)",
            r"(목표|납기).*(달성|맞출|가능)",
            r"(앞으로|내일|다음).*(어떻|예상)",
            # 가능성
            r".*(할 수 있|가능할까|될까)",
        ],
        "keywords": ["예상", "예측", "전망", "가능해", "될까", "맞출 수"],
        "examples": [
            "납기 맞출 수 있어?",
            "오늘 목표 달성 가능해?",
            "내일 생산량 예상",
            "예측해줘",
        ],
        "slots": {
            "required": ["metric"],
            "optional": ["target", "period"],
        },
    },

    "WHAT_IF": {
        "priority": 67,
        "route_to": "JUDGMENT_ENGINE",
        "description": "가정/시뮬레이션",
        "patterns": [
            # 가정
            r"(하면|멈추면|늘리면|줄이면).*(어떻|어떨|영향)",
            r"(만약|가정|시뮬).*(하면|했다면)",
            r".*(면|으면)\s*어떻게",
            # 시뮬레이션
            r"시뮬레이션",
        ],
        "keywords": ["하면", "만약", "가정", "시뮬", "늘리면", "줄이면"],
        "examples": [
            "1호기 멈추면 어떻게 돼?",
            "생산량 10% 늘리면?",
            "만약 온도가 90도면?",
            "시뮬레이션 해줘",
        ],
        "slots": {
            "required": ["condition"],
            "optional": ["target", "metric"],
        },
    },

    # =========================================
    # 액션 (Action) - 2개
    # =========================================
    "REPORT": {
        "priority": 100,  # 시각화 키워드 최우선
        "route_to": "BI_GUIDE",
        "description": "보고서/차트/시각화 생성",
        "patterns": [
            # 시각화 명시
            r"(차트|그래프|대시보드|리포트|보고서).*(생성|만들|보여)",
            r".*(차트로|그래프로|시각화).*(보여|만들)",
            r"시각화",
            # 리포트
            r"(리포트|보고서).*(생성|만들|줘)",
            # 분석 + 시각화
            r"(분석|통계).*(차트|그래프|리포트)",
        ],
        "keywords": ["차트", "그래프", "대시보드", "리포트", "보고서", "시각화"],
        "examples": [
            "일일 리포트 만들어줘",
            "생산 추이 차트",
            "불량률 그래프 보여줘",
            "월간 보고서 생성",
        ],
        "slots": {
            "optional": ["report_type", "chart_type", "metric", "period"],
            "defaults": {"report_type": "daily"},
        },
    },

    "NOTIFY": {
        "priority": 75,
        "route_to": "WORKFLOW_GUIDE",
        "description": "알림/워크플로우 설정",
        "patterns": [
            # 워크플로우 키워드
            r".*워크플로우",
            # 알림 설정
            r"(알려줘|알림|통보).*(설정|해줘)",
            r"(넘으면|되면|미만이면|초과하면).*(알려|알림|통보|슬랙)",
            # 자동화
            r"(자동|자동화).*(알림|설정|워크플로우)",
            r"(매일|매주|매시간).*(보내|알려|알림)",
            # 슬랙/이메일
            r"(슬랙|이메일|메일).*(보내|알림)",
        ],
        "keywords": ["워크플로우", "알려줘", "알림", "넘으면", "되면", "슬랙", "자동화"],
        "examples": [
            "온도 60도 넘으면 알려줘",
            "매일 아침 현황 보내줘",
            "워크플로우 만들어줘",
            "슬랙으로 알림 보내줘",
        ],
        "slots": {
            "required": ["condition"],
            "optional": ["action", "schedule", "target"],
            "defaults": {"action": "slack"},
        },
    },

    # =========================================
    # 대화 제어 (Conversation) - 4개
    # =========================================
    "CONTINUE": {
        "priority": 30,
        "route_to": "CONTEXT_DEPENDENT",
        "description": "대화 계속 (응, 더 자세히)",
        "patterns": [
            r"^(응|어|그래|네|예|yes|ok|okay)$",
            r"^(더|좀 더|자세히|상세히)",
            r"(그래서|그럼|그러면)\??$",
            r"(아까|방금).*(거|것)",
            r"^(계속|이어서)$",
        ],
        "keywords": ["응", "어", "그래", "더", "자세히", "그래서", "아까"],
        "examples": [
            "응",
            "더 자세히",
            "그래서?",
            "아까 그거",
        ],
    },

    "CLARIFY": {
        "priority": 10,
        "route_to": "ASK_BACK",
        "description": "명확화 필요 (모호한 발화)",
        "patterns": [
            # 모호한 요청
            r"^(확인|체크|봐줘|알려줘)$",
            r"^(어떻게|어떡해)\??$",
            r"^(괜찮아|됐어)\??$",
            # 짧고 모호한 발화
            r"^.{1,3}$",  # 3글자 이하
        ],
        "keywords": [],
        "examples": [
            "확인해줘",
            "어떻게 된 거야?",
            "괜찮아?",
        ],
        "confidence_threshold": 0.7,  # 이 미만이면 CLARIFY
    },

    "STOP": {
        "priority": 80,
        "route_to": "CONTEXT_DEPENDENT",
        "description": "중단/취소",
        "patterns": [
            r"^(그만|됐어|취소|멈춰|중단|중지|stop)$",
            r"(그만|취소|중단).*(해|해줘)",
            r"(안 해|하지 마|필요 없)",
        ],
        "keywords": ["그만", "됐어", "취소", "멈춰", "중단"],
        "examples": [
            "그만",
            "됐어",
            "취소해",
            "멈춰",
        ],
    },

    "SYSTEM": {
        "priority": 5,
        "route_to": "DIRECT_RESPONSE",
        "description": "인사, 도움말, 범위 외 질문",
        "patterns": [
            # 인사
            r"^(안녕|하이|헬로|hello|hi|반가워)",
            r"(좋은|굿).*(아침|저녁|밤)",
            # 도움말
            r"(도움말|help|도와줘)",
            r"(뭘|뭐).*(할 수|가능)",
            r"(기능|할 수 있는 것)",
            # 감사/마무리
            r"(고마워|감사|땡큐|thanks|수고)",
            # 자기소개 요청
            r"(뭐야|누구야|뭐니|누구니)",
        ],
        "keywords": ["안녕", "도움말", "뭐야", "누구야", "고마워"],
        "examples": [
            "안녕",
            "뭘 할 수 있어?",
            "도움말",
            "고마워",
        ],
    },
}


# =========================================
# Legacy 라우팅 규칙 (하위호환)
# =========================================
LEGACY_ROUTING_RULES: Dict[str, Dict[str, Any]] = {
    "judgment": {
        "priority": 50,
        "v7_mapping": ["CHECK", "TREND", "COMPARE", "FIND_CAUSE", "PREDICT", "WHAT_IF"],
        "description": "센서/라인 데이터 조회, 상태 확인, 실시간 모니터링",
    },
    "bi": {
        "priority": 100,
        "v7_mapping": ["REPORT", "RANK"],
        "description": "차트/그래프 생성, 데이터 분석, 시각화, 리포트",
    },
    "workflow": {
        "priority": 75,
        "v7_mapping": ["NOTIFY"],
        "description": "자동화 워크플로우 생성/수정/삭제, 트리거 설정",
    },
    "learning": {
        "priority": 76,
        "v7_mapping": ["DETECT_ANOMALY"],
        "description": "규칙/룰셋 생성, 피드백 학습, 규칙 개선 제안",
    },
    "general": {
        "priority": 0,
        "v7_mapping": ["SYSTEM", "CONTINUE", "CLARIFY", "STOP"],
        "description": "일반 질문, 인사, 도움말",
    },
}


# =========================================
# 유틸리티 함수
# =========================================

def get_v7_rule(intent: str) -> Dict[str, Any]:
    """V7 Intent의 규칙 조회"""
    return V7_ROUTING_RULES.get(intent.upper(), {})


def get_legacy_rule(intent: str) -> Dict[str, Any]:
    """Legacy Intent의 규칙 조회"""
    return LEGACY_ROUTING_RULES.get(intent.lower(), {})


def get_all_v7_intents() -> List[str]:
    """모든 V7 Intent 타입 조회"""
    return list(V7_ROUTING_RULES.keys())


def get_all_legacy_intents() -> List[str]:
    """모든 Legacy Intent 타입 조회"""
    return LEGACY_INTENT_TYPES


def get_sorted_v7_rules() -> List[tuple]:
    """우선순위 순으로 정렬된 V7 규칙 목록"""
    return sorted(
        V7_ROUTING_RULES.items(),
        key=lambda x: x[1].get("priority", 0),
        reverse=True
    )


def v7_to_legacy(v7_intent: str) -> str:
    """V7 Intent를 Legacy Intent로 변환"""
    try:
        intent_enum = V7Intent(v7_intent.upper())
        return V7_TO_LEGACY_INTENT.get(intent_enum, "general")
    except ValueError:
        return "general"


def v7_to_route_target(v7_intent: str) -> str:
    """V7 Intent를 Route Target으로 변환"""
    try:
        intent_enum = V7Intent(v7_intent.upper())
        return V7_INTENT_TO_ROUTE.get(intent_enum, RouteTarget.DIRECT_RESPONSE).value
    except ValueError:
        return RouteTarget.DIRECT_RESPONSE.value


def get_route_target(v7_intent: str) -> Optional[str]:
    """V7 Intent의 라우팅 대상 조회"""
    rule = get_v7_rule(v7_intent)
    return rule.get("route_to")


# =========================================
# 하위 호환성을 위한 별칭
# =========================================
INTENT_TYPES = LEGACY_INTENT_TYPES
ROUTING_RULES = LEGACY_ROUTING_RULES


def get_rule(intent: str) -> Dict[str, Any]:
    """특정 Intent의 규칙 조회 (하위호환)"""
    # V7 Intent 먼저 확인
    v7_rule = get_v7_rule(intent)
    if v7_rule:
        return v7_rule
    # Legacy Intent 확인
    return get_legacy_rule(intent)


def get_all_intents() -> List[str]:
    """모든 Intent 타입 조회 (하위호환)"""
    return get_all_legacy_intents()


def get_sorted_rules() -> List[tuple]:
    """우선순위 순으로 정렬된 규칙 목록 (하위호환)"""
    return sorted(
        LEGACY_ROUTING_RULES.items(),
        key=lambda x: x[1].get("priority", 0),
        reverse=True
    )
