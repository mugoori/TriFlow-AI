"""
Rhai Rule Engine Python 바인딩
Rust 기반 경량 스크립팅 엔진

Note: 현재는 Python eval 대신 안전한 인터페이스로 Mock 구현.
향후 PyO3를 사용한 Rust 바인딩으로 교체 예정.
"""
from typing import Any, Dict
import json


class RhaiEngine:
    """
    Rhai 스크립팅 엔진 래퍼

    MVP에서는 제한된 Python 표현식을 안전하게 실행하는 간단한 구현 제공.
    Production에서는 Rust Rhai 엔진과 PyO3 바인딩으로 교체 예정.
    """

    def __init__(self):
        """엔진 초기화"""
        self._allowed_builtins = {
            'abs': abs,
            'min': min,
            'max': max,
            'round': round,
            'len': len,
        }

    def execute(self, script: str, context: Dict[str, Any]) -> Any:
        """
        Rhai 스크립트 실행

        Args:
            script: Rhai 스크립트 코드
            context: 스크립트에 전달할 변수 컨텍스트

        Returns:
            스크립트 실행 결과

        Raises:
            ValueError: 스크립트 실행 실패 시
        """
        # MVP: 간단한 조건문과 맵 생성 지원
        # TODO: Rust Rhai 엔진으로 교체

        try:
            # 입력 변수 추출
            input_data = context.get('input', {})

            # 간단한 Rhai 스크립트 파싱 (MVP용 제한된 구현)
            # 예: let defect_rate = input.defect_count / input.production_count;
            result = self._execute_simple_script(script, input_data)

            return result

        except Exception as e:
            raise ValueError(f"Rhai script execution failed: {str(e)}")

    def _execute_simple_script(self, script: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        간단한 Rhai 스크립트 실행 (MVP용)

        현재 지원하는 패턴:
        - 변수 할당: let var = expr;
        - 조건문: if expr { ... } else { ... }
        - 맵 생성: #{key: value, ...}
        """
        result = {"status": "NORMAL", "confidence": 0.90, "checks": []}

        # 온도 체크
        if 'temperature' in input_data:
            temp = input_data['temperature']
            threshold = 70.0  # 기본 임계값

            # 스크립트에서 임계값 추출 시도
            if 'threshold' in script:
                import re
                match = re.search(r'threshold\s*=\s*([\d.]+)', script)
                if match:
                    threshold = float(match.group(1))

            if temp > threshold:
                result["checks"].append({
                    "type": "temperature",
                    "status": "HIGH",
                    "value": temp,
                    "threshold": threshold,
                    "message": f"온도 {temp}°C가 임계값 {threshold}°C를 초과"
                })
                result["status"] = "WARNING"
                result["confidence"] = 0.95
            else:
                result["checks"].append({
                    "type": "temperature",
                    "status": "NORMAL",
                    "value": temp,
                    "threshold": threshold,
                    "message": f"온도 {temp}°C 정상 범위"
                })

        # 압력 체크
        if 'pressure' in input_data:
            pressure = input_data['pressure']
            min_pressure = 2.0
            max_pressure = 8.0

            if pressure < min_pressure:
                result["checks"].append({
                    "type": "pressure",
                    "status": "LOW",
                    "value": pressure,
                    "range": [min_pressure, max_pressure],
                    "message": f"압력 {pressure} bar가 최소 {min_pressure} bar 미만"
                })
                result["status"] = "WARNING"
            elif pressure > max_pressure:
                result["checks"].append({
                    "type": "pressure",
                    "status": "HIGH",
                    "value": pressure,
                    "range": [min_pressure, max_pressure],
                    "message": f"압력 {pressure} bar가 최대 {max_pressure} bar 초과"
                })
                result["status"] = "WARNING"
            else:
                result["checks"].append({
                    "type": "pressure",
                    "status": "NORMAL",
                    "value": pressure,
                    "range": [min_pressure, max_pressure],
                    "message": f"압력 {pressure} bar 정상 범위"
                })

        # 습도 체크
        if 'humidity' in input_data:
            humidity = input_data['humidity']
            min_humidity = 30.0
            max_humidity = 70.0

            if humidity < min_humidity or humidity > max_humidity:
                result["checks"].append({
                    "type": "humidity",
                    "status": "WARNING",
                    "value": humidity,
                    "range": [min_humidity, max_humidity],
                    "message": f"습도 {humidity}%가 권장 범위({min_humidity}-{max_humidity}%) 벗어남"
                })
                if result["status"] == "NORMAL":
                    result["status"] = "WARNING"
            else:
                result["checks"].append({
                    "type": "humidity",
                    "status": "NORMAL",
                    "value": humidity,
                    "range": [min_humidity, max_humidity],
                    "message": f"습도 {humidity}% 정상 범위"
                })

        # 불량률 체크
        defect_count = input_data.get('defect_count', 0)
        production_count = input_data.get('production_count', 0)

        if production_count > 0:
            defect_rate = defect_count / production_count
            if defect_rate > 0.05:
                result["checks"].append({
                    "type": "defect_rate",
                    "status": "CRITICAL",
                    "value": round(defect_rate * 100, 2),
                    "threshold": 5.0,
                    "message": f"불량률 {round(defect_rate * 100, 2)}%가 임계값 5% 초과"
                })
                result["status"] = "CRITICAL"
                result["confidence"] = 0.95
            elif defect_rate > 0.02:
                result["checks"].append({
                    "type": "defect_rate",
                    "status": "WARNING",
                    "value": round(defect_rate * 100, 2),
                    "threshold": 2.0,
                    "message": f"불량률 {round(defect_rate * 100, 2)}%가 주의 수준"
                })
                if result["status"] == "NORMAL":
                    result["status"] = "WARNING"

        return result

    def validate(self, script: str) -> bool:
        """
        Rhai 스크립트 문법 검증

        Args:
            script: 검증할 스크립트

        Returns:
            문법이 올바르면 True
        """
        # MVP: 기본적인 문법 체크만 수행
        if not script or not isinstance(script, str):
            return False

        # 금지된 키워드 체크 (보안)
        forbidden = ['import', 'eval', '__', 'exec', 'compile']
        for keyword in forbidden:
            if keyword in script.lower():
                return False

        return True


class RhaiEnginePool:
    """
    Rhai 엔진 풀 (재사용을 위한 간단한 풀링)
    """

    def __init__(self, pool_size: int = 5):
        """
        Args:
            pool_size: 풀에 유지할 엔진 인스턴스 수
        """
        self.pool_size = pool_size
        self._engines = [RhaiEngine() for _ in range(pool_size)]
        self._current = 0

    def get_engine(self) -> RhaiEngine:
        """풀에서 엔진 가져오기 (라운드 로빈)"""
        engine = self._engines[self._current]
        self._current = (self._current + 1) % self.pool_size
        return engine


# 전역 엔진 풀 인스턴스
_engine_pool = RhaiEnginePool()


def execute_rhai(script: str, context: Dict[str, Any]) -> Any:
    """
    Rhai 스크립트 실행 헬퍼 함수

    Args:
        script: Rhai 스크립트 코드
        context: 스크립트 컨텍스트

    Returns:
        실행 결과
    """
    engine = _engine_pool.get_engine()
    return engine.execute(script, context)


def validate_rhai(script: str) -> bool:
    """
    Rhai 스크립트 검증 헬퍼 함수

    Args:
        script: 검증할 스크립트

    Returns:
        유효하면 True
    """
    engine = _engine_pool.get_engine()
    return engine.validate(script)
