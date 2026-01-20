from typing import List, Optional, Dict, Any
from datetime import datetime
import re

from ..models.schemas import PromptRequest, SimilarProductAPI

def generate_formulation_prompt(request: PromptRequest) -> str:
    """
    배합비 추천 프롬프트 생성.
    Claude Desktop에서 SQL MCP로 내부 DB 검색 + 공공API 결과 참조.
    """
    product_info = request.product_info
    ingredients = request.ingredient_requirements
    constraints = request.constraints
    similar_products = request.similar_products_api or []

    # 필수 원료 목록
    required_ingredients = [ing.ingredient_name for ing in ingredients if ing.is_required]
    required_str = ", ".join(required_ingredients) if required_ingredients else "없음"

    # 선택 원료 목록
    optional_ingredients = [ing.ingredient_name for ing in ingredients if not ing.is_required]
    optional_str = ", ".join(optional_ingredients) if optional_ingredients else "없음"

    # 원료 상세 정보 (비율 제약 포함)
    ingredient_details = []
    for ing in ingredients:
        detail = f"- **{ing.ingredient_name}**"
        if ing.is_required:
            detail += " (필수)"
        if ing.min_ratio or ing.max_ratio:
            ratio_info = []
            if ing.min_ratio:
                ratio_info.append(f"최소 {ing.min_ratio}%")
            if ing.max_ratio:
                ratio_info.append(f"최대 {ing.max_ratio}%")
            detail += f" [{', '.join(ratio_info)}]"
        if ing.notes:
            detail += f" - {ing.notes}"
        ingredient_details.append(detail)

    ingredient_details_str = "\n".join(ingredient_details) if ingredient_details else "원료 요구사항 없음"

    # 제약조건
    constraints_list = []
    if constraints.max_ingredients:
        constraints_list.append(f"최대 원료 수: {constraints.max_ingredients}종")
    if constraints.avoid_ingredients:
        constraints_list.append(f"제외 원료: {', '.join(constraints.avoid_ingredients)}")
    if constraints.regulatory_requirements:
        for req in constraints.regulatory_requirements:
            constraints_list.append(f"규제 요건: {req}")
    if constraints.quality_requirements:
        for req in constraints.quality_requirements:
            constraints_list.append(f"품질 요건: {req}")

    constraints_str = "\n".join([f"{i+1}. {c}" for i, c in enumerate(constraints_list)]) if constraints_list else "특별한 제약 조건 없음."

    # 유사제품 테이블 (공공API 결과)
    similar_products_str = _format_similar_products(similar_products)

    # 원가 포맷
    cost_str = f"{product_info.target_cost:,}원/세트" if product_info.target_cost else "미정"

    # 중량 포맷
    weight_str = f"{product_info.target_weight}g" if product_info.target_weight else "미정"

    # 제형에서 첫 단어 추출 (SQL 검색용)
    formulation_keyword = product_info.formulation_type.split()[0] if product_info.formulation_type else ""

    prompt = f"""# 역할: 20년 경력의 건강기능식품 배합 전문가

## 0. 사전 데이터 분석 (필수)

### 1) 내부 DB 검색 (SQL MCP 사용)
formulation.db에서 유사 제품을 검색하세요:

**테이블 구조:**
- `recipe_metadata`: 제품 메타정보 (filename, product_name, company_name, formulation_type)
- `historical_recipes`: 배합비 상세 (ingredient, ratio, filename)

**검색 쿼리 예시:**
```sql
-- 제형이 '{product_info.formulation_type}'이고 주요 원료가 포함된 제품 찾기
SELECT rm.product_name, rm.company_name, rm.formulation_type,
       hr.ingredient, hr.ratio
FROM recipe_metadata rm
JOIN historical_recipes hr ON rm.filename = hr.filename
WHERE rm.formulation_type LIKE '%{formulation_keyword}%'
ORDER BY hr.ratio DESC
LIMIT 30;
```

→ 유사 제품의 **배합 비율 패턴**을 참고하세요.

### 2) 유사제품 참고자료 (공공API 검색결과)
아래는 식품안전나라에서 검색한 유사 제품입니다:

{similar_products_str}

→ **소비기한**, **원료 조합 패턴**을 참고하세요.

---

## 1. 제품 정보
- **제품명**: {product_info.name}
- **제형**: {product_info.formulation_type}
- **목표 원가**: {cost_str}
- **목표 중량**: {weight_str}
{f"- **비고**: {product_info.description}" if product_info.description else ""}

## 2. 원료 요구사항
### 필수 원료
{required_str}

### 선택 원료
{optional_str}

### 상세 요구사항
{ingredient_details_str}

## 3. 제약 조건
{constraints_str}

---

## 4. 출력 요청: 배합비 3가지 옵션

각 옵션별로 아래 형식을 따라 작성하세요.

### 옵션 1: 원가 최적화
| No | 원료명 | 배합비 (%) | 역할 |
|----|--------|------------|------|
| 1 | [원료명] | [비율] | [주원료/부형제/기능성] |
| ... | ... | ... | ... |
| **계** | **합계** | **100.00%** | - |

- **예상 원가**: X원/세트
- **제조 시 주의사항**: [믹싱 순서, 온도, 습도 등]
- **예상 품질**: [맛, 용해성, 안정성 등]

### 옵션 2: 프리미엄 품질
(동일 형식)

### 옵션 3: 균형 (추천)
(동일 형식)

---

## 5. 종합 의견
- **옵션별 비교 요약**: 각 옵션의 장단점
- **추천 옵션 및 근거**: 어떤 옵션을 왜 추천하는지
- **참고한 유사제품**: 내부 DB/공공API에서 참고한 제품 목록

---

**중요 지침:**
1. 배합비 총합은 정확히 **100.00%**
2. 원가 계산은 내부적으로만, **최종 출력에는 단가 미노출**
3. 식약처 기준 **일일섭취량** 준수
4. 실제 **제조 가능성** 고려 (유동성, 성형성)
"""

    return prompt


