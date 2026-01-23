/**
 * API 유틸리티 함수
 * 공통 API 관련 헬퍼 함수 모음
 */

/**
 * 객체를 URLSearchParams로 변환
 * undefined/null 값은 자동으로 필터링
 */
export function buildQueryParams(params?: object): URLSearchParams {
  const searchParams = new URLSearchParams();
  if (!params) return searchParams;

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, String(value));
    }
  });

  return searchParams;
}

/**
 * URL에 쿼리 파라미터 추가
 */
export function appendQueryParams(baseUrl: string, params?: object): string {
  const searchParams = buildQueryParams(params);
  const queryString = searchParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
}

export default { buildQueryParams, appendQueryParams };
