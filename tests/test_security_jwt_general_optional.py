from typing import Optional, Set, Type
from uuid import uuid4

from fastapi import FastAPI, Security
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from fastapi_jwt import JwtAccessBearer, JwtAuthorizationCredentials, JwtRefreshBearer, force_jwt_backend
from fastapi_jwt.jwt_backends import AbstractJWTBackend

from .mock_datetime_utils import mock_now_for_backend


def create_example_client(jwt_backend: Type[AbstractJWTBackend]):
    force_jwt_backend(jwt_backend)
    app = FastAPI()

    access_security = JwtAccessBearer(secret_key="secret_key", auto_error=False)
    refresh_security = JwtRefreshBearer.from_other(access_security)
    unique_identifiers_database: Set[str] = set()

    @app.post("/auth")
    def auth():
        subject = {"username": "username", "role": "user"}
        unique_identifier = str(uuid4())
        unique_identifiers_database.add(unique_identifier)

        access_token = access_security.create_access_token(subject=subject, unique_identifier=unique_identifier)
        refresh_token = access_security.create_refresh_token(subject=subject)

        return {"access_token": access_token, "refresh_token": refresh_token}

    @app.post("/refresh")
    def refresh(
        credentials: Optional[JwtAuthorizationCredentials] = Security(refresh_security),
    ):
        if credentials is None:
            return {"msg": "Create an account first"}

        unique_identifier = str(uuid4())
        unique_identifiers_database.add(unique_identifier)

        access_token = refresh_security.create_access_token(
            subject=credentials.subject,
            unique_identifier=unique_identifier,
        )
        refresh_token = refresh_security.create_refresh_token(subject=credentials.subject)

        return {"access_token": access_token, "refresh_token": refresh_token}

    @app.get("/users/me")
    def read_current_user(
        credentials: Optional[JwtAuthorizationCredentials] = Security(access_security),
    ):
        if credentials is None:
            return {"msg": "Create an account first"}
        return {"username": credentials["username"], "role": credentials["role"]}

    @app.get("/auth/meta")
    def get_token_meta(
        credentials: JwtAuthorizationCredentials = Security(access_security),
    ):
        if credentials is None:
            return {"msg": "Create an account first"}
        return {"jti": credentials.jti}

    return TestClient(app), unique_identifiers_database


openapi_schema = {
    "openapi": "3.1.0",
    "info": {"title": "FastAPI", "version": "0.1.0"},
    "paths": {
        "/auth": {
            "post": {
                "responses": {
                    "200": {
                        "description": "Successful Response",
                        "content": {"application/json": {"schema": {}}},
                    }
                },
                "summary": "Auth",
                "operationId": "auth_auth_post",
            }
        },
        "/refresh": {
            "post": {
                "responses": {
                    "200": {
                        "description": "Successful Response",
                        "content": {"application/json": {"schema": {}}},
                    }
                },
                "summary": "Refresh",
                "operationId": "refresh_refresh_post",
                "security": [{"JwtRefreshBearer": []}],
            }
        },
        "/users/me": {
            "get": {
                "responses": {
                    "200": {
                        "description": "Successful Response",
                        "content": {"application/json": {"schema": {}}},
                    }
                },
                "summary": "Read Current User",
                "operationId": "read_current_user_users_me_get",
                "security": [{"JwtAccessBearer": []}],
            }
        },
        "/auth/meta": {
            "get": {
                "responses": {
                    "200": {
                        "description": "Successful Response",
                        "content": {"application/json": {"schema": {}}},
                    }
                },
                "summary": "Get Token Meta",
                "operationId": "get_token_meta_auth_meta_get",
                "security": [{"JwtAccessBearer": []}],
            }
        },
    },
    "components": {
        "securitySchemes": {
            "JwtAccessBearer": {"type": "http", "scheme": "bearer"},
            "JwtRefreshBearer": {"type": "http", "scheme": "bearer"},
        }
    },
}


def test_openapi_schema(jwt_backend: Type[AbstractJWTBackend]):
    client, _ = create_example_client(jwt_backend)
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    assert response.json() == openapi_schema


