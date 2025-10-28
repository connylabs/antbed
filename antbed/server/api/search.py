#!/usr/bin/env python3
# pylint: disable=no-name-in-module
# pylint: disable=too-few-public-methods
import logging

from fastapi import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.responses import PlainTextResponse

from antbed.models import DocsQuery, DocsResponse, OutputFormatEnum, SearchQuery
from antbed.search import SearchManager
from antbed.store import antbeddb

router = APIRouter()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/docs", tags=["antbed", "search", "callback"])


# pylint: disable=dangerous-default-value
@router.post(
    "/search",
    response_description="return all the matching documents",
    summary="Execute a semantic search and returns matching documents",
    response_model=DocsResponse,
    response_model_exclude_defaults=True,
    response_model_exclude_unset=True,
    response_model_exclude={"docs": {"__all__": {"tags", "keywords", "lang", "language"}}},
    response_model_by_alias=True,
    responses={
        200: {
            "description": (
                "Search documents and return the matching documents as JSON or markdown, "
                "with either summarized or full content."
            ),
            "content": {
                "text/plain": {"description": "Returns matching documents as markdown."},
            },
        },
    },
)
def search(query: SearchQuery):
    sm = SearchManager()
    # Assuming sm.search() doesn't need summary_variant directly, but hits_to_model/markdown does
    records = sm.search(  # This part might need adjustment if sm.search itself needs summary_variant for some reason
        collection_name=query.collection_name, query=query.query, filters=query.filters, limit=query.limit
    )
    if query.output == OutputFormatEnum.MARKDOWN:
        return PlainTextResponse(
            sm.hits_to_markdown(records, query.keys, with_content=query.mode, summary_variant=query.summary_variant)
        )

    if query.output == OutputFormatEnum.JSON:
        return DocsResponse(
            docs=sm.hits_to_model(records, query.keys, with_content=query.mode, summary_variant=query.summary_variant),
            query=query,
        )
    raise HTTPException(status_code=400, detail="output not supported")


@router.post(
    "/scroll",
    response_description="return all the content for a given vector",
    summary="Return all the content for a givenvector",
    response_model=DocsResponse,
    response_model_exclude_defaults=True,
    response_model_exclude_unset=True,
    # response_model_exclude={"docs": {"__all__": {"tags", "keywords", "lang", "language"}}},
    response_model_by_alias=True,
    responses={
        200: {
            "description": (
                "Return all content for a given vector as JSON or markdown, with either summarized or full content."
            ),
            "content": {
                "text/plain": {"description": "Return all content for a given vector as markdown."},
            },
        },
    },
)
def scroll(query: DocsQuery):
    sm = SearchManager()
    antbeddb().check()
    with antbeddb().new_session() as session:
        print(query.model_dump())
        records = sm.get_all(query, session=session)
        logger.info("generating TOC: %s", query.output)
        if query.output == OutputFormatEnum.MARKDOWN:
            return PlainTextResponse(
                sm.hits_to_markdown(records, query.keys, with_content=query.mode, summary_variant=query.summary_variant)
            )
        if query.output == OutputFormatEnum.JSON:
            return DocsResponse(
                docs=sm.hits_to_model(
                    records, query.keys, with_content=query.mode, summary_variant=query.summary_variant
                ),
                query=query,
            )

    raise HTTPException(status_code=400, detail="output not supported")
