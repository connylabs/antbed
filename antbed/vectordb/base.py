import logging

from antbed.db.models import Vector, VFile, VFileSplit, VFileUpload

logger = logging.getLogger(__name__)


class VectorDB:
    def __init__(self, client=None):
        self.client = client

    @property
    def manager_name(self) -> str:
        raise NotImplementedError("manager_name")

    def create_vector(self, vector: Vector, **kwargs):
        _ = kwargs
        _ = vector
        raise NotImplementedError("create_vector")

    @staticmethod
    def vector_id(subject_id: int, subject_type: str, vector_type: str):
        return f"v-{subject_type}_{subject_id}_{vector_type}"

    def upload_content(self, ifile: VFile) -> VFileUpload:
        return VFileUpload(vfile_id=ifile.id, external_provider=self.manager_name, external_id=None)

    def add_points(self, vector: Vector, vsplit: VFileSplit, vfile: VFile) -> str:
        _ = vector
        _ = vsplit
        _ = vfile
        raise NotImplementedError("add_points")


class NoopVectorDB(VectorDB):
    @property
    def manager_name(self) -> str:
        return "noop"

    def create_vector(self, vector: Vector, **kwargs):
        _ = kwargs
        return vector

    def add_points(self, vector: Vector, vsplit: VFileSplit, vfile: VFile) -> str:
        _ = vsplit
        _ = vfile
        return vector.id

    def upload_content(self, ifile: VFile) -> VFileUpload:
        return VFileUpload(vfile_id=ifile.id, external_provider=self.manager_name, external_id=None)
