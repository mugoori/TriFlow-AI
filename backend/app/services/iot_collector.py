"""
IoT 데이터 수집 서비스
스펙 참조: INT-REQ-020

지원 프로토콜:
- MQTT (센서 데이터 실시간 수집)
- OPC UA (산업 자동화 표준)

기능:
- 실시간 센서 데이터 수집
- 버퍼링 (네트워크 장애 시)
- 데이터 검증 및 저장
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from collections import deque
import threading

logger = logging.getLogger(__name__)


# ============================================================================
# MQTT Collector
# ============================================================================

class MQTTCollector:
    """
    MQTT 기반 센서 데이터 수집기

    사용 예시:
        collector = MQTTCollector(
            broker_host="mqtt.factory.com",
            broker_port=1883,
            topics=["sensor/#"]
        )
        collector.set_message_handler(save_sensor_data)
        collector.start()
    """

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        topics: List[str] = None,
        qos: int = 1,
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.topics = topics or ["sensor/#"]
        self.qos = qos

        self._client = None
        self._message_handler: Optional[Callable] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # 버퍼 (네트워크 장애 시 데이터 보존)
        self._buffer: deque = deque(maxlen=10000)
        self._buffer_enabled = True

    def set_message_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """메시지 핸들러 등록"""
        self._message_handler = handler

    def start(self):
        """MQTT 수집기 시작"""
        if self._running:
            logger.warning("MQTT collector is already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"MQTT collector started: {self.broker_host}:{self.broker_port}")

    def stop(self):
        """MQTT 수집기 중지"""
        self._running = False
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("MQTT collector stopped")

    def _run_loop(self):
        """MQTT 수집 루프 (별도 스레드)"""
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.error("paho-mqtt not installed. Run: pip install paho-mqtt")
            return

        # MQTT 클라이언트 생성
        self._client = mqtt.Client()

        # 인증 설정
        if self.username and self.password:
            self._client.username_pw_set(self.username, self.password)

        # 콜백 설정
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

        # 연결
        try:
            self._client.connect(self.broker_host, self.broker_port, 60)
            self._client.loop_forever()
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            self._running = False

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT 연결 콜백"""
        if rc == 0:
            logger.info("MQTT connected successfully")

            # 토픽 구독
            for topic in self.topics:
                client.subscribe(topic, qos=self.qos)
                logger.info(f"Subscribed to topic: {topic}")
        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """MQTT 연결 해제 콜백"""
        if rc != 0:
            logger.warning(f"MQTT disconnected unexpectedly: {rc}")

    def _on_message(self, client, userdata, msg):
        """MQTT 메시지 수신 콜백"""
        try:
            # 토픽 파싱: sensor/LINE_A/temperature → line=LINE_A, type=temperature
            topic_parts = msg.topic.split("/")

            if len(topic_parts) >= 3:
                line_code = topic_parts[1]
                sensor_type = topic_parts[2]
            else:
                line_code = "UNKNOWN"
                sensor_type = "UNKNOWN"

            # 페이로드 파싱
            try:
                payload = json.loads(msg.payload.decode())
            except json.JSONDecodeError:
                # JSON이 아니면 문자열 그대로
                payload = {"value": msg.payload.decode()}

            # 데이터 구조화
            sensor_data = {
                "topic": msg.topic,
                "line_code": payload.get("line_code", line_code),
                "sensor_type": payload.get("sensor_type", sensor_type),
                "value": payload.get("value"),
                "unit": payload.get("unit"),
                "timestamp": payload.get("timestamp", datetime.utcnow().isoformat()),
                "metadata": payload.get("metadata", {}),
            }

            # 핸들러 호출
            if self._message_handler:
                try:
                    self._message_handler(sensor_data)
                except Exception as e:
                    logger.error(f"Message handler error: {e}")
                    # 버퍼에 저장
                    if self._buffer_enabled:
                        self._buffer.append(sensor_data)
            else:
                # 핸들러 없으면 버퍼에 저장
                if self._buffer_enabled:
                    self._buffer.append(sensor_data)

        except Exception as e:
            logger.error(f"Failed to process MQTT message: {e}")

    def get_buffered_data(self) -> List[Dict[str, Any]]:
        """버퍼된 데이터 조회 및 클리어"""
        data = list(self._buffer)
        self._buffer.clear()
        return data


# ============================================================================
# OPC UA Collector
# ============================================================================

