# pylint: disable=singleton-comparison
# pylint: disable=unsubscriptable-object
# pylint: disable=too-many-ancestors
# ruff: noqa: E711
import logging
import uuid
from abc import abstractmethod
from datetime import datetime
from typing import Annotated, Any, AnyStr, ClassVar, Optional, TypeVar

import tiktoken
from activealchemy.activerecord import ActiveRecord, PKMixin, UpdateMixin
from pydantic import BaseModel, ConfigDict, create_model
from pydantic.fields import FieldInfo
from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column, relationship

logger = logging.getLogger(__name__)

# Base = automap_base()


class ExternalMixin(MappedAsDataclass):
    external_id: Mapped[str | None] = mapped_column(default=None, kw_only=True)
    external_provider: Mapped[str | None] = mapped_column(default=None, kw_only=True)


class TokensMixin(MappedAsDataclass):
    tokens: Mapped[int | None] = mapped_column(default=None)

    def count_tokens(self) -> int:
        encoder = tiktoken.encoding_for_model("gpt-4o")
        return len(encoder.encode(self._content()))

    def update_tokens(self) -> None:
        if self.tokens != self.count_tokens():
            self.tokens = self.count_tokens()

    def save(self, commit=False, session=None):
        """Add this instance to the database."""
        self.update_tokens()
        return self.add(self, commit, session)

    @abstractmethod
    def _content(self) -> str: ...


class SubjectMixin(MappedAsDataclass):
    subject_id: Mapped[str | None] = mapped_column(default=None, kw_only=True, nullable=False)
    subject_type: Mapped[str | None] = mapped_column(default="extern", kw_only=True, nullable=False)


class Base(ActiveRecord, DeclarativeBase):
    @classmethod
    def __columns__fields__(cls) -> Any:
        dd = {}
        for col in list(cls.__table__.columns):
            dd[col.name] = (col.type.python_type, col.default.arg if col.default != None else None)
        return dd


T = TypeVar("T", bound=Base)


class BaseSchema[T](BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True, extra="allow")

    def to_model(self, modelcls: type[T]) -> T:
        inst = modelcls()
        inst.__dict__.update(self.model_dump())
        return inst

    # Source: https://github.com/pydantic/pydantic/issues/1937#issuecomment-695313040
    @classmethod
    def add_fields(cls, **field_definitions: Any):
        new_fields: dict[str, FieldInfo] = {}

        for f_name, f_def in field_definitions.items():
            if isinstance(f_def, tuple):
                try:
                    f_annotation, f_value = f_def
                except ValueError as e:
                    raise Exception(
                        "field definitions should either be a tuple of (<type>, <default>) or just a "
                        "default value, unfortunately this means tuples as "
                        "default values are not allowed"
                    ) from e
            else:
                f_annotation, f_value = None, f_def

            new_fields[f_name] = FieldInfo(annotation=f_annotation | None, default=f_value)

        cls.model_fields.update(new_fields)
        cls.model_rebuild(force=True)


# VFile -> FileUploaded
# VSplit -> configuration of hte chunking
# Embedding -> The chunks of a vsplit with the vector float
# Vector -> Collection of embeddings for retriaval
# VectorVFile -> The relationship between a vector and a file


class VectorSchema(BaseSchema["Vector"]):
    def vector_id(self) -> str:
        return f"v-{self.subject_type}_{self.subject_id}_{self.vector_type}"

    def vector_id_meta(self) -> str:
        return self.vector_id() + "-meta"


class VFileSchema(BaseSchema["VFile"]): ...


class VFileSplitSchema(BaseSchema["VFileSplit"]): ...


class EmbeddingSchema(BaseSchema["Embedding"]): ...


class VFileUploadSchema(BaseSchema["VFileUpload"]): ...


class VectorVFileSchema(BaseSchema["VectorVFile"]): ...


class SummarySchema(BaseSchema["Summary"]): ...


