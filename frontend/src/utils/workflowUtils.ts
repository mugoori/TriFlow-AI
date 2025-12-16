/**
 * Workflow Utility Functions
 * 워크플로우 DSL 처리를 위한 공유 유틸리티
 */

import { WorkflowNode } from '@/types/agent';

/**
 * 평탄화된 노드 정보
 */
export interface FlattenedNode {
  node: WorkflowNode;
  parentId?: string;
  branchType?: 'then' | 'else' | 'loop' | 'parallel';
  depth: number;
}

/**
 * 중첩된 워크플로우 노드를 평탄화
 * @param nodes 워크플로우 노드 배열
 * @param depth 현재 깊이 (기본값: 0)
 * @param parentId 부모 노드 ID
 * @param branchType 분기 타입
 */
export function flattenWorkflowNodes(
  nodes: WorkflowNode[],
  depth = 0,
  parentId?: string,
  branchType?: 'then' | 'else' | 'loop' | 'parallel'
): FlattenedNode[] {
  const result: FlattenedNode[] = [];

  for (const node of nodes) {
    result.push({ node, depth, parentId, branchType });

    if (node.then_nodes?.length) {
      result.push(...flattenWorkflowNodes(node.then_nodes, depth + 1, node.id, 'then'));
    }
    if (node.else_nodes?.length) {
      result.push(...flattenWorkflowNodes(node.else_nodes, depth + 1, node.id, 'else'));
    }
    if (node.loop_nodes?.length) {
      result.push(...flattenWorkflowNodes(node.loop_nodes, depth + 1, node.id, 'loop'));
    }
    if (node.parallel_nodes?.length) {
      result.push(...flattenWorkflowNodes(node.parallel_nodes, depth + 1, node.id, 'parallel'));
    }
  }

  return result;
}

/**
 * 노드 타입을 한글 라벨로 변환
 */
export function getNodeTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    condition: '조건',
    action: '액션',
    if_else: '분기',
    loop: '반복',
    parallel: '병렬',
  };
  return labels[type] || type;
}

/**
 * 액션 타입을 한글 라벨로 변환
 */
export function getActionDisplayName(actionType: string | undefined): string {
  if (!actionType) return '알 수 없는 액션';

  const actionNames: Record<string, string> = {
    send_slack_notification: 'Slack 알림',
    send_email: '이메일 전송',
    send_sms: 'SMS 전송',
    log_event: '이벤트 로그',
    stop_production_line: '라인 정지',
    trigger_maintenance: '유지보수 트리거',
    adjust_sensor_threshold: '임계값 조정',
    save_to_database: 'DB 저장',
    export_to_csv: 'CSV 내보내기',
  };
  return actionNames[actionType] || actionType;
}

/**
 * 노드 요약 문자열 생성
 */
export function getNodeSummary(node: WorkflowNode): string {
  const config = node.config || {};

  if (node.type === 'action') {
    const actionType = (config.action_type || config.action) as string | undefined;
    return getActionDisplayName(actionType);
  }

  if (node.type === 'if_else' || node.type === 'condition') {
    const cond = config.condition as Record<string, unknown> | string | undefined;
    if (typeof cond === 'object' && cond) {
      const field = cond.field || '';
      const operator = cond.operator || '';
      const value = cond.value ?? '';
      return `${field} ${operator} ${value}`;
    }
    if (typeof cond === 'string') {
      return cond;
    }
    return node.id;
  }

  if (node.type === 'loop') {
    const count = config.count || config.iterations || '?';
    return `${count}회 반복`;
  }

  if (node.type === 'parallel') {
    const parallelCount = node.parallel_nodes?.length || 0;
    return `${parallelCount}개 병렬 실행`;
  }

  return node.id;
}

/**
 * 트리거 타입을 한글 라벨로 변환
 */
export function getTriggerTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    event: '이벤트',
    schedule: '스케줄',
    manual: '수동',
  };
  return labels[type] || type;
}