class OPCUACollector:
    """
    OPC UA 기반 센서 데이터 수집기

    사용 예시:
        collector = OPCUACollector(
            server_url="opc.tcp://plc.factory.com:4840"
        )
        collector.add_node("ns=2;s=LINE-A.Temperature", "temperature")
        collector.set_data_handler(save_sensor_data)
        await collector.start()
    """

    def __init__(
        self,
        server_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        poll_interval: float = 1.0,
    ):
        self.server_url = server_url
        self.username = username
        self.password = password
        self.poll_interval = poll_interval

        self._client = None
        self._nodes: Dict[str, str] = {}  # {node_id: sensor_type}
        self._data_handler: Optional[Callable] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def add_node(self, node_id: str, sensor_type: str):
        """모니터링할 노드 추가"""
        self._nodes[node_id] = sensor_type

    def set_data_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """데이터 핸들러 등록"""
        self._data_handler = handler

    async def start(self):
        """OPC UA 수집기 시작"""
        if self._running:
            logger.warning("OPC UA collector is already running")
            return

        try:
            from opcua import Client
        except ImportError:
            logger.error("opcua library not installed. Run: pip install opcua")
            return

        try:
            # 클라이언트 생성 및 연결
            self._client = Client(self.server_url)

            # 인증 설정
            if self.username and self.password:
                self._client.set_user(self.username)
                self._client.set_password(self.password)

            self._client.connect()
            logger.info(f"OPC UA connected: {self.server_url}")

            self._running = True
            self._task = asyncio.create_task(self._poll_loop())

        except Exception as e:
            logger.error(f"OPC UA connection failed: {e}")
            self._running = False

    async def stop(self):
        """OPC UA 수집기 중지"""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._client:
            self._client.disconnect()
            logger.info("OPC UA disconnected")

    async def _poll_loop(self):
        """폴링 루프 (주기적 노드 읽기)"""
        while self._running:
            try:
                for node_id, sensor_type in self._nodes.items():
                    try:
                        # 노드 읽기
                        node = self._client.get_node(node_id)
                        value = node.get_value()

                        # 데이터 구조화
                        sensor_data = {
                            "node_id": node_id,
                            "sensor_type": sensor_type,
                            "value": value,
                            "timestamp": datetime.utcnow().isoformat(),
                        }

                        # 핸들러 호출
                        if self._data_handler:
                            self._data_handler(sensor_data)

                    except Exception as e:
                        logger.error(f"Failed to read OPC UA node {node_id}: {e}")

                # 폴링 간격 대기
                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"OPC UA polling error: {e}")
                await asyncio.sleep(self.poll_interval)


# ============================================================================
# IoT Collector Manager
# ============================================================================

