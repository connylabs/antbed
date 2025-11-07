from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError
from temporalloop.utils import as_completed_with_concurrency

with workflow.unsafe.imports_passed_through():
    from antgent.agents.summarizer.models import SummaryInput
    from antgent.models.agent import AgentInput
    from antgent.workflows.base import WorkflowInput
    from antgent.workflows.summarizer.text import TextSummarizerAllWorkflow

    from antbed.models import EmbeddingRequest, UploadRequest, UploadRequestIDs
    from antbed.temporal.activities import (
        add_vfile_to_collection,
        get_or_create_file,
        save_summaries_to_db,
        vfile_has_summaries,
    )

MAX_CONCURRENT = 10


@workflow.defn
class UploadWorkflow:
    def __init__(self) -> None:
        self.upload: None | UploadRequest = None
        self.urir: UploadRequestIDs = UploadRequestIDs()
        self.embeddings: list[EmbeddingRequest] = []
        self.is_ready: bool = False

    @workflow.run
    async def run(self, upload: UploadRequest) -> UploadRequestIDs:
        workflow.logger.info("Workflow start Upload")

        activities = []
        # 1. Upload the file
        self.urir = await workflow.start_activity(
            get_or_create_file,
            upload,
            start_to_close_timeout=timedelta(minutes=120),
            schedule_to_close_timeout=timedelta(hours=24),
        )
        # 3. Attach the file to a vector for retriaval later
        if upload.collection_name is not None:
            activities.append(
                workflow.start_activity(
                    add_vfile_to_collection,
                    self.urir,
                    start_to_close_timeout=timedelta(minutes=120),
                    schedule_to_close_timeout=timedelta(hours=24),
                )
            )

        # 5. Run summarization as a child workflow if requested
        summary_result = None
        should_summarize = upload.summarize
        if should_summarize and not upload.resummarize and self.urir.vfile_id:
            has_summaries = await workflow.start_activity(
                vfile_has_summaries,
                args=[self.urir.vfile_id],
                start_to_close_timeout=timedelta(minutes=5),
            )
            if has_summaries:
                workflow.logger.info(
                    "All summary variants already exist and resummarize is false, skipping summarization."
                )
                should_summarize = False

        if should_summarize:
            workflow.logger.info("Starting summarization child workflow")
            # Prepare workflow input using content from the upload request
            # (vfile_id is already in self.urir from get_or_create_file activity)
            content = "\n".join(upload.doc.pages)
            context = SummaryInput(content=content)
            agent_input = AgentInput(context=context)
            workflow_input = WorkflowInput(agent_input=agent_input)

            # Execute as child workflow
            try:
                summary_output = await workflow.execute_child_workflow(
                    TextSummarizerAllWorkflow.run,
                    workflow_input,
                    id=f"summarizer-{self.urir.vfile_id}",
                    task_queue="antbed-queue",
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                # Convert to serializable dict for activity
                if summary_output and summary_output.result:
                    summary_result = summary_output.model_dump(mode="json")
                workflow.logger.info("Summarization child workflow completed")
            except Exception as e:
                workflow.logger.error(f"Summarization child workflow failed: {e}")
                # Continue workflow even if summarization fails
                summary_result = None

        # 6. Save summary results to database via activity
        if summary_result is not None:
            activities.append(
                workflow.start_activity(
                    save_summaries_to_db,
                    args=[self.urir, summary_result],
                    start_to_close_timeout=timedelta(minutes=5),
                    schedule_to_close_timeout=timedelta(minutes=10),
                )
            )

        if upload.translate is not None:
            # 6. Translate the content
            workflow.logger.info("Translate the content")
            pass

        if upload.translate_summary:
            # 7. Translate the summary
            workflow.logger.info("Translate the summary")
            pass

        last_error = None
        workflow.logger.info(f"Start activities: {len(activities)}...")
        async for res in as_completed_with_concurrency(MAX_CONCURRENT, workflow, *activities):
            try:
                self.urir = await res
            except ActivityError as e:
                workflow.logger.error(f"ActivityFailure: {e}, continue...")
                last_error = e

        # self.is_ready = True

        # workflow.logger.info(f"Start embeddings activities: {len(embeddings_activities)}...")
        # async for res in as_completed_with_concurrency(MAX_CONCURRENT, workflow, *embeddings_activities):
        #     try:
        #         self.embeddings.append(await res)
        #     except ActivityError as e:
        #         workflow.logger.error(f"ActivityFailure: {e}, continue...")
        #         last_error = e

        if last_error:
            raise last_error

        return self.urir

    @workflow.query
    def query_urir(self) -> UploadRequestIDs:
        return self.urir

    @workflow.query
    def query_ready(self) -> dict[str, bool]:
        return {"ready": self.is_ready}

    @workflow.query
    def query_embeddings(self) -> list[EmbeddingRequest]:
        return self.embeddings
