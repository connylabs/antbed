import datetime
import logging
import re
import tempfile
from pathlib import Path

from openai import OpenAI
from openai.types import VectorStore

from antbed.clients.llm import openai_client
from antbed.db.models import Vector, VFile, VFileSplit, VFileUpload
from antbed.vectordb.base import VectorDB

OPENAI_PROJECT_NAME = "askmycase"

logger = logging.getLogger(__name__)


class VectorOpenAI(VectorDB):
    def __init__(self, openai: OpenAI | None = None):
        if openai is None:
            openai = openai_client()
        self.client = openai

    @property
    def manager_name(self) -> str:
        return "openai"

    def create_vector(self, vector: Vector, **kwargs):
        subject_type, subject_id, vector_type = vector.subject_type, vector.subject_id, vector.vector_type
        expires_days = kwargs.get("expires_days")
        vname = f"v-{subject_type}_{subject_id}-{vector_type}"
        metadata = {"subject_id": str(subject_id), "subject_type": subject_type, "type": vector_type}
        openai_vector = self.client.vector_stores.create(name=vname, metadata=metadata)

        if expires_days is not None:
            openai_vector = self.expires_vector(openai_vector.id, expires_days=expires_days)

        vector.external_provider = "openai"
        vector.external_id = openai_vector.id
        return vector

    def expires_vector(self, external_id: str, expires_days: int) -> VectorStore:
        return self.client.vector_stores.update(
            external_id, expires_after={"anchor": "last_active_at", "days": expires_days}
        )

    @classmethod
    def gen_filename(cls, fname: str | Path, date: datetime.datetime | None, kind: str | None = None):
        if kind is None:
            kind = "content"
        if date is None:
            date = datetime.datetime.now(datetime.UTC)
        name = Path(re.sub(r"[\[\].+ *:/]", "_", str(fname).replace("/", "")))
        return f"{date.strftime('%Y-%m-%d')}_{kind}-{name}.txt"

    def upload_content(self, ifile: VFile) -> VFileUpload:
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = self.gen_filename(ifile.source_filename, ifile.source_created_at, ifile.subject_type)
            content_path = Path(f"{tmpdir}/{filename}")
            with open(content_path, "w") as tmpfile:
                tmpfile.write(ifile.content())
            with open(str(content_path), "rb") as tmpfile:
                upload = self.client.files.create(file=tmpfile, purpose="assistants")
        return VFileUpload(
            vfile_id=ifile.id, external_provider=self.manager_name, external_id=upload.id, filename=filename
        )

    # def delete_file(self, ifile: VFile):
    #     if ifile.external_id is not None:
    #         with suppress(NotFoundError):
    #             self.client.files.delete(ifile.external_id)
    #         self.db.delete_vfile(ifile)
    #     return ifile

    # def delete_vector(self, vector: Vector):
    #     [self.delete_file(vfile.vfile) for vfile in vector.vfiles]
    #     if vector.external_id is not None:
    #         with suppress(NotFoundError):
    #             self.client.vector_stores.delete(vector.external_id)
    #         self.db.delete_vector(vector)
    #     return vector

    def add_points(self, vector: Vector, vsplit: VFileSplit, vfile: VFile) -> str:
        _ = vsplit
        vfu = (
            VFileUpload.where(VFileUpload.vfile_id == vfile.id, VFileUpload.external_provider == "openai")
            .scalars()
            .one()
        )
        if vfu.external_id is None or vector.external_id is None:
            print("raise")
            raise ValueError("VFileUpload or Vector external_id is None")
        res = self.client.vector_stores.files.create(
            vector_store_id=str(vector.external_id), file_id=str(vfu.external_id), timeout=3.0
        )
        logger.info(f"Added {vfu.filename}({vfu.external_id}) to {vector.external_id}")
        return res.id