class IoTCollectorManager:
    """
    IoT 데이터 수집 관리자

    MQTT, OPC UA 수집기를 통합 관리
    """

    def __init__(self):
        self.mqtt_collectors: Dict[str, MQTTCollector] = {}
        self.opcua_collectors: Dict[str, OPCUACollector] = {}

    def add_mqtt_collector(
        self,
        collector_id: str,
        broker_host: str,
        broker_port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        topics: List[str] = None,
    ) -> MQTTCollector:
        """MQTT 수집기 추가"""
        collector = MQTTCollector(
            broker_host=broker_host,
            broker_port=broker_port,
            username=username,
            password=password,
            topics=topics,
        )
        self.mqtt_collectors[collector_id] = collector
        return collector

    def add_opcua_collector(
        self,
        collector_id: str,
        server_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> OPCUACollector:
        """OPC UA 수집기 추가"""
        collector = OPCUACollector(
            server_url=server_url,
            username=username,
            password=password,
        )
        self.opcua_collectors[collector_id] = collector
        return collector

    def start_all(self):
        """모든 수집기 시작"""
        for collector_id, collector in self.mqtt_collectors.items():
            try:
                collector.start()
                logger.info(f"Started MQTT collector: {collector_id}")
            except Exception as e:
                logger.error(f"Failed to start MQTT collector {collector_id}: {e}")

        for collector_id, collector in self.opcua_collectors.items():
            try:
                asyncio.create_task(collector.start())
                logger.info(f"Started OPC UA collector: {collector_id}")
            except Exception as e:
                logger.error(f"Failed to start OPC UA collector {collector_id}: {e}")

    def stop_all(self):
        """모든 수집기 중지"""
        for collector in self.mqtt_collectors.values():
            collector.stop()

        for collector in self.opcua_collectors.values():
            asyncio.create_task(collector.stop())

    def get_status(self) -> Dict[str, Any]:
        """수집기 상태 조회"""
        return {
            "mqtt_collectors": {
                collector_id: {"running": collector._running, "buffer_size": len(collector._buffer)}
                for collector_id, collector in self.mqtt_collectors.items()
            },
            "opcua_collectors": {
                collector_id: {"running": collector._running}
                for collector_id, collector in self.opcua_collectors.items()
            },
        }


# ============================================================================
# 센서 데이터 저장 핸들러
# ============================================================================

def save_sensor_data_handler(sensor_data: Dict[str, Any]):
    """
    센서 데이터 저장 핸들러

    MQTT/OPC UA 수집기가 호출하는 콜백 함수
    """
    from app.database import SessionLocal
    from app.models import SensorData

    try:
        db = SessionLocal()

        # SensorData 모델 생성
        sensor = SensorData(
            line_code=sensor_data.get("line_code", "UNKNOWN"),
            sensor_type=sensor_data.get("sensor_type", "UNKNOWN"),
            value=sensor_data.get("value"),
            unit=sensor_data.get("unit"),
            recorded_at=datetime.fromisoformat(sensor_data["timestamp"])
            if sensor_data.get("timestamp")
            else datetime.utcnow(),
        )

        db.add(sensor)
        db.commit()

        logger.debug(
            f"Sensor data saved: {sensor.line_code}/{sensor.sensor_type} = {sensor.value}"
        )

    except Exception as e:
        logger.error(f"Failed to save sensor data: {e}")
    finally:
        db.close()


# ============================================================================
# 전역 수집기 매니저
# ============================================================================

_iot_manager: Optional[IoTCollectorManager] = None


def get_iot_manager() -> IoTCollectorManager:
    """IoT 수집기 매니저 싱글톤"""
    global _iot_manager
    if _iot_manager is None:
        _iot_manager = IoTCollectorManager()
    return _iot_manager


def setup_iot_collectors():
    """
    IoT 수집기 초기 설정 (환경변수 기반)

    환경변수:
    - MQTT_BROKER_HOST: MQTT 브로커 주소
    - MQTT_BROKER_PORT: MQTT 브로커 포트 (기본: 1883)
    - MQTT_USERNAME: MQTT 사용자명
    - MQTT_PASSWORD: MQTT 비밀번호
    - MQTT_TOPICS: 구독 토픽 (콤마 구분, 기본: sensor/#)
    - OPCUA_SERVER_URL: OPC UA 서버 URL
    - OPCUA_USERNAME: OPC UA 사용자명
    - OPCUA_PASSWORD: OPC UA 비밀번호
    """
    import os

    manager = get_iot_manager()

    # MQTT 수집기 설정
    mqtt_host = os.getenv("MQTT_BROKER_HOST")
    if mqtt_host:
        mqtt_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        mqtt_username = os.getenv("MQTT_USERNAME")
        mqtt_password = os.getenv("MQTT_PASSWORD")
        mqtt_topics = os.getenv("MQTT_TOPICS", "sensor/#").split(",")

        collector = manager.add_mqtt_collector(
            collector_id="default_mqtt",
            broker_host=mqtt_host,
            broker_port=mqtt_port,
            username=mqtt_username,
            password=mqtt_password,
            topics=mqtt_topics,
        )
        collector.set_message_handler(save_sensor_data_handler)
        collector.start()

        logger.info(f"MQTT collector configured: {mqtt_host}:{mqtt_port}")
    else:
        logger.info("MQTT collector not configured (MQTT_BROKER_HOST not set)")

    # OPC UA 수집기 설정
    opcua_url = os.getenv("OPCUA_SERVER_URL")
    if opcua_url:
        opcua_username = os.getenv("OPCUA_USERNAME")
        opcua_password = os.getenv("OPCUA_PASSWORD")

        collector = manager.add_opcua_collector(
            collector_id="default_opcua",
            server_url=opcua_url,
            username=opcua_username,
            password=opcua_password,
        )

        # 모니터링 노드 등록 (환경변수 또는 설정 파일에서 로드)
        # 예: OPCUA_NODES=ns=2;s=LINE-A.Temperature:temperature,ns=2;s=LINE-A.Pressure:pressure
        opcua_nodes = os.getenv("OPCUA_NODES", "").split(",")
        for node_config in opcua_nodes:
            if ":" in node_config:
                node_id, sensor_type = node_config.split(":")
                collector.add_node(node_id, sensor_type)

        collector.set_data_handler(save_sensor_data_handler)
        asyncio.create_task(collector.start())

        logger.info(f"OPC UA collector configured: {opcua_url}")
    else:
        logger.info("OPC UA collector not configured (OPCUA_SERVER_URL not set)")
