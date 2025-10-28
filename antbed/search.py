import json
import logging
from collections.abc import Sequence
from typing import Any

import sentry_sdk as sentry
import sqlalchemy as sa
from openai import OpenAI

from antbed.clients import openai_client
from antbed.db.models import VFile
from antbed.models import Content, DocsQuery, SearchRecord, WithContentMode
from antbed.store import antbeddb

logger = logging.getLogger(__name__)


class SearchManager:
    def __init__(self, oclient: OpenAI | None = None) -> None:
        # Initialize the search
        self.openai_client = oclient if oclient else openai_client()

    def get_all(self, query: DocsQuery, session: sa.orm.Session | None = None) -> list[VFile]:
        return antbeddb().scroll(query, session=session)
        # return [SearchRecord.from_vfile(vfile.to_pydantic()) for vfile in vfiles]

    def hits_to_markdown(
        self,
        records: list[VFile],
        keys: Sequence[tuple[str, str]] | None = None,
        with_content: WithContentMode = WithContentMode.SUMMARY,
        summary_variant: str = "default",  # Added
    ) -> str:
        antbeddb().check()
        res = []
        data = self.hits_to_model(records, keys, with_content, summary_variant=summary_variant)  # Pass summary_variant
        for hit in data:
            res.append("\n\n -----\n\n")
            res.append("\n## Metadata\n\n")
            for key, value in hit.metadata.items():
                res.append(f"- {key}: {value}\n")
            if hit.keywords:
                res.append(f"- tags: {','.join(hit.keywords)}\n")
            if hit.language:
                res.append(f"- lang: {hit.language}\n")
            if hit.title:
                res.append(f"- title: {hit.title}\n")
            if hit.description:
                res.append(f"- short: {hit.description}\n")
            res.append("\n## Content\n\n")
            res.append(hit.content())
        return "".join(res)

    def hits_to_dict(
        self,
        records: list[VFile],
        keys: Sequence | None = None,
        with_content: WithContentMode = WithContentMode.SUMMARY,
    ) -> list[dict[str, Any]]:
        contents = self.hits_to_model(records, keys, with_content)
        return [content.model_dump(exclude_none=True, exclude=set(["mode"]), by_alias=True) for content in contents]

    def hits_to_json(
        self,
        records: list[VFile],
        keys: Sequence | None = None,
        with_content: WithContentMode = WithContentMode.SUMMARY,
    ) -> str:
        return json.dumps(self.hits_to_dict(records, keys, with_content), indent=2)

    def hits_to_model(
        self,
        records: list[VFile],
        keys: Sequence | None = None,
        with_content: WithContentMode = WithContentMode.SUMMARY,
        summary_variant: str = "default",
    ) -> list[Content]:
        res = []
        antbeddb().check()
        if keys is None:
            keys = [
                ("subject_id", "id"),
                ("subject_type", "type"),
                ("created_at", "date"),
                ("filename", "name"),
                ("source_url", "url"),
                ("language", "language"),
                ("keywords", "keywords"),
                #               ("source", "src"),
                #                 ("score", "score"),
                # ("file_id", "id"),
                # ("vfile_id", "id"),
                #
                ("content_type", "mime"),
                ("metadata", "metadata"),
                ("title", "title"),
                ("description", "description"),
                ("summary_variant", "summary_variant"),
                #                ("chunk_id", "chunk_id"),
                #                ("vector_id", "collection"),
            ]
        key_set = set([name for _, name in keys])

        for hit in records:
            payload = SearchRecord.from_vfile(hit.to_pydantic()).payload
            if payload is None:
                payload = {}

            data = payload
            try:
                searchhit = antbeddb().get_content(
                    with_content,
                    vfile=hit,
                    metadata=data,
                    keys=key_set,
                    summary_variant=summary_variant,
                )
            except ValueError as e:
                logger.error(f"Error: {e}")
                sentry.capture_exception(e)
                continue
            if len(keys) > 0:
                metadata = {name: payload.get(key, "") for key, name in keys if payload.get(key)}
                data = {key: value for key, value in metadata.items() if key in key_set}

            searchhit.metadata = data
            res.append(searchhit)

        return res
