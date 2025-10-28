import tiktoken
from langchain_text_splitters import (
    CharacterTextSplitter,
    NLTKTextSplitter,
    RecursiveCharacterTextSplitter,
    SpacyTextSplitter,
    TextSplitter,
)

from antbed.models import SplitDocument, SplitterConfig, SplitterType


class Splitter:
    def __init__(self, config: SplitterConfig | None = None) -> None:
        if config is None:
            config = SplitterConfig()
        self.config = config
        self.text_splitter = self.new_splitter(self.config)

    @staticmethod
    def new_splitter(config: SplitterConfig) -> TextSplitter:
        enc = tiktoken.encoding_for_model(config.model)
        split_cls = RecursiveCharacterTextSplitter
        if config.splitter_type == SplitterType.RECURSIVE:
            split_cls = RecursiveCharacterTextSplitter
        elif config.splitter_type == SplitterType.CHAR:
            split_cls = CharacterTextSplitter
        elif config.splitter_type == SplitterType.SEMANTIC:
            try:
                split_cls = NLTKTextSplitter
            except ImportError as e:
                raise ImportError("NLTK is not installed, please install it with `pip install nltk`.") from e
        elif config.splitter_type == SplitterType.SPACY:
            split_cls = SpacyTextSplitter
        else:
            raise ValueError(f"Unknown splitter type: {config.splitter_type}")

        if config.token_splitter:
            return split_cls.from_tiktoken_encoder(
                encoding_name=enc.name,
                chunk_size=config.chunk_size,
                chunk_overlap=config.overlap(),
                add_start_index=True,
            )
        return split_cls(chunk_size=config.chunk_size, chunk_overlap=config.overlap(), add_start_index=True)

    def split(self, text: str) -> list[SplitDocument]:
        docs = self.text_splitter.create_documents([text])
        res = []
        for doc in docs:
            start = doc.metadata["start_index"]
            stop = len(doc.page_content) + start
            res.append(SplitDocument(start=start, stop=stop, content=doc.page_content))
        return res