class PromptSchema(BaseSchema["Prompt"]): ...


class CollectionSchema(BaseSchema["Collection"]): ...


class VFileCollectionSchema(BaseSchema["VFileCollection"]): ...


class Summary(Base, PKMixin, UpdateMixin, TokensMixin):
    __tablename__ = "summary"
    __allow_unmapped__ = True
    language: Mapped[str] = mapped_column(default="")
    summary: Mapped[str] = mapped_column(default="")
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), default_factory=list)
    description: Mapped[str] = mapped_column(default="")
    title: Mapped[str] = mapped_column(default="")
    info: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict)
    tokens: Mapped[int | None] = mapped_column(default=None)
    vfile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vfile.id"), nullable=False, default=None)
    vfile: Mapped["VFile"] = relationship(back_populates="summaries", init=False, repr=False)
    prompt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prompt.id"), default=None)
    prompt: Mapped["Prompt"] = relationship(init=False, repr=False)
    variant_name: Mapped[str] = mapped_column(default="default", nullable=False)

    def to_pydantic(self) -> SummarySchema:
        return SummarySchema(**self.to_dict())

    def _content(self) -> str:
        return self.summary


class Prompt(Base, PKMixin, UpdateMixin):
    __tablename__ = "prompt"
    __allow_unmapped__ = True
    name: Mapped[str] = mapped_column(default="")
    prompt: Mapped[str] = mapped_column(default="")
    version: Mapped[str] = mapped_column(default="")
    latest: Mapped[bool] = mapped_column(default=False)
    variables: Mapped[list[str]] = mapped_column(ARRAY(String), default_factory=list)
    info: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict)
    model: Mapped[str] = mapped_column(default="")

    def to_pydantic(self) -> PromptSchema:
        return PromptSchema(**self.to_dict())


class VectorVFile(Base, PKMixin, UpdateMixin, ExternalMixin):
    __tablename__ = "vector_vfile"
    __allow_unmapped__ = True

    vector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vector.id"))
    vfile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vfile.id"))
    vsplit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vfile_split.id"), default=None)
    vector: Mapped["Vector"] = relationship(back_populates="vector_vfile", init=False, repr=False)
    vfile: Mapped["VFile"] = relationship(back_populates="vector_vfile", init=False, repr=False)
    split: Mapped["VFileSplit"] = relationship(back_populates="vector_vfile", init=False, repr=False)

    def to_pydantic(self) -> VectorVFileSchema:
        return VectorVFileSchema(**self.to_dict())


class VFileCollection(Base, PKMixin, UpdateMixin):
    __tablename__ = "vfile_collection"
    __allow_unmapped__ = True

    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collection.id"))
    vfile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vfile.id"))
    collection: Mapped["Collection"] = relationship(back_populates="vfile_collection", init=False, repr=False)
    vfile: Mapped["VFile"] = relationship(back_populates="vfile_collection", init=False, repr=False)

    def to_pydantic(self) -> VFileCollectionSchema:
        return VFileCollectionSchema(**self.to_dict())


class Collection(Base, PKMixin, UpdateMixin):
    __tablename__ = "collection"

    collection_name: Mapped[str] = mapped_column(default="")
    description: Mapped[str | None] = mapped_column(default=None)
    info: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default_factory=dict)
    vfile_collection: Mapped[list[VFileCollection]] = relationship(
        back_populates="collection",
        cascade="save-update, merge, delete, delete-orphan",
        default_factory=list,
        repr=False,
    )
    vfiles: AssociationProxy[list[VectorVFile]] = association_proxy(
        "vfile_collection",
        "vfile",
        creator=lambda vfile: VFileCollection(vfile=vfile),
        default_factory=list,
        repr=False,
    )

    def to_pydantic(self) -> CollectionSchema:
        return CollectionSchema(**self.to_dict())


