from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError
from temporalloop.utils import as_completed_with_concurrency

with workflow.unsafe.imports_passed_through():
    from antbed.models import EmbeddingRequest, UploadRequest, UploadRequestIDs
    from antbed.temporal.activities import add_vfile_to_collection, get_or_create_file, summarize

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

        if upload.summarize:
            # 5. Summarize the content
            activities.append(
                workflow.start_activity(
                    summarize,
                    self.urir,
                    start_to_close_timeout=timedelta(minutes=120),
                    schedule_to_close_timeout=timedelta(hours=24),
                    retry_policy=RetryPolicy(maximum_attempts=3),
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
