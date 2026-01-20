import httpx
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote

from ..config.settings import API_KEYS

logger = logging.getLogger(__name__)

# API 설정
FOODSAFETY_API_KEY = API_KEYS.get("식품안전나라", {}).get("api_key", "")
FOODSAFETY_BASE_URL = "http://openapi.foodsafetykorea.go.kr/api"
SERVICE_CODE = "I0030"  # 건강기능식품 품목제조 신고사항 현황

async def search_similar_products(
    keyword: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    식품안전나라 API에서 유사 제품 검색.
    원료명(RAWMTRL_NM)에서 키워드 검색.
    """
    if not FOODSAFETY_API_KEY:
        return []

    url = f"{FOODSAFETY_BASE_URL}/{FOODSAFETY_API_KEY}/{SERVICE_CODE}/json/1/{limit}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if SERVICE_CODE not in data:
                return []

            rows = data[SERVICE_CODE].get("row", [])

            # 키워드로 필터링 (원료명에 포함된 것만)
            filtered = []
            for row in rows:
                raw_materials = row.get("RAWMTRL_NM", "")
                if keyword.lower() in raw_materials.lower():
                    filtered.append(_parse_product(row))

            return filtered

    except Exception as e:
        logger.exception(f"[FoodSafety API] Error: {e}")
        # 에러가 발생해도 빈 배열 반환 (다른 검색 결과는 유지)
        return []

async def search_by_ingredients(
    ingredients: List[str],
    formulation_type: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    여러 원료로 유사 제품 검색.
    API의 PRDLST_NM(품목명) 파라미터를 활용하여 검색.
    """
    logger.info(f"[FoodSafety API] search_by_ingredients called: {ingredients}, limit={limit}")

    if not FOODSAFETY_API_KEY:
        logger.warning("[FoodSafety API] API key not found")
        return []

    logger.info(f"[FoodSafety API] API_KEY: {FOODSAFETY_API_KEY[:10]}...")

    results = []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 각 원료명으로 품목명 검색 (API가 PRDLST_NM 파라미터 지원)
            for ingredient in ingredients[:3]:  # 최대 3개 원료로 검색
                # PRDLST_NM 파라미터로 품목명 검색 (URL 인코딩 필요)
                encoded_ingredient = quote(ingredient)
                url = f"{FOODSAFETY_BASE_URL}/{FOODSAFETY_API_KEY}/{SERVICE_CODE}/json/1/50/PRDLST_NM={encoded_ingredient}"

                logger.info(f"[FoodSafety API] Calling: {url}")

                response = await client.get(url)
                logger.info(f"[FoodSafety API] Response status: {response.status_code}")

                if response.status_code != 200:
                    logger.warning(f"[FoodSafety API] Non-200 status: {response.status_code}")
                    continue

                data = response.json()

                if SERVICE_CODE not in data:
                    logger.warning(f"[FoodSafety API] SERVICE_CODE not in response. Keys: {data.keys()}")
                    continue

                rows = data[SERVICE_CODE].get("row", [])
                logger.info(f"[FoodSafety API] Found {len(rows)} products for '{ingredient}'")

                rows = data[SERVICE_CODE].get("row", [])

                for row in rows:
                    raw_materials = row.get("RAWMTRL_NM", "").lower()
                    product_form = row.get("PRDT_SHAP_CD_NM", "")

                    # 제형 필터
                    if formulation_type and formulation_type not in product_form:
                        continue

                    # 원료 매칭 점수 (원료명에 검색어가 포함되어 있으면 추가 점수)
                    match_count = sum(1 for ing in ingredients if ing.lower() in raw_materials)

                    parsed = _parse_product(row)
                    parsed["match_count"] = match_count
                    parsed["source"] = "식품안전나라"

                    # 중복 제거 (품목명 기준)
                    if not any(r["product_name"] == parsed["product_name"] for r in results):
                        results.append(parsed)

            # 매칭 점수로 정렬
            results.sort(key=lambda x: x["match_count"], reverse=True)
            return results[:limit]

    except Exception as e:
        logger.exception(f"[FoodSafety API] Error: {e}")
        # 에러가 발생해도 빈 배열 반환 (다른 검색 결과는 유지)
        return []

def _parse_product(row: Dict[str, Any]) -> Dict[str, Any]:
    """API 응답을 파싱하여 정리된 형태로 반환.

    I0030 (건강기능식품 품목제조 신고사항 현황) API 필드:
    - PRDLST_NM: 품목명
    - BSSH_NM: 업소명
    - PRDT_SHAP_CD_NM: 제품형태 (캡슐, 정제, 액상 등)
    - RAWMTRL_NM: 원재료명 (간략)
    - INDIV_RAWMTRL_NM: 기능성원료명 (상세)
    - ETC_RAWMTRL_NM: 기타원료명
    - POG_DAYCNT: 소비기한
    - PRIMARY_FNCLTY: 주된기능성
    - NTK_MTHD: 섭취방법
    - PRDLST_REPORT_NO: 품목제조번호
    - IFTKN_ATNT_MATR_CN: 섭취시주의사항
    - STDR_STND: 기준규격
    """
    return {
        "product_name": row.get("PRDLST_NM", ""),
        "company_name": row.get("BSSH_NM", ""),
        "formulation_type": row.get("PRDT_SHAP_CD_NM", ""),
        "raw_materials": row.get("RAWMTRL_NM", ""),
        "functional_ingredients": row.get("INDIV_RAWMTRL_NM", ""),
        "other_ingredients": row.get("ETC_RAWMTRL_NM", ""),
        "shelf_life": row.get("POG_DAYCNT", ""),
        "functionality": row.get("PRIMARY_FNCLTY", "")[:500] if row.get("PRIMARY_FNCLTY") else "",
        "intake_method": row.get("NTK_MTHD", ""),
        "report_no": row.get("PRDLST_REPORT_NO", ""),
        "caution": row.get("IFTKN_ATNT_MATR_CN", ""),
        "standard": row.get("STDR_STND", "")[:300] if row.get("STDR_STND") else ""
    }
