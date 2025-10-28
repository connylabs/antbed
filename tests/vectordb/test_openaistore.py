from unittest.mock import MagicMock

from antbed.db.models import Vector
from antbed.vectordb.openaistore import VectorOpenAI


def test_vector_openai_create_vector():
    mock_openai_client = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_store.id = "vs_123"
    mock_openai_client.vector_stores.create.return_value = mock_vector_store
    mock_openai_client.vector_stores.update.return_value = mock_vector_store

    vector_db = VectorOpenAI(openai=mock_openai_client)
    vector = Vector(subject_id="test_id", subject_type="test_type", vector_type="all")

    result_vector = vector_db.create_vector(vector, expires_days=7)

    assert result_vector.external_id == "vs_123"
    assert result_vector.external_provider == "openai"
    mock_openai_client.vector_stores.create.assert_called_once()
    mock_openai_client.vector_stores.update.assert_called_once()
