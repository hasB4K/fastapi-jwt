from typing import Type

from fastapi import FastAPI, Security
from fastapi.testclient import TestClient

from fastapi_jwt import JwtAccessCookie, JwtAuthorizationCredentials, JwtRefreshCookie, force_jwt_backend
from fastapi_jwt.jwt_backends import AbstractJWTBackend


def create_example_client(jwt_backend: Type[AbstractJWTBackend]):
    force_jwt_backend(jwt_backend)
    app = FastAPI()

    access_security = JwtAccessCookie(secret_key="secret_key")
    refresh_security = JwtRefreshCookie(secret_key="secret_key")

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
            },
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
                "security": [{"JwtRefreshCookie": []}],
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
                "security": [{"JwtAccessCookie": []}],
            }
        },
    },
    "components": {
        "securitySchemes": {
            "JwtAccessCookie": {
                "type": "apiKey",
                "name": "access_token_cookie",
                "in": "cookie",
            },
            "JwtRefreshCookie": {
                "type": "apiKey",
                "name": "refresh_token_cookie",
                "in": "cookie",
            },
        }
    },
}


def test_openapi_schema(jwt_backend: Type[AbstractJWTBackend]):
    client = create_example_client(jwt_backend)
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    assert response.json() == openapi_schema


def test_security_jwt_auth(jwt_backend: Type[AbstractJWTBackend]):
    client = create_example_client(jwt_backend)
    response = client.post("/auth")
    assert response.status_code == 200, response.text


def test_security_jwt_access_cookie(jwt_backend: Type[AbstractJWTBackend]):
    client = create_example_client(jwt_backend)
    access_token = client.post("/auth").json()["access_token"]

    response = client.get("/users/me", cookies={"access_token_cookie": access_token})
    assert response.status_code == 200, response.text
    assert response.json() == {"username": "username", "role": "user"}


def test_security_jwt_access_cookie_wrong(jwt_backend: Type[AbstractJWTBackend]):
    client = create_example_client(jwt_backend)
    response = client.get("/users/me", cookies={"access_token_cookie": "wrong_access_token_cookie"})
    assert response.status_code == 401, response.text


def test_security_jwt_access_cookie_no_credentials(jwt_backend: Type[AbstractJWTBackend]):
    client = create_example_client(jwt_backend)
    client.cookies.clear()
    response = client.get("/users/me", cookies={})
    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Credentials are not provided"}


def test_security_jwt_refresh_cookie(jwt_backend: Type[AbstractJWTBackend]):
    client = create_example_client(jwt_backend)
    client.cookies.clear()
    refresh_token = client.post("/auth").json()["refresh_token"]

    response = client.post("/refresh", cookies={"refresh_token_cookie": refresh_token})
    assert response.status_code == 200, response.text


def test_security_jwt_refresh_cookie_wrong(jwt_backend: Type[AbstractJWTBackend]):
    client = create_example_client(jwt_backend)
    response = client.post("/refresh", cookies={"refresh_token_cookie": "wrong_refresh_token_cookie"})
    assert response.status_code == 401, response.text


def test_security_jwt_refresh_cookie_no_credentials(jwt_backend: Type[AbstractJWTBackend]):
    client = create_example_client(jwt_backend)
    client.cookies.clear()
    response = client.post("/refresh", cookies={})
    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "Credentials are not provided"}
