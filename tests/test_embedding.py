from unittest.mock import MagicMock, patch

from antbed.db.models import Embedding, VFile, VFileSplit
from antbed.embedding import VFileEmbedding


@patch("antbed.embedding.embedding_client")
def test_vfile_embedding_embedding(mock_embedding_client_factory):
    mock_embedding_client = MagicMock()
    mock_embedding_client.embed.return_value = [[0.1, 0.2, 0.3]]
    mock_embedding_client_factory.return_value = mock_embedding_client

    vsplit = VFileSplit(model="text-embedding-3-large")
    emb = Embedding(
        id="emb1",
        content="some text",
        status="new",
    )
    emb.split = vsplit

    embedder = VFileEmbedding()

    # Mock the database add method
    with patch("antbed.db.models.Embedding.add") as mock_add:
        result_emb = embedder.embedding(emb)

        assert result_emb.status == "complete"
        assert result_emb.embedding_vector == [0.1, 0.2, 0.3]
        mock_embedding_client.embed.assert_called_once_with(["some text"], "text-embedding-3-large")
        mock_add.assert_called_once()


@patch("antbed.embedding.VFileEmbedding.prepare")
@patch("antbed.embedding.VFileEmbedding.gen_vector")
def test_embedding_vfile(mock_gen_vector, mock_prepare):
    mock_vsplit = VFileSplit()
    mock_prepare.return_value = mock_vsplit
    mock_gen_vector.return_value = mock_vsplit

    embedder = VFileEmbedding()
    vfile = VFile()

    # Test without skipping
    result = embedder.embedding_vfile(vfile, skip=False)
    mock_prepare.assert_called_with(vfile, skip=False, session=None)
    mock_gen_vector.assert_called_with(mock_vsplit, session=None)
    assert result == mock_vsplit

    # Test with skipping
    mock_gen_vector.reset_mock()
    result_skipped = embedder.embedding_vfile(vfile, skip=True)
    mock_prepare.assert_called_with(vfile, skip=True, session=None)
    mock_gen_vector.assert_not_called()
    assert result_skipped == mock_vsplit
