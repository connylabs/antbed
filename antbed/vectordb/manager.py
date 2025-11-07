import logging

import qdrant_client
from openai import OpenAI
from sqlalchemy.exc import IntegrityError

from antbed.db.models import Collection, Vector, VectorVFile, VFile, VFileCollection, VFileSplit
from antbed.embedding import VFileEmbedding
from antbed.models import ManagerEnum
from antbed.splitdoc import Splitter
from antbed.store import antbeddb
from antbed.vectordb.base import VectorDB
from antbed.vectordb.openaistore import VectorOpenAI
from antbed.vectordb.qdrant import VectorQdrant

logger = logging.getLogger(__name__)


class VectorManager:
    def __init__(
        self,
        splitter: Splitter | None = None,
        client: qdrant_client.QdrantClient | OpenAI | None = None,
        manager: ManagerEnum = ManagerEnum.NONE,
        embedding_provider: str | None = None,
    ) -> None:
        if splitter is None:
            self.splitter = Splitter()
        else:
            self.splitter = splitter
        self.manager_name: ManagerEnum = manager
        self.manager = self._init_manager(client, manager)
        self.embedder = VFileEmbedding(self.splitter, provider=embedding_provider)
        self.db = antbeddb()

    def _init_manager(self, client: qdrant_client.QdrantClient | OpenAI | None, manager: ManagerEnum) -> VectorDB:
        if manager == "qdrant":
            if client is not None and not isinstance(client, qdrant_client.QdrantClient):
                raise ValueError("Qdrant client is required with manager qdrant")
            return VectorQdrant(client)
        elif manager == "openai":
            if client is not None and not isinstance(client, OpenAI):
                raise ValueError("OpenAI client is required with manager openai")
            return VectorOpenAI(client)
        elif manager == "none":
            return VectorDB()
        else:
            raise ValueError("Manager should be either openai or qdrant")

    def get_or_create_vector(
        self,
        subject_id: str | None,
        subject_type: str | None = "antbed",
        vector_type: str | None = "all",
        expires_days: int | None = None,
        session=None,
    ) -> Vector:
        vector = self.db.get_vector(
            subject_id=subject_id,
            subject_type=subject_type,
            vector_type=vector_type,
            external_provider=self.manager_name,
            session=session,
        )
        if vector is None:
            vector = Vector(
                subject_id=subject_id,
                subject_type=subject_type,
                vector_type=vector_type,
                external_provider=self.manager_name,
            )
            vector = self.manager.create_vector(vector, expires_days=expires_days, session=session)
            vector = self.db.add_vector(vector, session=session)
        return vector

    def get_or_create_collection(
        self,
        collection_name: str,
        session=None,
    ) -> Collection:
        collection = self.db.get_collection(
            name=collection_name,
            session=session,
        )
        if collection is None:
            collection = Collection(collection_name=collection_name)
            collection = self.db.add_collection(collection, session=session)
        return collection

    def content(
        self, sfile: VFileSplit, part: int | None = None, start_index: int | None = None, length: int | None = None
    ) -> str:
        if part is None:
            content = sfile.vfile.content()
        elif part >= len(sfile.embeddings):
            raise ValueError(f"Part {part} not found in {sfile}")
        else:
            content = sfile.embeddings[part].content
        if start_index is not None:
            content = content[start_index:]
        if length is not None:
            content = content[:length]
        return content

    def add_vfiles_to_vector(
        self, vector: Vector, vfiles: list[VFile], reindex: bool = True, skip: bool = False, session=None
    ) -> Vector:
        # pylint: disable=logging-fstring-interpolation
        vector = self.get_or_create_vector(
            subject_id=vector.subject_id,
            subject_type=vector.subject_type,
            vector_type=vector.vector_type,
            session=session,
        )
        logger.info(f"Adding {len(vfiles)} vfiles to vector {vector.id}")
        for vfile in vfiles:
            vvfile = self.db.get_vector_vfile(vector_id=vector.id, vfile_id=vfile.id, session=session)
            reindexing = False
            if vvfile is None or reindex:
                if vvfile is not None:
                    reindexing = True
                    logger.info(f"Reindexing {vfile.id} to vector {vector.id}")
                if self.manager_name != "openai" and skip:
                    raise ValueError("Skip is only supported with openai")
                vsplit = self.embedder.embedding_vfile(vfile, skip, session=session)
                eid = self.manager.add_points(vector, vsplit, vfile)
                vvfile = VectorVFile(
                    vector_id=vector.id,
                    vfile_id=vfile.id,
                    external_id=eid,
                    external_provider=vector.external_provider,
                    vsplit_id=vsplit.id,
                )
                try:
                    self.db.add_vector_vfile(vvfile, session=session)
                except IntegrityError as e:
                    logger.error(f"Error adding vector vfile: {e}")
                    if not reindexing:
                        raise e
            logger.info(vvfile.dump_model())
        logger.info(f"Vector {vector.id} has {len(vector.vfiles)}")  # pylint: disable=logging-fstring-interpolation
        return vector

    def add_vfiles_to_collection(self, collection: Collection, vfiles: list[VFile], session=None) -> Collection:
        # pylint: disable=logging-fstring-interpolation
        collection = self.get_or_create_collection(collection_name=collection.collection_name, session=session)
        logger.info(f"Adding {len(vfiles)} vfiles to collection {collection.collection_name}({collection.id})")
        vcollection = []
        for vfile in vfiles:
            vcollection.append(VFileCollection(vfile_id=vfile.id, collection_id=collection.id))
        vcollection = self.db.add_vfile_collections(vcollection, session=session)
        return collection

    def get_or_create_embedding(self, ifile: VFile, skip: bool = True, session=None) -> VFileSplit:
        vfile = self.get_or_create_file(ifile, session=session)
        return self.embedder.embedding_vfile(vfile, skip, session=session)

    def get_or_create_split(self, ifile: VFile, skip: bool = True, session=None) -> VFileSplit:
        vfile = self.get_or_create_file(ifile, session=session)
        return self.embedder.prepare(vfile, skip=skip, session=session)

    def get_or_create_file(self, ifile: VFile, session=None) -> VFile:
        vfile = self.db.get_vfile(subject_id=ifile.subject_id, subject_type=ifile.subject_type, session=session)
        if vfile is None:
            vfile = self.db.add_vfile(ifile, session=session)
        # update metadata
        elif vfile.info is None and ifile.info is not None:
            vfile.info = ifile.info
            vfile = self.db.add_vfile(vfile, session=session)
        elif vfile.info is not None and ifile.info is not None and vfile.info != ifile.info:
            vfile.info.update(ifile.info)
            vfile = self.db.add_vfile(vfile, session=session)
        return vfile
