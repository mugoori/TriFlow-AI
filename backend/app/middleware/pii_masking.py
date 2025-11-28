"""
PII 마스킹 미들웨어
Request Body와 Response Body에서 개인정보를 감지하고 마스킹
특히 LLM으로 전송되는 채팅 메시지의 민감정보 차단이 주 목적
"""
import json
import logging
from typing import Callable, List, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.types import ASGIApp

from app.utils.pii_patterns import mask_pii, contains_pii

logger = logging.getLogger(__name__)


class PIIMaskingFilter(logging.Filter):
    """
    로깅 필터: 로그 메시지에서 PII 마스킹
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            masked, detected = mask_pii(record.msg)
            if detected:
                record.msg = masked
        return True


class PIIMaskingMiddleware(BaseHTTPMiddleware):
    """
    PII 마스킹 미들웨어

    기능:
    1. Request Body 마스킹 (특히 /agents/chat 엔드포인트)
    2. Response Body 마스킹
    3. 로깅 시 PII 마스킹

    설정:
    - enabled: 마스킹 활성화 여부
    - mask_request: Request Body 마스킹 여부
    - mask_response: Response Body 마스킹 여부
    - target_paths: 마스킹 적용 경로 (기본: /agents/)
    - exclude_paths: 마스킹 제외 경로
    """

    def __init__(
        self,
        app: ASGIApp,
        enabled: bool = True,
        mask_request: bool = True,
        mask_response: bool = True,
        target_paths: List[str] = None,
        exclude_paths: List[str] = None,
    ):
        super().__init__(app)
        self.enabled = enabled
        self.mask_request = mask_request
        self.mask_response = mask_response
        self.target_paths: Set[str] = set(target_paths or ["/api/v1/agents/"])
        self.exclude_paths: Set[str] = set(exclude_paths or ["/health", "/docs", "/redoc", "/openapi.json"])

        # 로거에 PII 필터 추가
        self._setup_logging_filter()

    def _setup_logging_filter(self):
        """루트 로거에 PII 마스킹 필터 추가"""
        pii_filter = PIIMaskingFilter()
        root_logger = logging.getLogger()
        root_logger.addFilter(pii_filter)

    def _should_mask(self, path: str) -> bool:
        """해당 경로에 마스킹을 적용해야 하는지 확인"""
        if not self.enabled:
            return False

        # 제외 경로 체크
        for exclude in self.exclude_paths:
            if path.startswith(exclude):
                return False

        # 대상 경로 체크
        for target in self.target_paths:
            if path.startswith(target):
                return True

        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        미들웨어 메인 로직
        """
        path = request.url.path

        # 마스킹 대상이 아니면 바로 통과
        if not self._should_mask(path):
            return await call_next(request)

        # Request Body 마스킹
        if self.mask_request and request.method in ["POST", "PUT", "PATCH"]:
            request = await self._mask_request_body(request)

        # 원본 요청 처리
        response = await call_next(request)

        # Response Body 마스킹
        if self.mask_response:
            response = await self._mask_response_body(response)

        return response

    async def _mask_request_body(self, request: Request) -> Request:
        """
        Request Body에서 PII 마스킹
        특히 채팅 메시지의 'message' 필드를 대상으로 함
        """
        try:
            content_type = request.headers.get("content-type", "")

            if "application/json" not in content_type:
                return request

            # Body 읽기
            body = await request.body()
            if not body:
                return request

            body_str = body.decode("utf-8")
            body_json = json.loads(body_str)

            # 마스킹 적용
            masked = False

            # 채팅 메시지 필드 마스킹
            if "message" in body_json and isinstance(body_json["message"], str):
                original_message = body_json["message"]
                if contains_pii(original_message):
                    masked_message, detected = mask_pii(original_message)
                    body_json["message"] = masked_message
                    masked = True
                    logger.warning(
                        f"PII detected and masked in request: "
                        f"{len(detected)} item(s) - {[d['description'] for d in detected]}"
                    )

            # context 내부 검사
            if "context" in body_json and isinstance(body_json["context"], dict):
                for key, value in body_json["context"].items():
                    if isinstance(value, str) and contains_pii(value):
                        masked_value, detected = mask_pii(value)
                        body_json["context"][key] = masked_value
                        masked = True

            if masked:
                # 마스킹된 body로 새 request 생성
                new_body = json.dumps(body_json, ensure_ascii=False).encode("utf-8")

                # Request 객체 재구성
                scope = request.scope.copy()
                scope["_body"] = new_body

                async def receive():
                    return {"type": "http.request", "body": new_body}

                request = Request(scope, receive, request._send)
                request._body = new_body

            return request

        except json.JSONDecodeError:
            logger.debug("Request body is not valid JSON, skipping PII masking")
            return request
        except Exception as e:
            logger.error(f"Error masking request body: {e}")
            return request

    async def _mask_response_body(self, response: Response) -> Response:
        """
        Response Body에서 PII 마스킹
        """
        try:
            # StreamingResponse 처리
            if isinstance(response, StreamingResponse):
                return response

            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return response

            # Body 읽기
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            if not body:
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )

            body_str = body.decode("utf-8")
            body_json = json.loads(body_str)

            # 마스킹 적용
            masked = False

            # response 필드 마스킹 (Agent 응답)
            if "response" in body_json and isinstance(body_json["response"], str):
                original_response = body_json["response"]
                if contains_pii(original_response):
                    masked_response, detected = mask_pii(original_response)
                    body_json["response"] = masked_response
                    masked = True
                    logger.warning(
                        f"PII detected and masked in response: "
                        f"{len(detected)} item(s) - {[d['description'] for d in detected]}"
                    )

            # tool_calls 내부 검사
            if "tool_calls" in body_json and isinstance(body_json["tool_calls"], list):
                for tool_call in body_json["tool_calls"]:
                    if "result" in tool_call and isinstance(tool_call["result"], dict):
                        result_str = json.dumps(tool_call["result"], ensure_ascii=False)
                        if contains_pii(result_str):
                            masked_result_str, _ = mask_pii(result_str)
                            tool_call["result"] = json.loads(masked_result_str)
                            masked = True

            if masked:
                new_body = json.dumps(body_json, ensure_ascii=False).encode("utf-8")
            else:
                new_body = body

            return Response(
                content=new_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        except json.JSONDecodeError:
            return response
        except Exception as e:
            logger.error(f"Error masking response body: {e}")
            return response
