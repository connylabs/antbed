# pylint: disable=import-outside-toplevel
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict
from temporalio import activity

if TYPE_CHECKING:
    pass

# from antbed.agents.rag_summary import SummaryAgent, SummaryInput
from antbed.db.models import Collection, Embedding, Vector, VFile
from antbed.embedding import VFileEmbedding
from antbed.models import EmbeddingRequest, UploadRequest, UploadRequestIDs
from antbed.splitdoc import Splitter
from antbed.store import antbeddb
from antbed.vectordb.manager import VectorManager

logger = logging.getLogger(__name__)


class AnyData(BaseModel):
    model_config = ConfigDict(extra="allow")


@activity.defn
def echo(data: AnyData) -> AnyData:
    activity.heartbeat()
    time.sleep(0.5)
    activity.logger.info("Echoing: %s", data.model_dump_json(indent=2))
    return data


@activity.defn
async def aecho(data: dict[str, Any]) -> dict[str, Any]:
    activity.heartbeat()
    activity.logger.info("Echoing: %s", data)
    return data


@activity.defn
def get_vfile_id(subject_id: str | None = None, subject_type: str | None = None) -> UploadRequestIDs:
    activity.heartbeat()
    activity.logger.info("Getting VFile")
    antbeddb().check()
    with antbeddb().new_session() as session:
        vf = antbeddb().get_vfile(subject_id=subject_id, subject_type=subject_type, session=session)
        if vf is None:
            raise ValueError("VFile not found")
        return UploadRequestIDs(vfile_id=vf.id)


@activity.defn
def get_or_create_file(data: UploadRequest) -> UploadRequestIDs:
    activity.heartbeat()
    activity.logger.info("Creating file")
    antbeddb().check()
    splitter = Splitter(data.config)
    vm = VectorManager(splitter, manager=data.manager)
    with antbeddb().new_session() as session:
        vf = vm.get_or_create_file(data.doc.to_model(VFile), session=session)
        urir = UploadRequestIDs(
            config=data.config,
            manager=data.manager,
            vector=data.vector,
            vector_id=data.vector_id,
            skip_embedding=data.skip_embedding,
            collection_name=data.collection_name,
            collection_id=data.collection_id,
            vfile_id=vf.id,
        )
        activity.heartbeat()
        return urir


@activity.defn
def get_or_create_split(data: UploadRequestIDs) -> UploadRequestIDs:
    activity.heartbeat()
    activity.logger.info("Creating split and embedding(%s): %s", data.skip_embedding, data.vfile_id)
    antbeddb().check()
    splitter = Splitter(data.config)
    vm = VectorManager(splitter, manager=data.manager)
    if data.vfile_id is None:
        raise ValueError("VFile ID is required")
    with antbeddb().new_session() as session:
        vf = VFile.find(data.vfile_id, session=session)
        if vf is None:
            raise ValueError("VFile not found")
        split = vm.get_or_create_split(vf, skip=data.skip_embedding, session=session)
        urir = UploadRequestIDs(
            config=data.config,
            manager=data.manager,
            vector=data.vector,
            vector_id=data.vector_id,
            skip_embedding=data.skip_embedding,
            collection_id=data.collection_id,
            collection_name=data.collection_name,
            vfile_split_id=split.id,
            vfile_id=vf.id,
            embedding_ids=[x.id for x in split.embeddings],
        )
    activity.heartbeat()
    return urir


@activity.defn
def embedding(data: EmbeddingRequest) -> EmbeddingRequest:
    activity.heartbeat()
    activity.logger.info("Embedding")
    antbeddb().check()
    with antbeddb().new_session() as session:
        embedder = VFileEmbedding()
        emb = Embedding.find(data.embedding_id, session=session)
        if emb is None:
            raise ValueError("Embedding not found")
        emb = embedder.embedding(emb, session=session)
        activity.heartbeat()
        return EmbeddingRequest(embedding_id=emb.id, status=emb.status)


@activity.defn
def vfile_has_summaries(vfile_id: uuid.UUID) -> bool:
    """Check if a VFile has all expected summary variants."""
    activity.heartbeat()
    db = antbeddb()
    # TODO: Expected variants should ideally come from configuration
    expected_variants = {"machine", "pretty"}
    with db.new_session() as session:
        existing_variants = set(db.get_summary_variants(vfile_id, session=session))
        return expected_variants.issubset(existing_variants)