def _format_similar_products(products: Optional[List[SimilarProductAPI]]) -> str:
    """유사제품 목록을 마크다운 테이블로 포맷."""
    if not products:
        return "검색된 유사제품이 없습니다. 공공API 승인 대기 중일 수 있습니다."

    lines = ["| 제품명 | 업체명 | 제형 | 주요 원료 | 소비기한 |",
             "|--------|--------|------|----------|----------|"]

    for p in products[:5]:  # 최대 5개만
        raw_materials = p.raw_materials or ""
        raw_materials_short = raw_materials[:50] + "..." if len(raw_materials) > 50 else raw_materials
        lines.append(f"| {p.product_name} | {p.company_name or '-'} | {p.formulation_type or '-'} | {raw_materials_short} | {p.shelf_life or '-'} |")

    return "\n".join(lines)


def _generate_mock_response(product_info) -> str:
    """테스트용 Mock 응답 생성"""
    return f"""# 역할: 20년 경력의 건강기능식품 배합 전문가

## 0. 사전 데이터 분석

내부 DB와 공공API를 분석한 결과, {product_info.formulation_type} 제형의 유사 제품들을 참고했습니다.

---

## 1. 제품 정보
- **제품명**: {product_info.name}
- **제형**: {product_info.formulation_type}

---

## 4. 출력 요청: 배합비 3가지 옵션

### 옵션 1: 원가 최적화
| No | 원료명 | 배합비 (%) | 역할 |
|----|--------|------------|------|
| 1 | 비타민C | 35.00 | 주원료/기능성 |
| 2 | 아연 | 15.00 | 주원료/기능성 |
| 3 | 결정셀룰로오스 | 25.00 | 부형제 |
| 4 | 스테아린산마그네슘 | 10.00 | 활택제 |
| 5 | 이산화규소 | 10.00 | 흐름개선제 |
| 6 | HPMC | 5.00 | 코팅제 |
| **계** | **합계** | **100.00%** | - |

- **예상 원가**: 12,000원/세트
- **제조 시 주의사항**: 비타민C의 산화 방지를 위해 습도 관리 필요. 타정 시 15-20kN 압력 유지.
- **예상 품질**: 용해성 양호, 안정성 우수. 6개월 이상 품질 유지 가능.

### 옵션 2: 프리미엄 품질
| No | 원료명 | 배합비 (%) | 역할 |
|----|--------|------------|------|
| 1 | 비타민C (아스코르빈산) | 40.00 | 주원료/기능성 |
| 2 | 아연 킬레이트 | 20.00 | 주원료/기능성 |
| 3 | 셀룰로오스 | 20.00 | 부형제 |
| 4 | 스테아린산마그네슘 | 8.00 | 활택제 |
| 5 | 이산화규소 | 7.00 | 흐름개선제 |
| 6 | HPMC 코팅 | 5.00 | 코팅제 |
| **계** | **합계** | **100.00%** | - |

- **예상 원가**: 18,500원/세트
- **제조 시 주의사항**: 프리미엄 원료 사용으로 생체이용률 향상. 온도 25℃ 이하 유지.
- **예상 품질**: 용해성 매우 우수, 흡수율 높음. 12개월 이상 안정성 보장.

### 옵션 3: 균형 (추천)
| No | 원료명 | 배합비 (%) | 역할 |
|----|--------|------------|------|
| 1 | 비타민C | 38.00 | 주원료/기능성 |
| 2 | 아연 | 17.00 | 주원료/기능성 |
| 3 | 결정셀룰로오스 | 22.00 | 부형제 |
| 4 | 스테아린산마그네슘 | 9.00 | 활택제 |
| 5 | 이산화규소 | 9.00 | 흐름개선제 |
| 6 | HPMC | 5.00 | 코팅제 |
| **계** | **합계** | **100.00%** | - |

- **예상 원가**: 15,000원/세트
- **제조 시 주의사항**: 원가와 품질의 최적 균형. 일반적인 제조 조건 적용 가능.
- **예상 품질**: 용해성 우수, 안정성 양호. 9개월 이상 품질 유지 가능.

---

## 5. 종합 의견

### 옵션별 비교 요약
- **옵션 1 (원가 최적화)**: 가격 경쟁력이 필요한 경우 적합. 기본 품질 보장.
- **옵션 2 (프리미엄)**: 고급 브랜드 포지셔닝 시 추천. 생체이용률 우수.
- **옵션 3 (균형)**: 가장 추천하는 옵션. 원가와 품질의 최적 균형으로 시장 경쟁력 확보.

### 추천 옵션 및 근거
**옵션 3 (균형)** 을 추천합니다.
- 합리적인 원가 (15,000원)로 시장 진입 용이
- 충분한 기능성 원료 함량으로 효과 보장
- 제조 안정성 우수
- 소비자 만족도 높은 가격대

### 참고한 유사제품
- 내부 DB: 비타민C 정제 5개 제품 분석
- 공공API: 식품안전나라 등록 제품 3개 참조
"""


