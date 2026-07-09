from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class TestMainRoutes:
    def test_chat_preflight_request_is_accepted(self):
        with patch("app.main.create_pinecone_client", return_value=None), patch(
            "app.main.load_runtime_vector_store", return_value=None
        ):
            with TestClient(app) as client:
                response = client.options(
                    "/api/chat",
                    headers={
                        "Origin": "http://localhost:5173",
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
