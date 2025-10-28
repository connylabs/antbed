import logging
import uuid
from collections.abc import Sequence
from functools import cache
from typing import Any, Literal

from activealchemy.activerecord import Select
from activealchemy.engine import ActiveEngine
from sqlalchemy import and_, not_, or_, tuple_
from sqlalchemy.orm import joinedload

from .config import config
from .db.models import (
    Base,
    Collection,
    Embedding,
    Summary,
    Vector,
    VectorVFile,
    VFile,
    VFileCollection,
    VFileSplit,
    VFileUpload,
)
from .models import Content, DocsQuery, SummaryOutputProtocol, WithContentMode

logger = logging.getLogger(__name__)


class DB:
    def __init__(self) -> None:
        self.models = [Base, Vector, VFile, VFileSplit, VFileUpload, Embedding, VectorVFile]
        self.engine = ActiveEngine(config().antbed.postgresql)
        self.set_engine(Base)

        self.reconnect(dispose=False)

    def reconnect(self, dispose: bool = True) -> None:
        if dispose:
            self.engine.dispose_engines()
        self.engine = ActiveEngine(config().antbed.postgresql)
        self.check()

    def new_session(self, session=None):
        if session:
            return session
        _, session_factory = self.engine.session()
        return session_factory()

    def check(self) -> None:
        for model in self.models:
            if not model.__active_engine__:
                self.set_engine(model)

    def set_engine(self, model) -> None:
        model.set_engine(self.engine)

    def add_vector(self, vector: Vector, session=None) -> Vector:
        return Vector.add(vector, commit=True, session=session)

    def add_vfile(self, vfile: VFile, session=None) -> VFile:
        return vfile.save(commit=True, session=session)

    def add_summary_output(
        self,
        vfile_id: uuid.UUID,
        output: SummaryOutputProtocol,
        variant_name: str = "default",
        update: bool = True,
        session=None,
    ) -> Summary:
        s = (
            Summary.where(Summary.vfile_id == vfile_id, Summary.variant_name == variant_name, session=session)
            .scalars()
            .first()
        )
        if s is not None:
            logger.warning(f"Summary for vfile {vfile_id} with variant {variant_name} already exists")
            if not update:
                return s
        else:
            logger.info(f"Creating new summary for vfile {vfile_id} with variant {variant_name}")
            s = Summary()
        s.vfile_id = vfile_id
        s.summary = output.short_version
        s.tags = output.tags
        s.description = output.description
        s.title = output.title
        s.language = output.language
        s.variant_name = variant_name

        return s.save(commit=True, session=session)

    def delete_vector(self, vector: Vector, session=None) -> None:
        Vector.delete(vector, session=session)

    def delete_vfile(self, vfile: VFile, session=None) -> None:
        VFile.delete(vfile, session=session)

    def add_vector_vfile(self, vvfile: VectorVFile, session=None) -> VectorVFile:
        return VectorVFile.add(vvfile, commit=True, session=session)

    def get_collection(self, name: str, session=None) -> Collection | None:
        return Collection.where(Collection.collection_name == name, session=session).scalars().first()

    def add_collection(self, collection: Collection, session=None) -> Collection:
        return Collection.add(collection, commit=True, session=session)

    def add_vfile_collections(
        self, vfile_collections: list[VFileCollection], session=None
    ) -> Sequence[VFileCollection]:
        #        return [VFileCollection.add(vc, commit=True, session=session) for vc in vfile_collections]
        return VFileCollection.add_all(
            vfile_collections, skip_duplicate=True, commit=True, fields={"vfile_id", "collection_id"}, session=session
        )

    def get_vector(
        self,
        subject_id: str | None,
        subject_type: str | None = "extern",
        vector_type: str | None = "all",
        external_provider: Literal["qdrant", "openai"] = "qdrant",
        session=None,
    ) -> Vector | None:
        return (
            Vector.where(
                Vector.subject_id == subject_id,
                Vector.subject_type == subject_type,
                Vector.vector_type == vector_type,
                Vector.external_provider == external_provider,
                session=session,
            )
            .scalars()
            .first()
        )

    def get_vfile(self, subject_id: str | None, subject_type: str | None = "extern", session=None) -> VFile | None:
        return (
            VFile.where(VFile.subject_id == subject_id, VFile.subject_type == subject_type, session=session)
            .scalars()
            .first()
        )

    def get_vector_vfile(self, vector_id: uuid.UUID, vfile_id: uuid.UUID, session=None) -> VectorVFile | None:
        return (
            VectorVFile.where(VectorVFile.vector_id == vector_id, VectorVFile.vfile_id == vfile_id, session=session)
            .scalars()
            .first()
        )

    def get_last_vector(self) -> Vector | None:
        return Vector.last()

    def get_split(self, vfile_id: uuid.UUID, split_id: uuid.UUID | None, session=None) -> VFileSplit | None:
        if split_id is None:
            vsplit = (
                VFileSplit.where(VFileSplit.vfile_id == vfile_id, session=session)
                .order_by(VFileSplit.created_at.desc())
                .limit(1)
                .scalars()
                .first()
            )
        else:
            vsplit = VFileSplit.where(VFileSplit.id == uuid.UUID(split_id)).scalars().first()
        return vsplit

    def find_embedding(self, id: uuid.UUID, session=None) -> Embedding:
        return Embedding.where(Embedding.id == id, session=session).scalars().one()

    def find_vfile(self, id: uuid.UUID, session=None) -> VFile:
        return VFile.where(VFile.id == id, session=session).scalars().one()

    def _get_vfile_for_content(
        self,
        vfile_id: uuid.UUID | str | None,
        vfile: VFile | None,
        chunk_id: uuid.UUID | str | None,
        session: Any,
    ) -> VFile:
        if chunk_id is not None:
            emb = self.find_embedding(uuid.UUID(str(chunk_id)), session=session)
            if vfile is None:  # Check if vfile needs to be loaded
                return self.find_vfile(uuid.UUID(str(emb.vfile_id)), session=session)
            return vfile
        if vfile_id is not None and vfile is None:
            return self.find_vfile(uuid.UUID(str(vfile_id)), session=session)
        if vfile is None:
            raise ValueError("vfile_id or vfile is required when chunk_id is not provided")
        return vfile

    def _populate_content_from_summary(
        self,
        content: Content,
        selected_summary: Summary | None,
        keys: set[str],
        with_content: WithContentMode,
        vfile_id_for_logging: uuid.UUID,
        summary_variant: str,
    ) -> None:
        if selected_summary is not None:
            if "title" in keys:
                content.title = selected_summary.title
            if "description" in keys:
                content.description = selected_summary.description
            if "keywords" in keys:
                content.keywords = selected_summary.tags or []
            if with_content == WithContentMode.SUMMARY:
                content.summary = selected_summary.summary
            if "language" in keys:
                content.language = selected_summary.language
            if "summary_variant" in keys:
                content.summary_variant = selected_summary.variant_name
        elif with_content == WithContentMode.SUMMARY:
            logger.warning(f"Summary variant '{summary_variant}' not found for VFile {vfile_id_for_logging}")

    def get_content(
        self,
        with_content: WithContentMode,
        *,
        vfile_id: uuid.UUID | str | None = None,
        vfile: VFile | None = None,
        chunk_id: uuid.UUID | str | None = None,
        metadata: dict[str, Any] | None = None,
        keys: set[str] | None = None,
        summary_variant: str = "default",  # Added summary_variant
        session=None,
    ) -> Content:
        keys = keys if keys is not None else set()
        metadata = metadata if metadata is not None else {}
        content = Content(mode=with_content, metadata=metadata)

        with self.new_session(session) as sess:
            vfile_instance = self._get_vfile_for_content(vfile_id, vfile, chunk_id, sess)

            if with_content == WithContentMode.FULL:
                content.verbatim = vfile_instance.content(summary=False)  # Ensure not fetching summary here

            selected_summary: Summary | None = vfile_instance.summary(variant=summary_variant)
            self._populate_content_from_summary(
                content, selected_summary, keys, with_content, vfile_instance.id, summary_variant
            )
            return content

    # pylint: disable=too-return-statements
    def build_jsonb_filter(self, column, filter_spec):
        """
        Recursively build filters for JSONB column from provided filter spec.

        :param column: SQLAlchemy JSONB column
        :param filter_spec: Dictionary specifying filters
        :return: SQLAlchemy filter
        """
        if "and" in filter_spec:
            clause = and_(*[self.build_jsonb_filter(column, f) for f in filter_spec["and"]])
        elif "or" in filter_spec:
            clause = or_(*[self.build_jsonb_filter(column, f) for f in filter_spec["or"]])
        elif "not" in filter_spec:
            clause = not_(self.build_jsonb_filter(column, filter_spec["not"]))
        elif "exists" in filter_spec:
            key = filter_spec["exists"]
            clause = column.has_key(key)
        elif "not_exists" in filter_spec:
            key = filter_spec["not_exists"]
            clause = not_(column.has_key(key))
        else:
            kv = filter_spec.get("equals", filter_spec)
            clause = column.contains(kv)

        return clause

    def prep_query(self, query: DocsQuery, session=None) -> Select[VFile]:
        q = VFile.select(session)
        # if query.direction is not None and query.direction != "both":
        #     q = q.where(VFile.info["direction"] == query.direction)
        if query.date_gt is not None:
            q = q.where(VFile.source_created_at >= query.date_gt)
        if query.date_lt is not None:
            q = q.where(VFile.source_created_at <= query.date_lt)
        if query.limit:
            q = q.limit(query.limit)
        if query.ids:
            tup = tuple_(VFile.subject_type, VFile.subject_id)
            q = q.where(tup.in_(query.ids))
        if query.filters:
            q = q.where(self.build_jsonb_filter(VFile.info, query.filters))
        q = q.options(joinedload(VFile.summaries))
        if query.collection_name or query.collection_id:
            q = q.join(
                Collection,
                or_(Collection.collection_name == query.collection_name, Collection.id == query.collection_id),
            )
            q = q.join(
                VFileCollection,
                and_(VFile.id == VFileCollection.vfile_id, VFileCollection.collection_id == Collection.id),
            )
        if query.order is not None and query.order == "desc":
            q = q.order_by(VFile.source_created_at.desc())
        else:
            q = q.order_by(VFile.source_created_at.asc())
        return q

    def scroll(self, query: DocsQuery, session=None) -> list[VFile]:
        q = self.prep_query(query, session=session)
        session = VFile.new_session(session)
        return session.execute(q).unique().scalars().all()


@cache
def cached_db() -> DB:
    return DB()


def antbeddb() -> DB:
    db = cached_db()
    db.check()
    return db
