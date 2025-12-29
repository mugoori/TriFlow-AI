"""
TriFlow AI - Workflow Tests
============================
Tests for workflow endpoints
"""

import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from uuid import uuid4


class TestWorkflowEndpoints:
    """Test workflow CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_list_workflows(self, authenticated_client: AsyncClient):
        """Test listing workflows."""
        response = await authenticated_client.get("/api/v1/workflows")
        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data or isinstance(data, list)

    @pytest.mark.asyncio
    async def test_create_workflow(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test creating a workflow."""
        response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data or "workflow_id" in data

    @pytest.mark.asyncio
    async def test_get_workflow(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test getting a specific workflow."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        assert create_response.status_code in [200, 201]
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Get
        response = await authenticated_client.get(f"/api/v1/workflows/{workflow_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_workflow_data["name"]

    @pytest.mark.asyncio
    async def test_update_workflow(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test updating a workflow."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Update (PATCH, not PUT)
        updated_data = {"name": "Updated Workflow Name"}
        response = await authenticated_client.patch(
            f"/api/v1/workflows/{workflow_id}",
            json=updated_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Workflow Name"

    @pytest.mark.asyncio
    async def test_delete_workflow(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test deleting a workflow."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Delete
        response = await authenticated_client.delete(f"/api/v1/workflows/{workflow_id}")
        assert response.status_code in [200, 204]

        # Verify deleted
        get_response = await authenticated_client.get(f"/api/v1/workflows/{workflow_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_toggle_workflow_active(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test toggling workflow active status."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Toggle (POST method)
        response = await authenticated_client.post(
            f"/api/v1/workflows/{workflow_id}/toggle"
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_active" in data
        assert "message" in data
        # 최초 생성 시 is_active=True이므로 토글 후 False
        assert data["is_active"] is False

        # 다시 토글하면 True
        response2 = await authenticated_client.post(
            f"/api/v1/workflows/{workflow_id}/toggle"
        )
        assert response2.status_code == 200
        assert response2.json()["is_active"] is True


class TestWorkflowExecution:
    """Test workflow execution."""

    @pytest.mark.asyncio
    async def test_execute_workflow(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test manual workflow execution."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Execute
        response = await authenticated_client.post(
            f"/api/v1/workflows/{workflow_id}/execute",
            json={"context": {"temperature": 85}}
        )
        assert response.status_code == 200
        data = response.json()
        assert "instance_id" in data
        assert "status" in data
        assert data["workflow_id"] == workflow_id

    @pytest.mark.asyncio
    async def test_get_workflow_history(
        self,
        authenticated_client: AsyncClient,
        sample_workflow_data
    ):
        """Test getting workflow execution history."""
        # Create first
        create_response = await authenticated_client.post(
            "/api/v1/workflows",
            json=sample_workflow_data
        )
        workflow_id = create_response.json().get("id") or create_response.json().get("workflow_id")

        # Get history
        response = await authenticated_client.get(
            f"/api/v1/workflows/{workflow_id}/history"
        )
        assert response.status_code in [200, 404]


class TestActionCatalog:
    """Test action catalog endpoints."""

    @pytest.mark.asyncio
    async def test_get_action_catalog(self, authenticated_client: AsyncClient):
        """Test getting available actions."""
        response = await authenticated_client.get("/api/v1/workflows/actions")
        assert response.status_code == 200
        data = response.json()
        assert "actions" in data
        assert "categories" in data

    @pytest.mark.asyncio
    async def test_action_catalog_structure(self, authenticated_client: AsyncClient):
        """Test action catalog has required fields."""
        response = await authenticated_client.get("/api/v1/workflows/actions")
        data = response.json()

        for action in data.get("actions", []):
            assert "name" in action
            assert "display_name" in action
            assert "category" in action


# ============= Mock 기반 테스트 =============


class TestWorkflowPydanticModels:
    """워크플로우 Pydantic 모델 테스트"""

    def test_workflow_trigger_model(self):
        """WorkflowTrigger 모델"""
        from app.routers.workflows import WorkflowTrigger

        trigger = WorkflowTrigger(
            type="event",
            config={"event_type": "temperature_alert"},
        )

        assert trigger.type == "event"
        assert "event_type" in trigger.config

    def test_workflow_trigger_default_config(self):
        """WorkflowTrigger 기본 config"""
        from app.routers.workflows import WorkflowTrigger

        trigger = WorkflowTrigger(type="manual")

        assert trigger.config == {}

    def test_workflow_node_model(self):
        """WorkflowNode 모델"""
        from app.routers.workflows import WorkflowNode

        node = WorkflowNode(
            id="node-1",
            type="action",
            config={"action": "send_notification"},
            next=["node-2"],
        )

        assert node.id == "node-1"
        assert node.type == "action"
        assert node.next == ["node-2"]

    def test_workflow_node_with_nested(self):
        """WorkflowNode 중첩 노드"""
        from app.routers.workflows import WorkflowNode

        then_node = WorkflowNode(
            id="then-1",
            type="action",
            config={"action": "alert"},
        )

        node = WorkflowNode(
            id="condition-1",
            type="if_else",
            config={"condition": "temperature > 80"},
            then_nodes=[then_node],
        )

        assert node.then_nodes is not None
        assert len(node.then_nodes) == 1

    def test_workflow_dsl_model(self):
        """WorkflowDSL 모델"""
        from app.routers.workflows import WorkflowDSL, WorkflowTrigger, WorkflowNode

        dsl = WorkflowDSL(
            name="테스트 워크플로우",
            description="설명",
            trigger=WorkflowTrigger(type="schedule", config={"cron": "0 * * * *"}),
            nodes=[
                WorkflowNode(id="start", type="action", config={"action": "check"}),
            ],
        )

        assert dsl.name == "테스트 워크플로우"
        assert len(dsl.nodes) == 1

    def test_workflow_create_model(self):
        """WorkflowCreate 모델"""
        from app.routers.workflows import (
            WorkflowCreate,
            WorkflowDSL,
            WorkflowTrigger,
            WorkflowNode,
        )

        create = WorkflowCreate(
            name="새 워크플로우",
            description="테스트",
            dsl_definition=WorkflowDSL(
                name="새 워크플로우",
                trigger=WorkflowTrigger(type="manual"),
                nodes=[],
            ),
        )

        assert create.name == "새 워크플로우"

    def test_workflow_response_model(self):
        """WorkflowResponse 모델"""
        from app.routers.workflows import WorkflowResponse

        response = WorkflowResponse(
            workflow_id=str(uuid4()),
            name="워크플로우",
            description="설명",
            dsl_definition={"name": "test", "trigger": {}, "nodes": []},
            version="1",
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert response.is_active is True

    def test_workflow_list_response_model(self):
        """WorkflowListResponse 모델"""
        from app.routers.workflows import WorkflowListResponse, WorkflowResponse

        list_response = WorkflowListResponse(
            workflows=[
                WorkflowResponse(
                    workflow_id=str(uuid4()),
                    name="워크플로우",
                    description=None,
                    dsl_definition={},
                    version="1",
                    is_active=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                ),
            ],
            total=1,
        )

        assert list_response.total == 1

    def test_workflow_instance_response_model(self):
        """WorkflowInstanceResponse 모델"""
        from app.routers.workflows import WorkflowInstanceResponse

        response = WorkflowInstanceResponse(
            instance_id=str(uuid4()),
            workflow_id=str(uuid4()),
            workflow_name="테스트",
            status="completed",
            input_data={"key": "value"},
            output_data={"result": "success"},
            error_message=None,
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )

        assert response.status == "completed"


class TestSerializeForJson:
    """serialize_for_json 함수 테스트"""

    def test_serialize_uuid(self):
        """UUID 직렬화"""
        from app.routers.workflows import serialize_for_json

        test_uuid = uuid4()
        result = serialize_for_json(test_uuid)

        assert isinstance(result, str)
        assert result == str(test_uuid)

    def test_serialize_datetime(self):
        """datetime 직렬화"""
        from app.routers.workflows import serialize_for_json

        test_datetime = datetime(2024, 1, 15, 10, 30, 0)
        result = serialize_for_json(test_datetime)

        assert isinstance(result, str)
        assert "2024-01-15" in result

    def test_serialize_dict(self):
        """dict 직렬화"""
        from app.routers.workflows import serialize_for_json

        test_uuid = uuid4()
        test_dict = {"id": test_uuid, "name": "test"}
        result = serialize_for_json(test_dict)

        assert isinstance(result["id"], str)
        assert result["name"] == "test"

    def test_serialize_list(self):
        """list 직렬화"""
        from app.routers.workflows import serialize_for_json

        test_uuid = uuid4()
        test_list = [test_uuid, "text", 123]
        result = serialize_for_json(test_list)

        assert isinstance(result[0], str)
        assert result[1] == "text"
        assert result[2] == 123

    def test_serialize_primitive(self):
        """기본 타입 직렬화"""
        from app.routers.workflows import serialize_for_json

        assert serialize_for_json("text") == "text"
        assert serialize_for_json(123) == 123
        assert serialize_for_json(True) is True


class TestWorkflowEndpointsMock:
    """워크플로우 엔드포인트 Mock 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_list_workflows(self, mock_db, mock_user):
        """워크플로우 목록 조회"""
        from app.routers.workflows import list_workflows

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.all.return_value = []

        mock_db.query.return_value = mock_query

        result = await list_workflows(db=mock_db)

        assert hasattr(result, "workflows")
        assert hasattr(result, "total")

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(self, mock_db, mock_user):
        """워크플로우 조회 - 없음"""
        from app.routers.workflows import get_workflow
        from fastapi import HTTPException

        workflow_id = uuid4()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await get_workflow(
                workflow_id=str(workflow_id),
                db=mock_db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_workflow_success(self, mock_db, mock_user):
        """워크플로우 조회 성공"""
        from app.routers.workflows import get_workflow

        workflow_id = uuid4()

        mock_workflow = MagicMock()
        mock_workflow.workflow_id = workflow_id
        mock_workflow.tenant_id = mock_user.tenant_id
        mock_workflow.name = "테스트 워크플로우"
        mock_workflow.description = "설명"
        mock_workflow.dsl_definition = {"name": "test", "trigger": {}, "nodes": []}
        mock_workflow.version = "1"
        mock_workflow.is_active = True
        mock_workflow.created_at = datetime.now()
        mock_workflow.updated_at = datetime.now()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_workflow

        mock_db.query.return_value = mock_query

        result = await get_workflow(
            workflow_id=str(workflow_id),
            db=mock_db,
        )

        assert result.name == "테스트 워크플로우"

    @pytest.mark.asyncio
    async def test_delete_workflow_not_found(self, mock_db, mock_user):
        """워크플로우 삭제 - 없음"""
        from app.routers.workflows import delete_workflow
        from fastapi import HTTPException

        workflow_id = uuid4()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await delete_workflow(
                workflow_id=str(workflow_id),
                db=mock_db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_workflow_success(self, mock_db, mock_user):
        """워크플로우 삭제 성공"""
        from app.routers.workflows import delete_workflow

        workflow_id = uuid4()

        mock_workflow = MagicMock()
        mock_workflow.tenant_id = mock_user.tenant_id

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_workflow

        mock_db.query.return_value = mock_query

        result = await delete_workflow(
            workflow_id=str(workflow_id),
            db=mock_db,
        )

        # delete_workflow returns None on success
        assert result is None
        mock_db.delete.assert_called_once_with(mock_workflow)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_workflow_not_found(self, mock_db, mock_user):
        """워크플로우 토글 - 없음"""
        from app.routers.workflows import toggle_workflow
        from fastapi import HTTPException

        workflow_id = uuid4()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await toggle_workflow(
                workflow_id=str(workflow_id),
                db=mock_db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_toggle_workflow_success(self, mock_db, mock_user):
        """워크플로우 토글 성공"""
        from app.routers.workflows import toggle_workflow

        workflow_id = uuid4()

        mock_workflow = MagicMock()
        mock_workflow.tenant_id = mock_user.tenant_id
        mock_workflow.is_active = True
        mock_workflow.name = "테스트"

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_workflow

        mock_db.query.return_value = mock_query

        result = await toggle_workflow(
            workflow_id=str(workflow_id),
            db=mock_db,
        )

        assert result.is_active is False
        mock_db.commit.assert_called()


class TestWorkflowInstanceResponseModel:
    """워크플로우 인스턴스 응답 모델 테스트"""

    def test_workflow_instance_response_model(self):
        """WorkflowInstanceResponse 모델"""
        from app.routers.workflows import WorkflowInstanceResponse

        now = datetime.now()
        response = WorkflowInstanceResponse(
            instance_id=str(uuid4()),
            workflow_id=str(uuid4()),
            workflow_name="테스트 워크플로우",
            status="completed",
            input_data={"temperature": 85},
            output_data={"result": "success"},
            error_message=None,
            started_at=now,
            completed_at=now,
        )

        assert response.status == "completed"
        assert response.workflow_name == "테스트 워크플로우"

    def test_workflow_instance_response_with_error(self):
        """WorkflowInstanceResponse 에러 포함"""
        from app.routers.workflows import WorkflowInstanceResponse

        now = datetime.now()
        response = WorkflowInstanceResponse(
            instance_id=str(uuid4()),
            workflow_id=str(uuid4()),
            workflow_name="워크플로우",
            status="failed",
            input_data={},
            output_data={},
            error_message="Something went wrong",
            started_at=now,
            completed_at=now,
        )

        assert response.error_message == "Something went wrong"
        assert response.status == "failed"

    def test_workflow_instance_list_response_model(self):
        """WorkflowInstanceListResponse 모델"""
        from app.routers.workflows import WorkflowInstanceListResponse, WorkflowInstanceResponse

        instance = WorkflowInstanceResponse(
            instance_id=str(uuid4()),
            workflow_id=str(uuid4()),
            workflow_name="테스트",
            status="completed",
            input_data={},
            output_data={},
            error_message=None,
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )

        response = WorkflowInstanceListResponse(
            instances=[instance],
            total=1,
        )

        assert len(response.instances) == 1
        assert response.total == 1


class TestActionCatalogMock:
    """액션 카탈로그 Mock 테스트"""

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_get_action_catalog(self, mock_user):
        """액션 카탈로그 조회"""
        from app.routers.workflows import get_action_catalog

        result = await get_action_catalog()

        assert hasattr(result, "actions")
        assert hasattr(result, "categories")
        assert isinstance(result.actions, list)
        assert isinstance(result.categories, list)

    @pytest.mark.asyncio
    async def test_actions_have_required_fields(self, mock_user):
        """액션에 필수 필드 존재"""
        from app.routers.workflows import get_action_catalog

        result = await get_action_catalog()

        for action in result.actions:
            assert hasattr(action, "name")
            assert hasattr(action, "display_name")
            assert hasattr(action, "category")


class TestWorkflowUpdateMock:
    """워크플로우 업데이트 Mock 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock DB 세션"""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Mock 사용자"""
        user = MagicMock()
        user.tenant_id = uuid4()
        user.user_id = uuid4()
        return user

    @pytest.mark.asyncio
    async def test_update_workflow_not_found(self, mock_db, mock_user):
        """워크플로우 업데이트 - 없음"""
        from app.routers.workflows import update_workflow, WorkflowUpdate
        from fastapi import HTTPException

        workflow_id = uuid4()
        update_data = WorkflowUpdate(name="수정된 이름")

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await update_workflow(
                workflow_id=str(workflow_id),
                update_data=update_data,
                db=mock_db,
            )

        assert exc_info.value.status_code == 404


class TestWorkflowExecuteRequestModel:
    """워크플로우 실행 요청 모델 테스트"""

    def test_execute_request_model(self):
        """ExecuteWorkflowRequest 모델"""
        from app.routers.workflows import ExecuteWorkflowRequest

        request = ExecuteWorkflowRequest(
            context={"temperature": 85},
        )

        assert request.context["temperature"] == 85

    def test_execute_request_empty_context(self):
        """ExecuteWorkflowRequest 빈 context"""
        from app.routers.workflows import ExecuteWorkflowRequest

        request = ExecuteWorkflowRequest()

        assert request.context == {}


class TestWorkflowUpdateModel:
    """워크플로우 업데이트 모델 테스트"""

    def test_workflow_update_model(self):
        """WorkflowUpdate 모델"""
        from app.routers.workflows import WorkflowUpdate

        update = WorkflowUpdate(
            name="수정된 이름",
            description="수정된 설명",
        )

        assert update.name == "수정된 이름"

    def test_workflow_update_partial(self):
        """WorkflowUpdate 부분 업데이트"""
        from app.routers.workflows import WorkflowUpdate

        update = WorkflowUpdate(name="이름만")

        assert update.name == "이름만"
        assert update.description is None


class TestAdditionalPydanticModels:
    """추가 Pydantic 모델 테스트"""

    def test_workflow_toggle_response_model(self):
        """WorkflowToggleResponse 모델"""
        from app.routers.workflows import WorkflowToggleResponse

        response = WorkflowToggleResponse(
            workflow_id=str(uuid4()),
            name="테스트 워크플로우",
            is_active=True,
            message="활성화됨",
        )

        assert response.is_active is True
        assert response.message == "활성화됨"

    def test_workflow_run_request_model(self):
        """WorkflowRunRequest 모델"""
        from app.routers.workflows import WorkflowRunRequest

        request = WorkflowRunRequest(
            input_data={"temperature": 85},
            use_simulated_data=False,
            simulation_scenario="normal",
        )

        assert request.input_data["temperature"] == 85
        assert request.use_simulated_data is False

    def test_workflow_run_request_defaults(self):
        """WorkflowRunRequest 기본값"""
        from app.routers.workflows import WorkflowRunRequest

        request = WorkflowRunRequest()

        assert request.input_data is None
        assert request.use_simulated_data is False
        assert request.simulation_scenario == "random"

    def test_sensor_simulator_request_model(self):
        """SensorSimulatorRequest 모델"""
        from app.routers.workflows import SensorSimulatorRequest

        request = SensorSimulatorRequest(
            sensors=["temp_sensor_1", "humidity_sensor_1"],
            scenario="alert",
            scenario_name="high_temperature",
        )

        assert len(request.sensors) == 2
        assert request.scenario == "alert"

    def test_sensor_simulator_request_defaults(self):
        """SensorSimulatorRequest 기본값"""
        from app.routers.workflows import SensorSimulatorRequest

        request = SensorSimulatorRequest()

        assert request.sensors is None
        assert request.scenario == "random"

    def test_condition_test_request_model(self):
        """ConditionTestRequest 모델"""
        from app.routers.workflows import ConditionTestRequest

        request = ConditionTestRequest(
            condition="temperature > 80",
            context={"temperature": 85},
        )

        assert request.condition == "temperature > 80"
        assert request.context["temperature"] == 85

    def test_resume_workflow_request_model(self):
        """ResumeWorkflowRequest 모델"""
        from app.routers.workflows import ResumeWorkflowRequest

        request = ResumeWorkflowRequest(
            checkpoint_id="checkpoint-123",
            additional_input={"override": True},
        )

        assert request.checkpoint_id == "checkpoint-123"
        assert request.additional_input["override"] is True

    def test_resume_workflow_request_defaults(self):
        """ResumeWorkflowRequest 기본값"""
        from app.routers.workflows import ResumeWorkflowRequest

        request = ResumeWorkflowRequest()

        assert request.checkpoint_id is None
        assert request.additional_input is None

    def test_action_catalog_item_model(self):
        """ActionCatalogItem 모델"""
        from app.routers.workflows import ActionCatalogItem

        item = ActionCatalogItem(
            name="send_notification",
            display_name="알림 전송",
            description="슬랙 알림을 전송합니다",
            category="notification",
            category_display_name="알림",
            parameters={"channel": "string", "message": "string"},
        )

        assert item.name == "send_notification"
        assert item.category == "notification"

    def test_category_info_model(self):
        """CategoryInfo 모델"""
        from app.routers.workflows import CategoryInfo

        info = CategoryInfo(
            name="notification",
            display_name="알림",
        )

        assert info.name == "notification"
        assert info.display_name == "알림"

    def test_action_catalog_response_model(self):
        """ActionCatalogResponse 모델"""
        from app.routers.workflows import ActionCatalogResponse, ActionCatalogItem, CategoryInfo

        item = ActionCatalogItem(
            name="send_email",
            display_name="이메일 전송",
            description="이메일을 전송합니다",
            category="notification",
            category_display_name="알림",
            parameters={},
        )
        category = CategoryInfo(name="notification", display_name="알림")

        response = ActionCatalogResponse(
            categories=[category],
            actions=[item],
            total=1,
        )

        assert len(response.actions) == 1
        assert response.total == 1


class TestWorkflowVersionModels:
    """워크플로우 버전 모델 테스트"""

    def test_workflow_version_response_model(self):
        """WorkflowVersionResponse 모델"""
        from app.routers.workflows import WorkflowVersionResponse

        response = WorkflowVersionResponse(
            version_id=str(uuid4()),
            workflow_id=str(uuid4()),
            version=1,
            dsl_definition={"name": "test", "trigger": {}, "nodes": []},
            change_log="Initial version",
            status="published",
            created_by="user-123",
            published_at=datetime.now(),
            created_at=datetime.now(),
        )

        assert response.version == 1
        assert response.change_log == "Initial version"

    def test_workflow_version_list_response_model(self):
        """WorkflowVersionListResponse 모델"""
        from app.routers.workflows import WorkflowVersionListResponse, WorkflowVersionResponse

        version = WorkflowVersionResponse(
            version_id=str(uuid4()),
            workflow_id=str(uuid4()),
            version=1,
            dsl_definition={"name": "test", "trigger": {}, "nodes": []},
            change_log="Initial version",
            status="published",
            created_by="user-123",
            published_at=datetime.now(),
            created_at=datetime.now(),
        )

        response = WorkflowVersionListResponse(
            versions=[version],
            total=1,
        )

        assert len(response.versions) == 1
        assert response.total == 1


class TestWorkflowStateModels:
    """워크플로우 상태 모델 테스트"""

    def test_workflow_state_response_model(self):
        """WorkflowStateResponse 모델"""
        from app.routers.workflows import WorkflowStateResponse

        response = WorkflowStateResponse(
            instance_id=str(uuid4()),
            state="running",
            previous_state="pending",
            updated_at="2024-01-01T00:00:00",
            reason="시작됨",
            exists=True,
        )

        assert response.state == "running"
        assert response.previous_state == "pending"

    def test_workflow_state_history_response_model(self):
        """WorkflowStateHistoryResponse 모델"""
        from app.routers.workflows import WorkflowStateHistoryResponse, WorkflowStateHistoryItem

        item = WorkflowStateHistoryItem(
            from_state="pending",
            to_state="running",
            reason="시작",
            transitioned_at="2024-01-01T00:00:00",
        )

        response = WorkflowStateHistoryResponse(
            instance_id=str(uuid4()),
            history=[item],
            total=1,
        )

        assert len(response.history) == 1
        assert response.total == 1


class TestApprovalModels:
    """승인 모델 테스트"""

    def test_approval_response_model(self):
        """ApprovalResponse 모델"""
        from app.routers.workflows import ApprovalResponse

        response = ApprovalResponse(
            approval_id=str(uuid4()),
            status="approved",
            decided_by="user-123",
            decided_at=datetime.now(),
            comment="승인 완료",
        )

        assert response.status == "approved"
        assert response.decided_by == "user-123"

    def test_approval_list_item_model(self):
        """ApprovalListItem 모델"""
        from app.routers.workflows import ApprovalListItem

        item = ApprovalListItem(
            approval_id=str(uuid4()),
            workflow_id=str(uuid4()),
            workflow_name="승인 테스트",
            node_id="approval-node-1",
            title="승인 요청",
            description="테스트 승인 요청",
            approval_type="single",
            approvers=["user-1", "user-2"],
            status="pending",
            timeout_at=datetime.now(),
            created_at=datetime.now(),
        )

        assert item.status == "pending"
        assert item.title == "승인 요청"

    def test_approval_list_response_model(self):
        """ApprovalListResponse 모델"""
        from app.routers.workflows import ApprovalListResponse, ApprovalListItem

        item = ApprovalListItem(
            approval_id=str(uuid4()),
            workflow_id=str(uuid4()),
            workflow_name="승인 테스트",
            node_id="approval-node-1",
            title="승인 요청",
            description="테스트 승인 요청",
            approval_type="single",
            approvers=["user-1"],
            status="pending",
            timeout_at=datetime.now(),
            created_at=datetime.now(),
        )

        response = ApprovalListResponse(
            approvals=[item],
            total=1,
        )

        assert len(response.approvals) == 1
        assert response.total == 1


class TestExecutionLogModel:
    """실행 로그 모델 테스트"""

    def test_execution_log_response_model(self):
        """ExecutionLogResponse 모델"""
        from app.routers.workflows import ExecutionLogResponse

        response = ExecutionLogResponse(
            logs=[
                {"timestamp": "2024-01-01T00:00:00", "level": "INFO", "message": "Started"},
                {"timestamp": "2024-01-01T00:00:01", "level": "INFO", "message": "Completed"},
            ],
            total=2,
        )

        assert len(response.logs) == 2
        assert response.total == 2


class TestCheckpointModels:
    """체크포인트 모델 테스트"""

    def test_checkpoint_info_model(self):
        """CheckpointInfo 모델"""
        from app.routers.workflows import CheckpointInfo

        info = CheckpointInfo(
            checkpoint_id="cp-1",
            node_id="node-1",
            created_at="2024-01-01T00:00:00",
            expires_at="2024-01-02T00:00:00",
        )

        assert info.checkpoint_id == "cp-1"
        assert info.node_id == "node-1"

    def test_checkpoint_list_response_model(self):
        """CheckpointListResponse 모델"""
        from app.routers.workflows import CheckpointListResponse, CheckpointInfo

        checkpoint = CheckpointInfo(
            checkpoint_id="cp-1",
            node_id="node-1",
            created_at="2024-01-01T00:00:00",
            expires_at="2024-01-02T00:00:00",
        )

        response = CheckpointListResponse(
            instance_id=str(uuid4()),
            checkpoints=[checkpoint],
            total=1,
        )

        assert len(response.checkpoints) == 1
        assert response.total == 1

    def test_recovery_info_response_model(self):
        """RecoveryInfoResponse 모델"""
        from app.routers.workflows import RecoveryInfoResponse

        response = RecoveryInfoResponse(
            instance_id=str(uuid4()),
            checkpoint_id="cp-123",
            resume_from_node="node-1",
            checkpoint_created_at="2024-01-01T00:00:00",
            can_resume=True,
        )

        assert response.can_resume is True
        assert response.checkpoint_id == "cp-123"


class TestHelperFunctions:
    """헬퍼 함수 테스트"""

    def test_workflow_to_response(self):
        """_workflow_to_response 헬퍼 함수"""
        from app.routers.workflows import _workflow_to_response

        mock_workflow = MagicMock()
        mock_workflow.workflow_id = uuid4()
        mock_workflow.tenant_id = uuid4()
        mock_workflow.name = "테스트 워크플로우"
        mock_workflow.description = "설명"
        mock_workflow.dsl_definition = {"name": "test", "trigger": {"type": "manual"}, "nodes": []}
        mock_workflow.version = "1"
        mock_workflow.is_active = True
        mock_workflow.created_at = datetime.now()
        mock_workflow.updated_at = datetime.now()

        result = _workflow_to_response(mock_workflow)

        assert result.name == "테스트 워크플로우"
        assert result.is_active is True

    def test_instance_to_response(self):
        """_instance_to_response 헬퍼 함수"""
        from app.routers.workflows import _instance_to_response
        from types import SimpleNamespace

        now = datetime.now()
        mock_instance = SimpleNamespace(
            instance_id=uuid4(),
            workflow_id=uuid4(),
            status="completed",
            input_context={"temperature": 85},
            runtime_context={"result": "success"},
            last_error=None,
            started_at=now,
            ended_at=now,
        )

        result = _instance_to_response(mock_instance, "테스트 워크플로우")

        assert result.status == "completed"
        assert result.workflow_name == "테스트 워크플로우"