def test_security_jwt_access_token(jwt_backend: Type[AbstractJWTBackend]):
    client, _ = create_example_client(jwt_backend)
    access_token = client.post("/auth").json()["access_token"]

    response = client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200, response.text
    assert response.json() == {"username": "username", "role": "user"}


def test_security_jwt_access_token_wrong(jwt_backend: Type[AbstractJWTBackend]):
    client, _ = create_example_client(jwt_backend)
    response = client.get("/users/me", headers={"Authorization": "Bearer wrong_access_token"})
    assert response.status_code == 200, response.text
    assert response.json() == {"msg": "Create an account first"}

    response = client.get("/users/me", headers={"Authorization": "Bearer wrong.access.token"})
    assert response.status_code == 200, response.text
    assert response.json() == {"msg": "Create an account first"}


def test_security_jwt_access_token_changed(jwt_backend: Type[AbstractJWTBackend]):
    client, _ = create_example_client(jwt_backend)
    access_token = client.post("/auth").json()["access_token"]

    access_token = access_token.split(".")[0] + ".wrong." + access_token.split(".")[-1]

    response = client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200, response.text
    assert response.json() == {"msg": "Create an account first"}


def test_security_jwt_access_token_expiration(mocker: MockerFixture, jwt_backend):
    client, _ = create_example_client(jwt_backend)
    access_token = client.post("/auth").json()["access_token"]

    mock_now_for_backend(mocker, jwt_backend, minutes=3)  # 3 min left
    response = client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200, response.text
    assert response.json() == {"username": "username", "role": "user"}

    mock_now_for_backend(mocker, jwt_backend, days=42)  # 42 days left
    response = client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200, response.text
    assert response.json() == {"msg": "Create an account first"}


def test_security_jwt_refresh_token(jwt_backend: Type[AbstractJWTBackend]):
    client, _ = create_example_client(jwt_backend)
    refresh_token = client.post("/auth").json()["refresh_token"]

    response = client.post("/refresh", headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 200, response.text
    assert "msg" not in response.json()


def test_security_jwt_refresh_token_wrong(jwt_backend: Type[AbstractJWTBackend]):
    client, _ = create_example_client(jwt_backend)
    response = client.post("/refresh", headers={"Authorization": "Bearer wrong_refresh_token"})
    assert response.status_code == 200, response.text
    assert response.json() == {"msg": "Create an account first"}

    response = client.post("/refresh", headers={"Authorization": "Bearer wrong.refresh.token"})
    assert response.status_code == 200, response.text
    assert response.json() == {"msg": "Create an account first"}


def test_security_jwt_refresh_token_using_access_token(jwt_backend: Type[AbstractJWTBackend]):
    client, _ = create_example_client(jwt_backend)
    tokens = client.post("/auth").json()
    access_token, refresh_token = tokens["access_token"], tokens["refresh_token"]
    assert access_token != refresh_token

    response = client.post("/refresh", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200, response.text
    assert response.json() == {"msg": "Create an account first"}


def test_security_jwt_refresh_token_changed(jwt_backend: Type[AbstractJWTBackend]):
    client, _ = create_example_client(jwt_backend)
    refresh_token = client.post("/auth").json()["refresh_token"]

    refresh_token = refresh_token.split(".")[0] + ".wrong." + refresh_token.split(".")[-1]

    response = client.post("/refresh", headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 200, response.text
    assert response.json() == {"msg": "Create an account first"}


def test_security_jwt_refresh_token_expired(mocker: MockerFixture, jwt_backend):
    client, _ = create_example_client(jwt_backend)
    refresh_token = client.post("/auth").json()["refresh_token"]

    mock_now_for_backend(mocker, jwt_backend, days=42)  # 42 days left
    response = client.post("/refresh", headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 200, response.text
    assert response.json() == {"msg": "Create an account first"}


def test_security_jwt_custom_jti(jwt_backend: Type[AbstractJWTBackend]):
    client, unique_identifiers_database = create_example_client(jwt_backend)
    access_token = client.post("/auth").json()["access_token"]

    response = client.get("/auth/meta", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200, response.text
    assert response.json()["jti"] in unique_identifiers_database
