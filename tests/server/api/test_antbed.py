from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from antbed.server.server import serve


@pytest.fixture
def client():
    app = serve()
    return TestClient(app)


@patch("antbed.server.api.antbed.start_upload_workflow")
@patch("antbed.server.api.antbed.start_embedding_workflow")
@patch("antbed.server.api.antbed.wait_for_result")
def test_upload_endpoint(mock_wait_for_result, mock_start_embedding_workflow, mock_start_upload_workflow, client):
    # Mock workflow handles
    mock_upload_handler = AsyncMock()
    mock_embedding_handler = AsyncMock()
    mock_start_upload_workflow.return_value = mock_upload_handler
    mock_start_embedding_workflow.return_value = mock_embedding_handler

    # Mock job results
    mock_wait_for_result.side_effect = [
        MagicMock(uuid="upload-job-id", name="upload_workflow", status="RUNNING", result={}),
        MagicMock(uuid="embedding-job-id", name="embedding_workflow", status="RUNNING", result={}),
    ]

    upload_data = {
        "doc": {"subject_id": "doc123", "subject_type": "test", "pages": ["page 1 content"]},
        "collection_name": "test_collection",
        "summarize": True,
        "manager": "qdrant",
    }

    response = client.post("/api/v1/embedding/upload", json=upload_data)

    assert response.status_code == 200
    json_response = response.json()
    assert len(json_response["payload"]["jobs"]) == 2
    assert json_response["payload"]["jobs"][0]["uuid"] == "upload-job-id"
    assert json_response["payload"]["jobs"][1]["uuid"] == "embedding-job-id"

    mock_start_upload_workflow.assert_called_once()
    mock_start_embedding_workflow.assert_called_once()
    assert mock_wait_for_result.call_count == 2
