# pylint: disable=import-outside-toplevel
import asyncio
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict
from temporalio import activity
from temporalio.common import WorkflowIDReusePolicy

if TYPE_CHECKING:
    from antgent.agents.summarizer.models import SummaryInput

# from antbed.agents.rag_summary import SummaryAgent, SummaryInput
from antbed.db.models import Collection, Embedding, Summary, Vector, VFile
from antbed.embedding import VFileEmbedding
from antbed.models import EmbeddingRequest, UploadRequest, UploadRequestIDs
from antbed.splitdoc import Splitter
from antbed.store import antbeddb
from antbed.temporal.client import tclient
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


def add_summary_output(vf: VFile, output: "SummaryInput", variant: str, session: Any = None) -> Summary:
    from antgent.agents.summarizer.models import SummaryInput

    db = antbeddb()
    summary = db.add_summary_output(vf.id, output=output, variant_name=variant, session=session)

    activity.logger.info(
        f"Summarized ( {summary.variant_name}) from {vf.tokens} to {summary.tokens} tokens for VFile {vf.id}"
    )
    return summary


@activity.defn
def summarize(data: UploadRequestIDs) -> UploadRequestIDs:
    # Import antgent modules inside activity to avoid Temporal sandbox restrictions
    from antgent.agents.summarizer.models import SummaryInput
    from antgent.models.agent import AgentInput
    from antgent.workflows.base import WorkflowInput
    from antgent.workflows.summarizer import TextSummarizerAllWorkflow

    activity.heartbeat()
    activity.logger.info("Summarize multi (pretty/machine)")
    db = antbeddb()
    with db.new_session() as session:
        if data.vfile_id is None:
            raise ValueError("VFile ID is required")
        vf = db.find_vfile(data.vfile_id, session=session)

        existing_variant = {s.variant_name for s in vf.summaries}
        variants_to_generate = {"machine", "pretty"} - existing_variant
        if not variants_to_generate:
            activity.logger.info("All summaries already exist for VFile %s", vf.id)
            data.summary_ids = [s.id for s in vf.summaries]
            return data

        activity.heartbeat()
        context = SummaryInput(content=vf.content(summary=False))
        agent_input = AgentInput(context=context)
        workflow_input = WorkflowInput(agent_input=agent_input)

        async def run_summarizer():
            client = await tclient()
            workflow_id = f"summarizer-{data.vfile_id}-{uuid.uuid4().hex[:8]}"
            return await client.execute_workflow(
                TextSummarizerAllWorkflow.run,
                workflow_input,
                id=workflow_id,
                task_queue="antbed-queue",
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
            )

        summaryoutput = asyncio.run(run_summarizer())

        if summaryoutput is None or summaryoutput.result is None:
            raise ValueError("Summary failed or returned empty result")

        summaries = []
        result = summaryoutput.result
        if "machine" in variants_to_generate and result.machine:
            summaries.append(add_summary_output(vf=vf, output=result.machine, variant="machine", session=session))
        if "pretty" in variants_to_generate and result.pretty:
            summaries.append(add_summary_output(vf=vf, output=result.pretty, variant="pretty", session=session))

        # Include existing summary IDs as well
        data.summary_ids.extend([s.id for s in summaries])

        activity.heartbeat()
        return data
