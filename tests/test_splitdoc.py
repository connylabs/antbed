import contextlib

from antbed.models import SplitterConfig, SplitterType
from antbed.splitdoc import Splitter


def test_splitter_default_config():
    splitter = Splitter()
    assert splitter.config.chunk_size == 800
    assert splitter.config.splitter_type == SplitterType.RECURSIVE
    assert splitter.config.token_splitter is False


def test_splitter_custom_config():
    config = SplitterConfig(chunk_size=100, splitter_type=SplitterType.CHAR, token_splitter=True)
    splitter = Splitter(config)
    assert splitter.config.chunk_size == 100
    assert splitter.config.splitter_type == SplitterType.CHAR
    assert splitter.config.token_splitter is True


def test_split_text():
    text = "This is a test sentence. This is another test sentence, which is a bit longer."
    config = SplitterConfig(chunk_size=35, chunk_overlap_perc=0, splitter_type=SplitterType.RECURSIVE)
    splitter = Splitter(config)
    docs = splitter.split(text)
    assert len(docs) == 3
    assert docs[0].content == "This is a test sentence. This is"
    assert docs[0].start == 0
    assert docs[0].stop == 32
    assert docs[1].content == "another test sentence, which is a"
    assert docs[1].start == 33
    assert docs[1].stop == 66
    assert docs[2].content == "bit longer."
    assert docs[2].start == 67
    assert docs[2].stop == 78


def test_split_text_overlap():
    text = "This is a test sentence for overlap functionality. It has multiple parts."
    config = SplitterConfig(chunk_size=30, chunk_overlap_perc=50, splitter_type=SplitterType.RECURSIVE)  # 15 overlap
    splitter = Splitter(config)
    docs = splitter.split(text)
    assert len(docs) == 4
    assert docs[0].content == "This is a test sentence for"
    assert docs[1].content == "sentence for overlap"
    assert docs[2].content == "for overlap functionality. It"
    assert docs[3].content == "It has multiple parts."


def test_splitter_types():
    config_char = SplitterConfig(splitter_type=SplitterType.CHAR)
    assert Splitter.new_splitter(config_char)
    config_semantic = SplitterConfig(splitter_type=SplitterType.SEMANTIC)
    with contextlib.suppress(ImportError):  # nltk not installed in test env, which is fine
        assert Splitter.new_splitter(config_semantic)
    config_spacy = SplitterConfig(splitter_type=SplitterType.SPACY)
    # Spacy might need model download, just check if it instantiates
    with contextlib.suppress(ImportError):  # spacy not installed in test env, which is fine
        assert Splitter.new_splitter(config_spacy)
