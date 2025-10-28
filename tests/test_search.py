from unittest.mock import MagicMock

from antbed.db.models import Summary, VFile
from antbed.models import Content, SearchRecord, WithContentMode
from antbed.search import SearchManager


def test_search_manager_initialization():
    sm = SearchManager()
    assert sm.openai_client is not None


def test_hits_to_model():
    sm = SearchManager()
    vfile = VFile(
        subject_id="doc1",
        subject_type="test",
        source_filename="test.txt",
        pages=["this is page 1"],
        info={"meta_key": "meta_value"},
    )
    vfile.id = "a3f4e3c8-db3a-4c28-8797-94a5e3e2b1b3"
    vfile.summaries = [
        Summary(
            variant_name="default",
            title="Test Title",
            description="Test Description",
            tags=["tag1", "tag2"],
            summary="This is a summary.",
            language="en",
        )
    ]
    records = [vfile]

    # Mock the database call inside hits_to_model
    sm.db = MagicMock()
    sm.db.get_content.return_value = Content(
        mode=WithContentMode.SUMMARY,
        metadata=SearchRecord.from_vfile(vfile.to_pydantic()).payload,
        title="Test Title",
        description="Test Description",
        keywords=["tag1", "tag2"],
        summary="This is a summary.",
        language="en",
    )

    contents = sm.hits_to_model(records, with_content=WithContentMode.SUMMARY, summary_variant="default")

    assert len(contents) == 1
    content = contents[0]
    assert content.title == "Test Title"
    assert content.description == "Test Description"
    assert content.summary == "This is a summary."
    assert "meta_key" in content.metadata["metadata"]


def test_hits_to_markdown():
    sm = SearchManager()
    vfile = VFile(
        subject_id="doc1",
        subject_type="test",
        source_filename="test.txt",
        pages=["Full verbatim content."],
        info={"meta_key": "meta_value"},
    )
    vfile.id = "a3f4e3c8-db3a-4c28-8797-94a5e3e2b1b3"
    vfile.summaries = [
        Summary(
            variant_name="default",
            title="Test Title",
            description="Test Description",
            tags=["tag1", "tag2"],
            summary="This is a summary.",
            language="en",
        )
    ]
    records = [vfile]

    # Mock hits_to_model which is called by hits_to_markdown
    sm.hits_to_model = MagicMock(
        return_value=[
            Content(
                mode=WithContentMode.FULL,
                metadata={"id": "doc1", "type": "test", "name": "test.txt"},
                verbatim="Full verbatim content.",
                title="Test Title",
                description="Test Description",
                keywords=["tag1", "tag2"],
                language="en",
            )
        ]
    )

    markdown = sm.hits_to_markdown(records, with_content=WithContentMode.FULL)
    assert "## Metadata" in markdown
    assert "- id: doc1" in markdown
    assert "- tags: tag1,tag2" in markdown
    assert "- lang: en" in markdown
    assert "- title: Test Title" in markdown
    assert "- short: Test Description" in markdown
    assert "## Content" in markdown
    assert "Full verbatim content." in markdown
