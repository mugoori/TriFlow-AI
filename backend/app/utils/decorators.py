# -*- coding: utf-8 -*-
"""
Decorators
공통 데코레이터 함수
"""
import functools
import logging
import asyncio
from typing import Callable, Any
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def handle_service_errors(
    resource: str,
    operation: str = None,
    status_code: int = 500
):
    """
    서비스 에러를 일관되게 처리하는 데코레이터
    
    Args:
        resource: 리소스 이름 (예: "workflow", "user")
        operation: 작업명 (예: "execute", "create")
        status_code: 기본 HTTP 상태 코드
        
    Usage:
        @handle_service_errors(resource="workflow", operation="execute")
        async def execute_workflow(self, workflow_id: UUID):
            # 비즈니스 로직
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # HTTPException은 그대로 전파
                raise
            except ValueError as e:
                # Validation 에러
                logger.warning(f"{resource} validation error: {e}")
                raise HTTPException(status_code=400, detail=str(e))
            except PermissionError as e:
                # 권한 에러
                logger.warning(f"{resource} permission denied: {e}")
                raise HTTPException(status_code=403, detail=str(e))
            except Exception as e:
                # 예상치 못한 에러
                op_msg = f" during {operation}" if operation else ""
                logger.error(
                    f"Error in {resource}{op_msg}: {e}",
                    exc_info=True,
                    extra={
                        "resource": resource,
                        "operation": operation,
                        "error_type": type(e).__name__
                    }
                )
                raise HTTPException(
                    status_code=status_code,
                    detail=f"Failed to process {resource}: {str(e)}"
                )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except HTTPException:
                raise
            except ValueError as e:
                logger.warning(f"{resource} validation error: {e}")
                raise HTTPException(status_code=400, detail=str(e))
            except PermissionError as e:
                logger.warning(f"{resource} permission denied: {e}")
                raise HTTPException(status_code=403, detail=str(e))
            except Exception as e:
                op_msg = f" during {operation}" if operation else ""
                logger.error(
                    f"Error in {resource}{op_msg}: {e}",
                    exc_info=True
                )
                raise HTTPException(
                    status_code=status_code,
                    detail=f"Failed to process {resource}: {str(e)}"
                )
        
        # async/sync 함수 자동 판별
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
