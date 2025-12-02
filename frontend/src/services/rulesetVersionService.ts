/**
 * Ruleset Version Service
 * 룰셋 버전 관리 API 클라이언트
 */
import { apiClient } from './api';

// ============ Types ============

export interface RulesetVersion {
  version_id: string;
  ruleset_id: string;
  version_number: number;
  version_label: string;
  rhai_script: string;
  description: string | null;
  change_summary: string | null;
  created_at: string;
}

export interface RulesetVersionListResponse {
  versions: RulesetVersion[];
  total: number;
}

export interface Ruleset {
  ruleset_id: string;
  name: string;
  description: string | null;
  rhai_script: string;
  version: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ============ API Functions ============

/**
 * 룰셋 버전 히스토리 조회
 */
export async function listRulesetVersions(
  rulesetId: string,
  params?: { limit?: number; offset?: number }
): Promise<RulesetVersionListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const queryString = searchParams.toString();
  const url = queryString
    ? `/api/v1/rulesets/${rulesetId}/versions?${queryString}`
    : `/api/v1/rulesets/${rulesetId}/versions`;

  return apiClient.get<RulesetVersionListResponse>(url);
}

/**
 * 특정 버전 상세 조회
 */
export async function getRulesetVersion(
  rulesetId: string,
  versionId: string
): Promise<RulesetVersion> {
  return apiClient.get<RulesetVersion>(
    `/api/v1/rulesets/${rulesetId}/versions/${versionId}`
  );
}

/**
 * 현재 상태를 새 버전으로 저장 (스냅샷)
 */
export async function createVersionSnapshot(
  rulesetId: string,
  changeSummary?: string
): Promise<RulesetVersion> {
  const url = changeSummary
    ? `/api/v1/rulesets/${rulesetId}/versions?change_summary=${encodeURIComponent(changeSummary)}`
    : `/api/v1/rulesets/${rulesetId}/versions`;

  return apiClient.post<RulesetVersion>(url, {});
}

/**
 * 특정 버전으로 롤백
 */
export async function rollbackToVersion(
  rulesetId: string,
  versionId: string
): Promise<Ruleset> {
  return apiClient.post<Ruleset>(
    `/api/v1/rulesets/${rulesetId}/versions/${versionId}/rollback`,
    {}
  );
}

/**
 * 특정 버전 삭제 (가장 최근 버전만 가능)
 */
export async function deleteVersion(
  rulesetId: string,
  versionId: string
): Promise<void> {
  await apiClient.delete(`/api/v1/rulesets/${rulesetId}/versions/${versionId}`);
}