def parse_recipe_response(claude_response: str) -> List[Dict[str, Any]]:
    """
    Claude 응답에서 3가지 배합비 옵션을 파싱.

    Returns:
        [
            {
                "option_type": "cost_optimized",
                "title": "원가 최적화",
                "ingredients": [
                    {"no": 1, "name": "비타민C", "ratio": 45.0, "role": "주원료"},
                    ...
                ],
                "total_ratio": 100.0,
                "estimated_cost": "15,000원/세트",
                "notes": "제조 시 주의사항...",
                "quality": "예상 품질..."
            },
            ...
        ]
    """
    options = []

    # 옵션 패턴 정의
    option_patterns = [
        (r"###\s*옵션\s*1[:\s]*원가\s*최적화", "cost_optimized", "원가 최적화"),
        (r"###\s*옵션\s*2[:\s]*프리미엄\s*품질", "premium", "프리미엄 품질"),
        (r"###\s*옵션\s*3[:\s]*균형", "balanced", "균형 (추천)")
    ]

    for pattern, option_type, title in option_patterns:
        # 옵션 섹션 찾기
        option_match = re.search(pattern, claude_response, re.IGNORECASE | re.MULTILINE)
        if not option_match:
            continue

        start_pos = option_match.end()

        # 다음 옵션 또는 "종합 의견" 섹션까지 추출
        next_section = re.search(r"###\s*옵션\s*[23]|##\s*5\.\s*종합\s*의견", claude_response[start_pos:], re.IGNORECASE | re.MULTILINE)
        if next_section:
            section_text = claude_response[start_pos:start_pos + next_section.start()]
        else:
            section_text = claude_response[start_pos:]

        # 테이블 파싱
        ingredients = []
        table_match = re.search(r'\|\s*No\s*\|.*?\|.*?\|.*?\|.*?\n\|[-\s|]+\n((?:\|.*?\n)+)', section_text, re.MULTILINE)

        if table_match:
            table_rows = table_match.group(1).strip().split('\n')
            for row in table_rows:
                # "계" 또는 "합계" 행 제외
                if '계' in row or '합계' in row:
                    continue

                cells = [cell.strip() for cell in row.split('|') if cell.strip()]
                if len(cells) >= 4:
                    try:
                        no = int(cells[0]) if cells[0].isdigit() else len(ingredients) + 1
                        name = cells[1]
                        ratio_text = cells[2].replace('%', '').replace(',', '').strip()
                        ratio = float(ratio_text) if ratio_text else 0.0
                        role = cells[3]

                        ingredients.append({
                            "no": no,
                            "name": name,
                            "ratio": ratio,
                            "role": role
                        })
                    except (ValueError, IndexError):
                        continue

        # 예상 원가 추출
        cost_match = re.search(r'-\s*\*\*예상\s*원가\*\*[:\s]*(.*?)(?:\n|$)', section_text, re.IGNORECASE)
        estimated_cost = cost_match.group(1).strip() if cost_match else None

        # 제조 시 주의사항 추출
        notes_match = re.search(r'-\s*\*\*제조\s*시\s*주의사항\*\*[:\s]*(.*?)(?:\n-|\n\n|$)', section_text, re.IGNORECASE | re.DOTALL)
        notes = notes_match.group(1).strip() if notes_match else None

        # 예상 품질 추출
        quality_match = re.search(r'-\s*\*\*예상\s*품질\*\*[:\s]*(.*?)(?:\n-|\n\n|$)', section_text, re.IGNORECASE | re.DOTALL)
        quality = quality_match.group(1).strip() if quality_match else None

        # 총 배합비 계산
        total_ratio = sum(ing["ratio"] for ing in ingredients)

        options.append({
            "option_type": option_type,
            "title": title,
            "ingredients": ingredients,
            "total_ratio": round(total_ratio, 2),
            "estimated_cost": estimated_cost,
            "notes": notes,
            "quality": quality
        })

    # 종합 의견 추출
    summary_match = re.search(r'##\s*5\.\s*종합\s*의견(.*?)(?:\n##|\Z)', claude_response, re.IGNORECASE | re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else None

    # 모든 옵션에 종합 의견 추가
    for option in options:
        option["summary"] = summary

    return options


async def generate_and_execute_recipe(
    product_info: dict,
    ingredient_requirements: list,
    constraints: dict,
    similar_products_api: list
) -> dict:
    """
    AI 배합비 자동 생성
    - Claude API 직접 호출
    - 3가지 배합비 옵션 반환
    """
    import os
    import anthropic
    from ..models.schemas import PromptRequest, ProductInfo, IngredientRequirement, Constraints

    # 1. 스키마 객체 생성
    product_info_obj = ProductInfo(**product_info)
    ingredient_reqs = [IngredientRequirement(**ing) for ing in ingredient_requirements]
    constraints_obj = Constraints(**constraints) if constraints else Constraints()

    prompt_request = PromptRequest(
        product_info=product_info_obj,
        ingredient_requirements=ingredient_reqs,
        constraints=constraints_obj,
        similar_products_api=similar_products_api
    )

    # 2. 프롬프트 생성
    prompt_text = generate_formulation_prompt(prompt_request)

    # 3. Claude API 호출
    try:
        # 환경 변수로 Mock/실제 API 전환
        use_mock = os.getenv("USE_MOCK_CLAUDE", "true").lower() == "true"

        if use_mock:
            # Mock 응답 사용 (테스트용)
            response = _generate_mock_response(product_info_obj)
        else:
            # 실제 Claude API 호출
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=8000,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt_text
                    }
                ]
            )
            response = message.content[0].text

        # 4. 응답 파싱
        recipe_options = parse_recipe_response(response)

        # 5. 구조화된 응답 반환
        return {
            "recipe_options": recipe_options,
            "raw_response": response,  # 디버깅용
            "generated_at": datetime.now().isoformat(),
            "product_name": product_info_obj.name,
            "formulation_type": product_info_obj.formulation_type
        }

    except Exception as e:
        # 에러 시 기본값 반환
        import traceback
        return {
            "recipe_options": [],
            "error": f"{str(e)}\n{traceback.format_exc()}",
            "generated_at": datetime.now().isoformat()
        }
