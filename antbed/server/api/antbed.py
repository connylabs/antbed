#!/usr/bin/env python3
# pylint: disable=no-name-in-module
# pylint: disable=too-few-public-methods

import asyncio
import logging
from datetime import timedelta
from typing import Any

import temporalio.client
from fastapi import APIRouter
from temporalio.client import WorkflowHandle
from temporalio.common import WorkflowIDReusePolicy
from temporalio.service import RPCError, RPCStatusCode

from antbed.models import AsyncResponse, EmbeddingWorkflowInput, Job, UploadRequest
from antbed.server.api.job_info import get_handler
from antbed.temporal.client import tclient
from antbed.temporal.workflows.embedding import EmbeddingWorkflow
from antbed.temporal.workflows.upload import UploadWorkflow
from antbed.version import VERSION

router = APIRouter()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/embedding", tags=["antbed"])


# pylint: disable=dangerous-default-value
@router.get("/")
async def index():
    return VERSION.to_dict()


@router.get("/version")
def version():
    return VERSION.to_dict()


async def create_upload_workflow(jid: str, upload: UploadRequest) -> WorkflowHandle[Any, Any]:
    client = await tclient()
    handler = await client.start_workflow(
        UploadWorkflow.run,
        args=[upload],
        search_attributes={},
        id=jid,
        task_queue="antbed-queue",
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
    )
    return handler


async def create_embedding_workflow(jid: str, upload: UploadRequest) -> WorkflowHandle[Any, Any]:
    client = await tclient()
    data = EmbeddingWorkflowInput(
        subject_id=upload.doc.subject_id, subject_type=upload.doc.subject_type, config=upload.config
    )
    handler = await client.start_workflow(
        EmbeddingWorkflow.run,
        args=[data],
        search_attributes={},
        id=jid,
        task_queue="antbed-queue",
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
    )
    return handler


async def start_upload_workflow(upload: UploadRequest) -> WorkflowHandle[Any, Any]:
    jid = f"upload-{upload.doc.subject_type}-{upload.doc.subject_id}"  # "-{uuid.uuid4().hex}"
    if upload.collection_name:
        jid = f"{jid}-v{upload.collection_name}"
    handler, _ = await get_handler(workflow_id=jid, workflow_name="antbed.temporal.workflows.upload:UploadWorkflow")
    try:
        # Try to update the workflow
        describe = await handler.describe()
    except RPCError as exc:
        # If it fails because the workflow is not found or already completed,
        # create a new one
        if exc.status != RPCStatusCode.NOT_FOUND:
            logger.error("unexpected error: %s", exc)
            # Do not raise create a new workflow
            # raise exc
        handler = await create_upload_workflow(jid, upload)
    describe = await handler.describe()
    if describe.status != temporalio.client.WorkflowExecutionStatus.RUNNING:
        handler = await create_upload_workflow(jid, upload)
    return handler


async def start_embedding_workflow(upload: UploadRequest) -> WorkflowHandle[Any, Any]:
    jid = f"embedding-{upload.doc.subject_type}-{upload.doc.subject_id}"  # "-{uuid.uuid4().hex}"
    if upload.collection_name:
        jid = f"{jid}-v{upload.collection_name}"
    handler, _ = await get_handler(
        workflow_id=jid, workflow_name="antbed.temporal.workflows.embedding:EmbeddingWorkflow"
    )
    try:
        # Try to update the workflow
        describe = await handler.describe()
    except RPCError as exc:
        # If it fails because the workflow is not found or already completed,
        # create a new one
        if exc.status != RPCStatusCode.NOT_FOUND:
            logger.error("unexpected error: %s", exc)
            # Do not raise create a new workflow
            # raise exc
        handler = await create_embedding_workflow(jid, upload)
    describe = await handler.describe()
    if describe.status != temporalio.client.WorkflowExecutionStatus.RUNNING:
        handler = await create_embedding_workflow(jid, upload)
    return handler


async def wait_for_result(
    workflow_name: str,
    handler: WorkflowHandle[Any, Any],
    wait: bool = False,
    timeout: int = 60,
    root_key: str | None = None,
) -> Job:
    results = {}
    if wait:
        try:
            res = await asyncio.wait_for(handler.result(rpc_timeout=timedelta(seconds=timeout)), timeout=timeout)
            if root_key:
                results[root_key] = res.model_dump()
            else:
                results = res.model_dump()
        except TimeoutError:
            pass
    status = "UNKNOWN"
    workflow_status = (await handler.describe()).status
    if workflow_status is not None:
        status = workflow_status.name

    return Job(uuid=handler.id, name=workflow_name, status=status, result=results)


@router.post("/upload", response_model=AsyncResponse)
async def upload(upload: UploadRequest, wait: bool = False) -> AsyncResponse:
    """
    :return: An AsyncResponse object containing the job details.
    """
    upload_handler = await start_upload_workflow(upload)
    ar = AsyncResponse()
    ar.payload.jobs.append(
        await wait_for_result("antbed.temporal.workflows.upload:UploadWorkflow", upload_handler, wait, 60)
    )

    if not upload.skip_embedding:
        embedding_handler = await start_embedding_workflow(upload)
        ar.payload.jobs.append(
            await wait_for_result(
                "antbed.temporal.workflows.embedding:EmbeddingWorkflow", embedding_handler, wait, 60, "embeddings"
            )
        )
    return ar
    # Generate a unique id for the workflow