class VFile(Base, PKMixin, UpdateMixin, SubjectMixin, TokensMixin):
    __tablename__ = "vfile"
    __allow_unmapped__ = True
    source_content_type: Mapped[str] = mapped_column(default="application/pdf")
    source_created_at: Mapped[datetime | None] = mapped_column(default=None)
    source: Mapped[str] = mapped_column(default="")
    source_filename: Mapped[str] = mapped_column(default="")
    pages: Mapped[list[str]] = mapped_column(ARRAY(String), default_factory=list, repr=False)
    vector_vfile: Mapped[list[VectorVFile]] = relationship(
        back_populates="vfile", cascade="all, delete-orphan", default_factory=list, repr=False
    )
    vfile_collection: Mapped[list[VFileCollection]] = relationship(
        back_populates="vfile", cascade="all, delete-orphan", default_factory=list, repr=False
    )
    collections: AssociationProxy[list[VFileCollection]] = association_proxy(
        "vfile_collection",
        "collection",
        creator=lambda collection: VFileCollection(collection_id=collection.id),
        default_factory=list,
        repr=False,
    )
    vectors: AssociationProxy[list[VectorVFile]] = association_proxy(
        "vector_vfile",
        "vector",
        creator=lambda vector: VectorVFile(vector_id=vector.id),
        default_factory=list,
        repr=False,
    )
    splits: Mapped[list["VFileSplit"]] = relationship(
        back_populates="vfile", cascade="all, delete-orphan", default_factory=list, repr=False
    )
    info: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict)

    uploads: Mapped[list["VFileUpload"]] = relationship(
        back_populates="vfile", cascade="all, delete-orphan", default_factory=list, repr=False
    )
    summaries: Mapped[list["Summary"]] = relationship(  # Changed from summary to summaries
        "Summary",
        back_populates="vfile",
        cascade="all, delete-orphan",
        default_factory=list,
        repr=False,
        order_by="Summary.variant_name, Summary.created_at",  # Added order_by
    )

    def summary(self, variant: str = "default") -> Optional["Summary"]:
        for s_item in self.summaries:
            if s_item.variant_name == variant:
                return s_item
            # Fallback: if default variant not found, and requested variant was default, return first available
        if variant == "default" and self.summaries:
            return self.summaries[0]
        return None

    def content(self, summary: bool = False, summary_variant: str = "default") -> str:
        if summary:
            s = self.summary(summary_variant)
            return s.summary if s else ""

        return "\n".join(self.pages)

    def to_pydantic(self) -> VFileSchema:
        return VFileSchema(**self.to_dict())

    def _content(self) -> str:
        return self.content(False)


class VFileSplit(Base, PKMixin, UpdateMixin):
    __tablename__ = "vfile_split"
    __allow_unmapped__ = True

    info: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict)
    config_hash: Mapped[str] = mapped_column(default="")
    vfile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vfile.id"), default=None)
    embeddings: Mapped[list["Embedding"]] = relationship(
        "Embedding",
        back_populates="split",
        cascade="all, delete-orphan",
        default_factory=list,
        order_by="Embedding.part_number.asc()",
    )
    parts: Mapped[int] = mapped_column(default=0)
    chunk_size: Mapped[int] = mapped_column(default=1000)
    chunk_overlap: Mapped[int] = mapped_column(default=0)
    mode: Mapped[str] = mapped_column(default="recursive")
    name: Mapped[str] = mapped_column(default="default")
    model: Mapped[str] = mapped_column(default="")
    vfile: Mapped[VFile] = relationship("VFile", back_populates="splits", init=False, repr=False)
    vectors: AssociationProxy[list[VectorVFile]] = association_proxy(
        "vector_vfile",
        "vector",
        creator=lambda vector: VectorVFile(vector_id=vector.id),
        default_factory=list,
        repr=False,
    )
    vector_vfile: Mapped[list[VectorVFile]] = relationship(
        back_populates="split", cascade="all, delete-orphan", default_factory=list, repr=False
    )

    def to_pydantic(self) -> VFileSplitSchema:
        return VFileSplitSchema(**self.to_dict())