@activity.defn
def add_vfile_to_collection(data: UploadRequestIDs) -> UploadRequestIDs:
    activity.heartbeat()
    activity.logger.info("Adding vfile to collection")
    antbeddb().check()
    splitter = Splitter(data.config)
    with antbeddb().new_session() as session:
        vm = VectorManager(splitter, manager=data.manager)
        if data.vfile_id is None:
            raise ValueError("VFile ID is required")
        vf = VFile.find(data.vfile_id, session=session)
        if vf is None:
            raise ValueError("VFile not found")
        if data.collection_name is None and data.collection_id is None:
            raise ValueError("Collection ID is required or Collection Name required")
        collection = None
        if data.collection_id is not None:
            collection = Collection.find(data.collection_id, session=session)
        elif data.collection_name is not None:
            collection = Collection(collection_name=data.collection_name)
        if collection is None:
            raise ValueError("Vector/Collection not found")
        activity.logger.info(f"Adding {vf.id} to collection {collection.id}")
        collection = vm.add_vfiles_to_collection(collection, [vf], session=session)
        data.collection_id = collection.id
        data.collection_name = collection.collection_name
        activity.heartbeat()
        return data


@activity.defn
def add_vfile_to_vector(data: UploadRequestIDs) -> UploadRequestIDs:
    activity.heartbeat()
    activity.logger.info("Adding vfile to vector")
    antbeddb().check()
    splitter = Splitter(data.config)
    with antbeddb().new_session() as session:
        vm = VectorManager(splitter, manager=data.manager)
        if data.vfile_id is None:
            raise ValueError("VFile ID is required")
        vf = VFile.find(data.vfile_id, session=session)
        if vf is None:
            raise ValueError("VFile not found")
        if data.vector is None and data.vector_id is None:
            raise ValueError("Vector ID is required or Vector required")
        vector = None
        if data.vector_id is not None:
            vector = Vector.find(data.vector_id, session=session)
        elif data.vector is not None:
            vector = data.vector.to_model(Vector)
        if vector is None:
            raise ValueError("Vector/Vector not found")
        vector = vm.add_vfiles_to_vector(vector, [vf], session=session)
        data.vector_id = vector.id
        data.vector = vector.to_pydantic()
        activity.heartbeat()
        return data


@activity.defn
def save_summaries_to_db(data: UploadRequestIDs, summary_result: dict[str, Any]) -> UploadRequestIDs:
    """Activity to save summary results to the database (pure I/O operation)."""

    activity.heartbeat()
    activity.logger.info("Saving summaries to database")
    db = antbeddb()

    with db.new_session() as session:
        if data.vfile_id is None:
            raise ValueError("VFile ID is required")
        vf = db.find_vfile(data.vfile_id, session=session)

        # Get existing summary variants
        existing_variants = {s.variant_name for s in vf.summaries}
        activity.logger.info(f"Existing summary variants: {existing_variants}")

        # Parse the summary result
        summaries_dict = summary_result.get("summaries", {})

        summaries = []
        for variant_str, summary_data in summaries_dict.items():
            variant = variant_str  # Already a string like "machine" or "pretty"
            if variant in existing_variants:
                activity.logger.info(f"Summary variant '{variant}' already exists, skipping")
                continue

            if summary_data is not None:
                # Extract the actual summary from the InternalSummaryResult structure
                actual_summary = summary_data.get("summary", {})
                if actual_summary:
                    summary_output_dict = {
                        "short_version": actual_summary.get("short_version", ""),
                        "description": actual_summary.get("description", ""),
                        "title": actual_summary.get("title", ""),
                        "tags": actual_summary.get("tags", []),
                        "language": actual_summary.get("language", ""),
                    }

                    # Create a simple object with the required attributes
                    class SummaryOutput:
                        def __init__(self, **kwargs):
                            for key, value in kwargs.items():
                                setattr(self, key, value)

                    summary_output = SummaryOutput(**summary_output_dict)
                    summary = db.add_summary_output(vf.id, output=summary_output, variant_name=variant, session=session)
                    activity.logger.info(
                        f"Saved summary variant '{variant}': {vf.tokens} -> {summary.tokens} tokens for VFile {vf.id}"
                    )
                    summaries.append(summary)

        # Include both new and existing summary IDs
        data.summary_ids.extend([s.id for s in summaries])
        data.summary_ids.extend([s.id for s in vf.summaries if s.id not in data.summary_ids])

        activity.heartbeat()
        return data
