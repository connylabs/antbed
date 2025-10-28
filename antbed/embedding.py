import logging
import uuid

from openai import OpenAI
from sqlalchemy.exc import SQLAlchemyError

from antbed.clients import openai_client
from antbed.db.models import Embedding, VFile, VFileSplit
from antbed.splitdoc import Splitter

logger = logging.getLogger(__name__)


class VFileEmbedding:
    def __init__(self, splitter: Splitter | None = None, client: OpenAI | None = None) -> None:
        if not splitter:
            splitter = Splitter()
        self.splitter = splitter
        if client:
            self.openai_client = client
        else:
            self.openai_client = openai_client()

    def get_openai_embedding(self, text, model="text-embedding-3-large") -> list[float]:
        return self.openai_client.embeddings.create(input=[text], model=model).data[0].embedding

    def embedding_vfile(self, vfile: VFile, skip: bool = False, session=None) -> VFileSplit:
        """Skip the embedding process"""
        vsplit = self.prepare(vfile, skip=skip, session=session)
        if skip:
            return vsplit
        return self.gen_vector(vsplit, session=session)

    def embedding(self, emb: Embedding, session=None):
        if emb.status in ["new", "skip", "error"]:
            emb.embedding_vector = self.get_openai_embedding(emb.content, emb.split.model)
            emb.status = "complete"
            logger.info(f"Embedding {emb.id} vect size: {len(emb.embedding_vector)} complete")  # pylint: disable=logging-fstring-interpolation
            try:
                Embedding.add(emb, commit=True, session=session)
            except SQLAlchemyError as e:
                logger.error(f"Error adding embedding: {e}")  # pylint: disable=logging-fstring-interpolation
                raise e
        return emb

    def gen_vector(self, vsplit: VFileSplit, session=None) -> VFileSplit:
        for emb in vsplit.embeddings:
            self.embedding(emb, session)
        return vsplit

    def prepare(self, vfile: VFile, skip: bool = False, session=None) -> VFileSplit:
        text = vfile.content()
        docs = self.splitter.split(text)
        embeddings = []
        vs = (
            VFileSplit.where(
                VFileSplit.vfile_id == vfile.id,
                VFileSplit.config_hash == self.splitter.config.config_hash(),
                session=session,
            )
            .scalars()
            .first()
        )
        if vs:
            return vs
        status = "new"
        if skip:
            status = "skip"
        session = VFile.new_session(session)
        with session.begin_nested():
            try:
                split = VFileSplit(
                    id=uuid.uuid4(),
                    vfile_id=vfile.id,
                    mode=self.splitter.config.splitter_type.name.lower(),
                    name=self.splitter.config.name().lower(),
                    chunk_size=self.splitter.config.chunk_size,
                    chunk_overlap=self.splitter.config.overlap(),
                    model=self.splitter.config.model.value.lower(),
                    info={"splitter": self.splitter.config.model_dump()},
                    config_hash=self.splitter.config.config_hash(),
                    parts=len(docs),
                )
                VFileSplit.add(split, commit=False, session=session)
                for i, doc in enumerate(docs):
                    uid = uuid.uuid4()
                    emb = Embedding(
                        id=uid,
                        vfile_id=vfile.id,
                        status=status,
                        char_start=doc.start,
                        char_end=doc.stop,
                        content=doc.content,
                        vfile_split_id=split.id,
                        info={},
                        part_number=i,
                        model=split.model,
                    )
                    Embedding.add(emb, commit=False, session=session)
                    embeddings.append(emb)
                # split.embeddings = embeddings

                VFile.add(vfile, commit=False, session=session)
                session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                raise e
            return split
