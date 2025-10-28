# pylint: disable=no-name-in-module
# pylint: disable=no-self-argument
# pylint: disable=too-few-public-methods
import logging
from typing import Any

import temporalio.client
from ant31box.server.exception import ResourceNotFound
from fastapi import APIRouter
from temporalloop.importer import import_from_string

from antbed.models import AsyncResponse
from antbed.temporal.client import tclient

router = APIRouter(prefix="/api/v1/job", tags=["antbed", "status"])

logger = logging.getLogger(__name__)


async def get_handler_from_ar(
    ar: AsyncResponse,
) -> tuple[temporalio.client.WorkflowHandle[Any, Any], Any]:
    """
    Retrieve the workflow handler and workflow object from the AsyncResponse.

    :param ar: The AsyncResponse object containing the job details.
    :return: A tuple containing the workflow handler and workflow object.
    """
    return await get_handler(ar.payload.jobs[0].uuid, ar.payload.jobs[0].name)


async def get_handler(
    workflow_id: str,
    workflow_name: str,
) -> tuple[temporalio.client.WorkflowHandle[Any, Any], Any]:
    """
    Retrieve the workflow handler and workflow object for the given workflow ID and name.

    :param workflow_id: The ID of the workflow.
    :param workflow_name: The name of the workflow.
    :return: A tuple containing the workflow handler and workflow object.
    """
    workflow = import_from_string(workflow_name)
    # Retrieve running workflow handler
    client = await tclient()
    return (
        client.get_workflow_handle_for(workflow_id=workflow_id, workflow=workflow.run),
        workflow,
    )


@router.post("/status", response_model=AsyncResponse)
async def status(ar: AsyncResponse, with_result: bool = False) -> AsyncResponse:
    """
    Retrieve the status of the workflow and update the AsyncResponse object.

    :param ar: The AsyncResponse object containing the job details.
    :return: The updated AsyncResponse object with the workflow status and result.
    """
    for job in ar.payload.jobs:
        workflow_id = job.uuid
        handler, _ = await get_handler_from_ar(ar)
        describe = await handler.describe()
        j = job
        if not describe.status:
            raise ResourceNotFound("Workflow not found", {"workflow_id": workflow_id})
        j.status = describe.status.name
        ## Don't include result. Add new endpoint for result if needed
        if describe.status == temporalio.client.WorkflowExecutionStatus.COMPLETED and with_result:
            j.result = await handler.result()
    ar.gen_signature()
    return ar
