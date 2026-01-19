# -*- coding: utf-8 -*-
"""
Alerts Router

Prometheus AlertManager webhook 수신용 엔드포인트
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from app.services.alert_handler import alert_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


class Alert(BaseModel):
    """Alert 정보"""
    status: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    startsAt: str
    endsAt: str


class AlertWebhook(BaseModel):
    """AlertManager webhook payload"""
    alerts: List[Alert]


@router.post("/webhook")
async def receive_alert_webhook(webhook: AlertWebhook):
    """
    Prometheus AlertManager webhook 수신

    AlertManager에서 alerts.yml 규칙 발동 시 호출됨.
    Slack/Email 알림을 전송합니다.
    """
    try:
        logger.info(f"Received alert webhook with {len(webhook.alerts)} alerts")
        await alert_handler.handle_prometheus_alert(webhook.dict())
        return {"status": "success", "processed": len(webhook.alerts)}
    except Exception as e:
        logger.error(f"Failed to process alert webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test")
async def test_alert_system():
    """
    Alert 시스템 테스트용 엔드포인트

    수동으로 테스트 Alert를 발생시킵니다.
    """
    test_alert_data = {
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "TestAlert", "severity": "info"},
                "annotations": {
                    "summary": "Alert 시스템 테스트",
                    "description": "이것은 테스트 알람입니다"
                },
                "startsAt": "2026-01-19T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z"
            }
        ]
    }

    try:
        await alert_handler.handle_prometheus_alert(test_alert_data)
        return {"status": "success", "message": "Test alert sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
