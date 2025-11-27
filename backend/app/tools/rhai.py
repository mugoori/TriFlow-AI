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
        # 샘플 데이터 기반 간단한 로직 실행
        # 예제: defect rate 체크
        defect_count = input_data.get('defect_count', 0)
        production_count = input_data.get('production_count', 1)

        if production_count == 0:
            production_count = 1  # division by zero 방지

        defect_rate = defect_count / production_count

        # Rhai 조건문 파싱 (매우 간단한 구현)
        if 'if defect_rate >' in script:
            if '> 0.05' in script and defect_rate > 0.05:
                return {"status": "HIGH_DEFECT", "confidence": 0.95}
            elif '> 0.02' in script and defect_rate > 0.02:
                return {"status": "WARNING", "confidence": 0.80}
            else:
                return {"status": "NORMAL", "confidence": 0.90}

        # 기본 반환값
        return {"status": "UNKNOWN", "confidence": 0.0, "defect_rate": defect_rate}

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
