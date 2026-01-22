"""
Locust 성능 테스트
스펙 참조: C-3-2 Performance Testing

성능 목표 (스펙 NFR-PERF):
- Judgment P95 < 2.5s (Hybrid)
- BI P95 < 3s
- 처리량: 50 TPS (Judgment)
- 동시 사용자: 500명

실행 방법:
    locust -f tests/performance/locustfile.py --host=http://localhost:8000
    브라우저: http://localhost:8089
"""
import json
import random
from uuid import uuid4

from locust import HttpUser, task, between, events


class TriFlowUser(HttpUser):
    """TriFlow AI 사용자 시뮬레이션"""

    # 요청 간 대기 시간 (1~3초)
    wait_time = between(1, 3)

    def on_start(self):
        """테스트 시작 시 로그인"""
        # 로그인
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123",
            },
        )

        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}
            print(f"Login failed: {response.status_code}")

        # 테스트용 Ruleset ID 생성 (사전에 생성된 것 사용)
        self.ruleset_id = self._get_or_create_test_ruleset()

    def _get_or_create_test_ruleset(self) -> str:
        """테스트용 Ruleset 조회 또는 생성"""
        # Ruleset 목록 조회
        response = self.client.get(
            "/api/v1/rulesets",
            headers=self.headers,
        )

        if response.status_code == 200:
            rulesets = response.json().get("rulesets", [])
            active_rulesets = [r for r in rulesets if r.get("is_active")]

            if active_rulesets:
                return active_rulesets[0]["ruleset_id"]

        # 없으면 생성
        response = self.client.post(
            "/api/v1/rulesets",
            headers=self.headers,
            json={
                "name": f"Perf Test Ruleset {uuid4()}",
                "rhai_script": "#{status: \"OK\", confidence: 0.85}",
                "is_active": True,
            },
        )

        if response.status_code == 201:
            return response.json()["ruleset_id"]

        # 기본값 (실패 시)
        return str(uuid4())

    @task(5)  # 가중치: 5 (Judgment가 가장 빈번)
    def execute_judgment(self):
        """Judgment 실행 (Rule Only - 빠름)"""
        if not self.token:
            return

        self.client.post(
            "/api/v1/judgment/execute",
            headers=self.headers,
            json={
                "ruleset_id": self.ruleset_id,
                "input_data": {
                    "temperature": random.uniform(20, 100),
                    "pressure": random.uniform(0.5, 10),
                    "humidity": random.uniform(30, 80),
                },
                "policy": "rule_only",  # 빠른 테스트
                "need_explanation": False,  # 설명 불필요
            },
            name="/api/v1/judgment/execute (RULE_ONLY)",
        )

    @task(2)  # 가중치: 2
    def execute_judgment_hybrid(self):
        """Judgment 실행 (Hybrid - 느림)"""
        if not self.token:
            return

        self.client.post(
            "/api/v1/judgment/execute",
            headers=self.headers,
            json={
                "ruleset_id": self.ruleset_id,
                "input_data": {
                    "temperature": random.uniform(60, 90),
                    "pressure": random.uniform(5, 12),
                },
                "policy": "hybrid_weighted",  # Rule + LLM
                "need_explanation": True,
            },
            name="/api/v1/judgment/execute (HYBRID)",
        )

    @task(3)  # 가중치: 3
    def get_sensor_summary(self):
        """센서 요약 조회"""
        if not self.token:
            return

        self.client.get(
            "/api/v1/sensors/summary",
            headers=self.headers,
        )

    @task(2)  # 가중치: 2
    def list_workflows(self):
        """워크플로우 목록 조회"""
        if not self.token:
            return

        self.client.get(
            "/api/v1/workflows",
            headers=self.headers,
            params={"page": 1, "size": 20},
        )

    @task(1)  # 가중치: 1
    def list_rulesets(self):
        """Ruleset 목록 조회"""
        if not self.token:
            return

        self.client.get(
            "/api/v1/rulesets",
            headers=self.headers,
        )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """테스트 시작 시"""
    print("========================================")
    print("TriFlow AI Performance Test Started")
    print("========================================")
    print(f"Host: {environment.host}")
    print(f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    print("========================================")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """테스트 종료 시"""
    print("========================================")
    print("TriFlow AI Performance Test Completed")
    print("========================================")
    print("Performance Targets (Spec NFR-PERF):")
    print("- Judgment P95 < 2.5s")
    print("- BI P95 < 3s")
    print("- Throughput: 50 TPS")
    print("========================================")
    print("Check results at: http://localhost:8089")
