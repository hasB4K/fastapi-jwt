import pytest
from fastapi import FastAPI, Security
from fastapi.testclient import TestClient

from fastapi_jwt import (
    AuthlibJWTBackend,
    JwtAccessBearerCookie,
    JwtAuthorizationCredentials,
    JwtRefreshBearerCookie,
    PythonJoseJWTBackend,
    define_default_jwt_backend,
)
from fastapi_jwt.jwt_backends import AbstractJWTBackend


def create_example_client(jwt_backend: AbstractJWTBackend):
    define_default_jwt_backend(jwt_backend)
    app = FastAPI()

    access_security = JwtAccessBearerCookie(secret_key="secret_key")
    refresh_security = JwtRefreshBearerCookie(secret_key="secret_key")

    @app.post("/auth")
    def auth():
        subject = {"username": "username", "role": "user"}

        access_token = access_security.create_access_token(subject=subject)
        refresh_token = access_security.create_refresh_token(subject=subject)

        return {"access_token": access_token, "refresh_token": refresh_token}

    @app.post("/refresh")
    def refresh(credentials: JwtAuthorizationCredentials = Security(refresh_security)):
        access_token = refresh_security.create_access_token(subject=credentials.subject)
        refresh_token = refresh_security.create_refresh_token(subject=credentials.subject)

        return {"access_token": access_token, "refresh_token": refresh_token}

    @app.get("/users/me")
    def read_current_user(
        credentials: JwtAuthorizationCredentials = Security(access_security),
    ):
        return {"username": credentials["username"], "role": credentials["role"]}

    return TestClient(app)


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
                "security": [{"JwtRefreshBearer": []}, {"JwtRefreshCookie": []}],
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
                "security": [{"JwtAccessBearer": []}, {"JwtAccessCookie": []}],
            }
        },
    },
    "components": {
        "securitySchemes": {
            "JwtAccessBearer": {"type": "http", "scheme": "bearer"},
            "JwtAccessCookie": {
                "type": "apiKey",
                "name": "access_token_cookie",
                "in": "cookie",
            },
            "JwtRefreshBearer": {"type": "http", "scheme": "bearer"},
            "JwtRefreshCookie": {
                "type": "apiKey",
                "name": "refresh_token_cookie",
                "in": "cookie",
            },
        }
    },
}


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_openapi_schema(jwt_backend):
    client = create_example_client(jwt_backend)
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    assert response.json() == openapi_schema


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_security_jwt_access_both_correct(jwt_backend):
    client = create_example_client(jwt_backend)
    access_token = client.post("/auth").json()["access_token"]

    response = client.get(
        "/users/me",
        cookies={"access_token_cookie": access_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"username": "username", "role": "user"}


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_security_jwt_access_only_cookie(jwt_backend):
    client = create_example_client(jwt_backend)
    access_token = client.post("/auth").json()["access_token"]

    response = client.get("/users/me", cookies={"access_token_cookie": access_token})
    assert response.status_code == 200, response.text
    assert response.json() == {"username": "username", "role": "user"}


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_security_jwt_access_only_bearer(jwt_backend):
    client = create_example_client(jwt_backend)
    access_token = client.post("/auth").json()["access_token"]

    response = client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200, response.text
    assert response.json() == {"username": "username", "role": "user"}


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_security_jwt_access_bearer_wrong_cookie_correct(jwt_backend):
    client = create_example_client(jwt_backend)
    access_token = client.post("/auth").json()["access_token"]

    response = client.get(
        "/users/me",
        headers={"Authorization": "Bearer wrong_access_token"},
        cookies={"access_token_cookie": access_token},
    )
    assert response.status_code == 401, response.text
    assert response.json()["detail"].startswith("Wrong token:")


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_security_jwt_access_bearer_correct_cookie_wrong(jwt_backend):
    client = create_example_client(jwt_backend)
    access_token = client.post("/auth").json()["access_token"]

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies={"access_token_cookie": "wrong_access_token_cookie"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"username": "username", "role": "user"}


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_security_jwt_access_both_no_credentials(jwt_backend):
    client = create_example_client(jwt_backend)
    response = client.get("/users/me")
    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Credentials are not provided"}


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_security_jwt_refresh_only_cookie(jwt_backend):
    client = create_example_client(jwt_backend)
    refresh_token = client.post("/auth").json()["refresh_token"]

    response = client.post("/refresh", cookies={"refresh_token_cookie": refresh_token})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_security_jwt_refresh_bearer_correct_cookie_wrong(jwt_backend):
    client = create_example_client(jwt_backend)
    refresh_token = client.post("/auth").json()["refresh_token"]

    response = client.post(
        "/refresh",
        headers={"Authorization": f"Bearer {refresh_token}"},
        cookies={"refresh_token_cookie": "wrong_refresh_token_cookie"},
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_security_jwt_refresh_bearer_wrong_cookie_correct(jwt_backend):
    client = create_example_client(jwt_backend)
    refresh_token = client.post("/auth").json()["refresh_token"]

    response = client.post(
        "/refresh",
        headers={"Authorization": "Bearer wrong_refresh_token_cookie"},
        cookies={"refresh_token_cookie": refresh_token},
    )
    assert response.status_code == 401, response.text
    assert response.json()["detail"].startswith("Wrong token:")


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_security_jwt_refresh_cookie_wrong_using_access_token(jwt_backend):
    client = create_example_client(jwt_backend)
    tokens = client.post("/auth").json()
    access_token, refresh_token = tokens["access_token"], tokens["refresh_token"]
    assert access_token != refresh_token

    response = client.post("/refresh", cookies={"refresh_token_cookie": access_token})
    assert response.status_code == 401, response.text
    assert response.json()["detail"].startswith("Wrong token: 'type' is not 'refresh'")


@pytest.mark.parametrize("jwt_backend", [AuthlibJWTBackend, PythonJoseJWTBackend])
def test_security_jwt_refresh_both_no_credentials(jwt_backend):
    client = create_example_client(jwt_backend)
    response = client.post("/refresh")
    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Credentials are not provided"}
