from datetime import timedelta

from temporalio import workflow
from temporalio.exceptions import ActivityError
from temporalloop.utils import as_completed_with_concurrency

with workflow.unsafe.imports_passed_through():
    from antbed.models import EmbeddingRequest, EmbeddingWorkflowInput, UploadRequest, UploadRequestIDs
    from antbed.temporal.activities import embedding, get_or_create_split, get_vfile_id

MAX_CONCURRENT = 10


@workflow.defn
class EmbeddingWorkflow:
    def __init__(self) -> None:
        self.upload: None | UploadRequest = None
        self.urir: UploadRequestIDs = UploadRequestIDs()
        self.embeddings: list[EmbeddingRequest] = []
        self.is_ready: bool = False

    @workflow.run
    async def run(self, data: EmbeddingWorkflowInput) -> list[EmbeddingRequest]:
        workflow.logger.info("Workflow start Upload")
        embeddings_activities = []
        # 1. Get the file ID
        if data.vfile_id is None:
            data.vfile_id = (
                await workflow.start_activity(
                    get_vfile_id,
                    args=[data.subject_id, data.subject_type],
                    start_to_close_timeout=timedelta(minutes=120),
                    schedule_to_close_timeout=timedelta(hours=24),
                )
            ).vfile_id

        self.urir = UploadRequestIDs(vfile_id=data.vfile_id, config=data.config)
        # 2. Split the file in multiple chunks, do not embed them yet
        self.urir = await workflow.start_activity(
            get_or_create_split,
            self.urir,
            start_to_close_timeout=timedelta(minutes=120),
            schedule_to_close_timeout=timedelta(hours=24),
        )

        # if upload.vector is not None:
        #     activities.append(
        #         workflow.start_activity(
        #             add_vfile_to_vector,
        #             self.urir,
        #             start_to_close_timeout=timedelta(minutes=120),
        #             schedule_to_close_timeout=timedelta(hours=24),
        #         )
        #     )

        for embedding_id in self.urir.embedding_ids:
            embeddings_activities.append(
                workflow.start_activity(
                    embedding,
                    EmbeddingRequest(embedding_id=embedding_id),
                    start_to_close_timeout=timedelta(minutes=120),
                    schedule_to_close_timeout=timedelta(hours=24),
                )
            )

        workflow.logger.info(f"Start embeddings activities: {len(embeddings_activities)}...")
        async for res in as_completed_with_concurrency(MAX_CONCURRENT, workflow, *embeddings_activities):
            try:
                self.embeddings.append(await res)
            except ActivityError as e:
                workflow.logger.error(f"ActivityFailure: {e}, continue...")
        return self.embeddings

    @workflow.query
    def query_urir(self) -> UploadRequestIDs:
        return self.urir

    @workflow.query
    def query_embeddings(self) -> list[EmbeddingRequest]:
        return self.embeddings