class Vector(Base, PKMixin, UpdateMixin, ExternalMixin, SubjectMixin):
    __tablename__ = "vector"
    __allow_unmapped__ = True
    vector_type: Mapped[str | None] = mapped_column(default=None)
    vector_vfile: Mapped[list[VectorVFile]] = relationship(
        back_populates="vector", cascade="save-update, merge, delete, delete-orphan", default_factory=list, repr=False
    )
    vfiles: AssociationProxy[list[VectorVFile]] = association_proxy(
        "vector_vfile", "vfile", creator=lambda vfile: VectorVFile(vfile=vfile), default_factory=list, repr=False
    )
    splits: AssociationProxy[list[VectorVFile]] = association_proxy(
        "vector_vfile", "split", creator=lambda split: VectorVFile(split=split), default_factory=list, repr=False
    )

    def to_pydantic(self) -> VectorSchema:
        return VectorSchema(**self.to_dict())


class Embedding(Base, PKMixin, UpdateMixin):
    __tablename__ = "embedding"

    vfile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vfile.id"), default=None)
    vfile_split_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vfile_split.id"), default=None)
    embedding_vector: Mapped[list[float]] = mapped_column(ARRAY(Float), default_factory=list, repr=False)
    model: Mapped[str | None] = mapped_column(default="")
    info: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    char_start: Mapped[int | None] = mapped_column(default=0)
    part_number: Mapped[int] = mapped_column(default=0)
    char_end: Mapped[int] = mapped_column(default=-1)
    status: Mapped[str] = mapped_column(default="created")
    vfile: Mapped["VFile"] = relationship("VFile", init=False, repr=False)
    split: Mapped["VFileSplit"] = relationship("VFileSplit", init=False, repr=False)
    content: Mapped[str] = mapped_column(default="")

    def to_pydantic(self) -> EmbeddingSchema:
        return EmbeddingSchema(**self.to_dict())


class VFileUpload(Base, PKMixin, UpdateMixin, ExternalMixin):
    __tablename__ = "vfile_upload"
    vfile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vfile.id"), default=None)
    vfile: Mapped[VFile] = relationship("VFile", init=False, repr=False)
    filename: Mapped[str | None] = mapped_column(default=None)

    def to_pydantic(self) -> VFileUploadSchema:
        return VFileUploadSchema(**self.to_dict())


VFileSchema.add_fields(**VFile.__columns__fields__())
VFileSplitSchema.add_fields(**VFileSplit.__columns__fields__())
VectorSchema.add_fields(**Vector.__columns__fields__())
EmbeddingSchema.add_fields(**Embedding.__columns__fields__())
VFileUploadSchema.add_fields(**VFileUpload.__columns__fields__())
VectorVFileSchema.add_fields(**VectorVFile.__columns__fields__())
SummarySchema.add_fields(**Summary.__columns__fields__())
PromptSchema.add_fields(**Prompt.__columns__fields__())
CollectionSchema.add_fields(**Collection.__columns__fields__())
VFileCollectionSchema.add_fields(**VFileCollection.__columns__fields__())
SummarySchema.add_fields(variant_name=(str, "default"))

# VectorSchema = create_model("VectorSchema", __base__=BaseSchema["Vector"], **Vector.__columns__fields__())

# EmbeddingSchema = create_model("EmbeddingSchema", __base__=BaseSchema["Embedding"], **Embedding.__columns__fields__())
# VFileUploadSchema = create_model(
#     "VFileUploadSchema", __base__=BaseSchema["VFileUpload"], **VFileUpload.__columns__fields__()
# )
# VectorVFileSchema = create_model(
#     "VectorVFileSchema", __base__=BaseSchema["VectorVFile"], **VectorVFile.__columns__fields__()
# )
