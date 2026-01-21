# -*- coding: utf-8 -*-
"""
Alert Handler Service

Prometheus AlertManager webhook을 받아서
Slack/Email 알림을 전송합니다.
"""

from typing import Dict, Any
from datetime import datetime
import logging

from app.services.notifications import notification_manager
from app.utils.decorators import handle_service_errors

logger = logging.getLogger(__name__)


class AlertHandler:
    """Alert 처리 서비스"""

    async def handle_prometheus_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Prometheus AlertManager webhook 처리

        alert_data 구조:
        {
            "alerts": [
                {
                    "status": "firing" | "resolved",
                    "labels": {"alertname": "...", "severity": "..."},
                    "annotations": {"summary": "...", "description": "..."},
                    "startsAt": "...",
                    "endsAt": "..."
                }
            ]
        }
        """
        alerts = alert_data.get("alerts", [])

        logger.info(f"Received {len(alerts)} alerts from Prometheus AlertManager")

        for alert in alerts:
            status = alert.get("status")
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})

            alertname = labels.get("alertname", "Unknown")
            severity = labels.get("severity", "info")
            summary = annotations.get("summary", "No summary")
            description = annotations.get("description", "")

            logger.info(
                f"Processing alert: {alertname} (severity={severity}, status={status})"
            )

            # 알림 메시지 생성
            message = self._format_alert_message(
                status, alertname, severity, summary, description
            )

            # Severity에 따라 채널 선택
            await self._send_alert_notification(severity, alertname, summary, message)

        return True

    @handle_service_errors(resource="alert", operation="send")
    async def _send_alert_notification(
        self, severity: str, alertname: str, summary: str, message: str
    ):
        """알림 전송 (Decorator로 에러 처리)"""
        if severity == "critical":
            # Slack + Email 모두
            await notification_manager.send_slack(message, channel="#alerts")
            await notification_manager.send_email(
                to=["admin@example.com"],
                subject=f"🚨 CRITICAL: {alertname}",
                body=message,
            )
            logger.info(f"Sent critical alert to Slack and Email: {alertname}")
        elif severity == "warning":
            # Slack만
            await notification_manager.send_slack(message, channel="#alerts")
            logger.info(f"Sent warning alert to Slack: {alertname}")
        else:
            # Info - 로그만
            logger.info(f"Alert (info): {alertname} - {summary}")

    def _format_alert_message(
        self, status: str, alertname: str, severity: str, summary: str, description: str
    ) -> str:
        """Alert 메시지 포맷"""
        emoji = "🔥" if status == "firing" else "✅"
        severity_emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(
            severity, "📊"
        )

        return f"""{emoji} **Alert {status.upper()}**

{severity_emoji} **{alertname}** ({severity})
{summary}

{description}

Time: {datetime.utcnow().isoformat()}
"""


# 싱글톤 인스턴스
alert_handler = AlertHandler()
