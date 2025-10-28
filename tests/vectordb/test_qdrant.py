from unittest.mock import MagicMock

from antbed.db.models import Vector
from antbed.vectordb.qdrant import VectorQdrant


def test_vector_qdrant_create_vector():
    mock_qdrant_client = MagicMock()
    mock_qdrant_client.collection_exists.return_value = False
    mock_qdrant_client.create_collection.return_value = True

    vector_db = VectorQdrant(qdrant=mock_qdrant_client)
    vector = Vector(subject_id="test_id", subject_type="test_type", vector_type="all")

    result_vector = vector_db.create_vector(vector)

    expected_vname = "v-test_type_test_id_all"
    assert result_vector.external_id == expected_vname
    assert result_vector.external_provider == "qdrant"
    mock_qdrant_client.collection_exists.assert_called_with(collection_name=expected_vname)
    mock_qdrant_client.create_collection.assert_called_once()
