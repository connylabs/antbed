import logging
from typing import Any

import qdrant_client as qc
from qdrant_client.models import Distance, PointStruct, VectorParams

from antbed.clients.llm import qdrant_client
from antbed.db.models import Embedding, Vector, VFile, VFileSplit
from antbed.vectordb.base import VectorDB

logger = logging.getLogger(__name__)


class VectorQdrant(VectorDB):
    def __init__(self, qdrant: qc.QdrantClient | None):
        if qdrant is None:
            qdrant = qdrant_client()
        self.client = qdrant

    @property
    def manager_name(self) -> str:
        return "qdrant"

    def create_collection(self, name: str, dim=3072) -> str:
        if not self.client.collection_exists(collection_name=name):
            res = self.client.create_collection(
                collection_name=name, vectors_config=VectorParams(size=dim, distance=Distance.DOT)
            )
            if not res:
                raise ValueError("Failed to create collection")
        return name

    def create_vector(self, vector: Vector, **kwargs):
        subject_type, subject_id, vector_type = vector.subject_type, vector.subject_id, vector.vector_type
        vname = self.vector_id(subject_id, subject_type, vector_type)
        # metadata = {"subject_id": str(subject_id), "subject_type": subject_type, "type": vector_type}
        self.create_collection(vname)
        vector.external_provider = "qdrant"
        vector.external_id = vname
        return vector

    def add_metacollection(self, vector: Vector, vsplit: VFileSplit, vfile: VFile) -> str:
        vname = self.vector_id(vector.subject_id, vector.subject_type, vector.vector_type)
        meta = f"{vname}-meta"
        self.create_collection(meta, dim=1)
        payload = self.payload(vector, vsplit, vfile, None)
        point = PointStruct(id=str(vfile.id), vector=[0.0], payload=payload)
        self.client.upsert(collection_name=meta, points=[point])
        return meta

    def payload(self, vector: Vector, vsplit: VFileSplit, vfile: VFile, emb: Embedding | None) -> dict[str, Any]:
        vname = self.vector_id(vector.subject_id, vector.subject_type, vector.vector_type)
        meta = f"{vname}-meta"
        payload = {
            "subject_id": vfile.subject_id,
            "subject_type": vfile.subject_type,
            "vector_type": vector.vector_type,
            "created_at": vfile.source_created_at,
            "source": vfile.source,
            "content_type": vfile.source_content_type,
            "filename": vfile.source_filename,
            "info": {"splitter": vsplit.info, "vfile": vfile.info},
            "vfile_id": str(vfile.id),
            "meta_collection": meta,
            "vector_id": str(vector.id),
            "vfile_split_id": str(vsplit.id),
            "metadata": vfile.info,
            "parts": vsplit.parts,
        }
        if emb is not None:
            payload["part_id"] = str(emb.id)
            payload["part"] = emb.part_number
            payload["char_start"] = emb.char_start
            payload["char_end"] = emb.char_end
        return payload

    def add_points(self, vector: Vector, vsplit: VFileSplit, vfile: VFile) -> str:
        points = []
        self.add_metacollection(vector, vsplit, vfile)
        for emb in vsplit.embeddings:
            payload = self.payload(vector, vsplit, vfile, emb)
            point = PointStruct(id=str(emb.id), vector=emb.embedding_vector, payload=payload)
            points.append(point)
        self.client.upsert(collection_name=str(vector.external_id), points=points)
        return str(vector.id)

    def reindex(self, vector: Vector, session=None) -> str:
        vector = self.create_vector(vector)
        vector.save(commit=True)
        for vf in vector.vfiles:
            split = (
                VFileSplit.where(VFileSplit.vfile_id == vf.id, session=session)
                .order_by(VFileSplit.created_at.desc())
                .scalars()
                .one()
            )
            self.add_points(vector, vsplit=split, vfile=vf)

        return str(vector.id)
