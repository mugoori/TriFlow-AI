# -*- coding: utf-8 -*-
"""
Users Router Tests
사용자 관리 API 테스트
"""
import pytest
from httpx import AsyncClient


class TestUsersRouter:
    """Users API 테스트"""

    @pytest.mark.asyncio
    async def test_list_users_as_admin(self, admin_client: AsyncClient):
        """admin은 사용자 목록을 조회할 수 있어야 함"""
        response = await admin_client.get("/api/v1/users/")

        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert isinstance(data["users"], list)
        assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_list_users_as_regular_user(self, authenticated_client: AsyncClient):
        """일반 사용자는 사용자 목록 조회 불가 (403 또는 401)"""
        response = await authenticated_client.get("/api/v1/users/")

        # 권한 없음 (Forbidden) 또는 인증 실패
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_list_users_unauthenticated(self, client: AsyncClient):
        """미인증 사용자는 사용자 목록 조회 불가 (401)"""
        response = await client.get("/api/v1/users/")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_users_with_search(self, admin_client: AsyncClient):
        """검색 필터 테스트"""
        response = await admin_client.get("/api/v1/users/?search=admin")

        assert response.status_code == 200
        data = response.json()
        assert "users" in data

    @pytest.mark.asyncio
    async def test_list_users_with_role_filter(self, admin_client: AsyncClient):
        """역할 필터 테스트"""
        response = await admin_client.get("/api/v1/users/?role_filter=admin")

        assert response.status_code == 200
        data = response.json()
        assert "users" in data

    @pytest.mark.asyncio
    async def test_list_users_pagination(self, admin_client: AsyncClient):
        """페이지네이션 테스트"""
        response = await admin_client.get("/api/v1/users/?skip=0&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert len(data["users"]) <= 10


class TestRolesAPI:
    """역할 관련 API 테스트"""

    @pytest.mark.asyncio
    async def test_list_roles(self, authenticated_client: AsyncClient):
        """모든 인증된 사용자는 역할 목록을 조회할 수 있어야 함"""
        response = await authenticated_client.get("/api/v1/users/roles")

        assert response.status_code == 200
        data = response.json()
        assert "roles" in data
        roles = data["roles"]
        assert len(roles) == 5  # 5-Tier RBAC

        # 역할 정보 확인
        role_names = [r["role"] for r in roles]
        assert "admin" in role_names
        assert "approver" in role_names
        assert "operator" in role_names
        assert "user" in role_names
        assert "viewer" in role_names

    @pytest.mark.asyncio
    async def test_get_role_permissions_admin(self, authenticated_client: AsyncClient):
        """admin 역할 권한 조회"""
        response = await authenticated_client.get("/api/v1/users/roles/admin/permissions")

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        assert data["level"] == 5
        assert "permissions" in data
        assert len(data["permissions"]) > 0

    @pytest.mark.asyncio
    async def test_get_role_permissions_viewer(self, authenticated_client: AsyncClient):
        """viewer 역할 권한 조회"""
        response = await authenticated_client.get("/api/v1/users/roles/viewer/permissions")

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "viewer"
        assert data["level"] == 1

    @pytest.mark.asyncio
    async def test_get_role_permissions_invalid_role(self, authenticated_client: AsyncClient):
        """잘못된 역할 조회 시 400 에러"""
        response = await authenticated_client.get("/api/v1/users/roles/invalid_role/permissions")

        assert response.status_code == 400


class TestUserRoleUpdate:
    """사용자 역할 변경 API 테스트"""

    @pytest.mark.asyncio
    async def test_update_role_as_admin(self, admin_client: AsyncClient):
        """admin은 다른 사용자의 역할을 변경할 수 있어야 함"""
        # 먼저 사용자 목록 조회
        list_response = await admin_client.get("/api/v1/users/")
        assert list_response.status_code == 200

        users = list_response.json()["users"]
        # admin이 아닌 사용자 찾기
        target_user = None
        for user in users:
            if user["role"] != "admin":
                target_user = user
                break

        if not target_user:
            pytest.skip("테스트할 non-admin 사용자가 없음")

        # 역할 변경
        response = await admin_client.patch(
            f"/api/v1/users/{target_user['user_id']}/role",
            json={"role": "operator"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Role updated successfully"
        assert data["new_role"] == "operator"

    @pytest.mark.asyncio
    async def test_update_own_role_forbidden(self, admin_client: AsyncClient):
        """admin도 자기 자신의 역할은 변경 불가"""
        # 현재 사용자 정보 조회
        me_response = await admin_client.get("/api/v1/auth/me")
        assert me_response.status_code == 200
        my_user_id = me_response.json()["user_id"]

        # 자기 역할 변경 시도
        response = await admin_client.patch(
            f"/api/v1/users/{my_user_id}/role",
            json={"role": "viewer"}
        )

        assert response.status_code == 400
        assert "Cannot change your own role" in response.json().get("detail", "")

    @pytest.mark.asyncio
    async def test_update_role_invalid_role(self, admin_client: AsyncClient):
        """잘못된 역할로 변경 시도 시 422 에러"""
        list_response = await admin_client.get("/api/v1/users/")
        users = list_response.json()["users"]

        if len(users) == 0:
            pytest.skip("테스트할 사용자가 없음")

        target_user = users[0]

        response = await admin_client.patch(
            f"/api/v1/users/{target_user['user_id']}/role",
            json={"role": "invalid_role"}
        )

        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_update_role_as_regular_user(self, authenticated_client: AsyncClient):
        """일반 사용자는 역할 변경 불가"""
        # 임의의 UUID
        response = await authenticated_client.patch(
            "/api/v1/users/00000000-0000-0000-0000-000000000001/role",
            json={"role": "admin"}
        )

        assert response.status_code in [401, 403]


class TestDataScopeAPI:
    """Data Scope 관련 API 테스트"""

    @pytest.mark.asyncio
    async def test_get_data_scope_as_admin(self, admin_client: AsyncClient):
        """admin은 사용자의 Data Scope를 조회할 수 있어야 함"""
        # 사용자 목록 조회
        list_response = await admin_client.get("/api/v1/users/")
        users = list_response.json()["users"]

        if len(users) == 0:
            pytest.skip("테스트할 사용자가 없음")

        target_user = users[0]

        response = await admin_client.get(
            f"/api/v1/users/{target_user['user_id']}/data-scope"
        )

        assert response.status_code == 200
        data = response.json()
        assert "factory_codes" in data
        assert "line_codes" in data
        assert "all_access" in data

    @pytest.mark.asyncio
    async def test_update_data_scope_as_admin(self, admin_client: AsyncClient):
        """admin은 사용자의 Data Scope를 설정할 수 있어야 함"""
        # 사용자 목록 조회
        list_response = await admin_client.get("/api/v1/users/")
        users = list_response.json()["users"]

        if len(users) == 0:
            pytest.skip("테스트할 사용자가 없음")

        target_user = users[0]

        # Data Scope 설정
        response = await admin_client.patch(
            f"/api/v1/users/{target_user['user_id']}/data-scope",
            json={
                "factory_codes": ["F001", "F002"],
                "line_codes": ["L001", "L002"],
                "all_access": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Data scope updated successfully"
        assert data["data_scope"]["factory_codes"] == ["F001", "F002"]
        assert data["data_scope"]["line_codes"] == ["L001", "L002"]

    @pytest.mark.asyncio
    async def test_update_data_scope_all_access(self, admin_client: AsyncClient):
        """all_access 설정 테스트"""
        list_response = await admin_client.get("/api/v1/users/")
        users = list_response.json()["users"]

        if len(users) == 0:
            pytest.skip("테스트할 사용자가 없음")

        target_user = users[0]

        response = await admin_client.patch(
            f"/api/v1/users/{target_user['user_id']}/data-scope",
            json={
                "factory_codes": [],
                "line_codes": [],
                "all_access": True
            }
        )

        assert response.status_code == 200
        assert response.json()["data_scope"]["all_access"] is True

    @pytest.mark.asyncio
    async def test_update_data_scope_as_regular_user(self, authenticated_client: AsyncClient):
        """일반 사용자는 Data Scope 설정 불가"""
        response = await authenticated_client.patch(
            "/api/v1/users/00000000-0000-0000-0000-000000000001/data-scope",
            json={
                "factory_codes": ["F001"],
                "line_codes": ["L001"],
                "all_access": False
            }
        )

        assert response.status_code in [401, 403]


class TestFactoryLinesAPI:
    """공장/라인 코드 API 테스트"""

    @pytest.mark.asyncio
    async def test_get_factory_lines_as_admin(self, admin_client: AsyncClient):
        """admin은 공장/라인 코드 목록을 조회할 수 있어야 함"""
        response = await admin_client.get("/api/v1/users/factory-lines")

        assert response.status_code == 200
        data = response.json()
        assert "factory_codes" in data
        assert "line_codes" in data
        assert isinstance(data["factory_codes"], list)
        assert isinstance(data["line_codes"], list)

    @pytest.mark.asyncio
    async def test_get_factory_lines_as_regular_user(self, authenticated_client: AsyncClient):
        """일반 사용자는 공장/라인 코드 조회 불가"""
        response = await authenticated_client.get("/api/v1/users/factory-lines")

        assert response.status_code in [401, 403]
