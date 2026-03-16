import json
import logging
import re
from typing import Any

import openai
from pydantic import BaseModel

from graphiti_core.llm_client.config import DEFAULT_MAX_TOKENS, ModelSize
from graphiti_core.llm_client.errors import RateLimitError
from graphiti_core.llm_client.openai_generic_client import (
    DEFAULT_MODEL,
    OpenAIGenericClient,
)
from graphiti_core.prompts.models import Message

logger = logging.getLogger(__name__)


class CompatOpenAIGenericClient(OpenAIGenericClient):
    """OpenAI-compatible client with tolerant JSON extraction for loose proxies."""

    @staticmethod
    def _extract_json_text(raw: str) -> str:
        text = (raw or "").strip()
        if not text:
            return text

        if text.startswith("```"):
            lines = text.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
            if text.lower().startswith("json"):
                text = text[4:].lstrip()

        decoder = json.JSONDecoder()
        for idx, ch in enumerate(text):
            if ch not in "{[":
                continue
            try:
                obj, end = decoder.raw_decode(text[idx:])
                return json.dumps(obj, ensure_ascii=False)
            except json.JSONDecodeError:
                continue

        return text

    @staticmethod
    def _normalize_payload(
        payload: Any,
        response_model: type[BaseModel] | None,
        messages: list[Message],
    ) -> Any:
        if response_model is None:
            return payload

        if isinstance(payload, list):
            field_names = list(response_model.model_fields.keys())
            if len(field_names) == 1:
                payload = {field_names[0]: payload}

        if (
            response_model.__name__ == "ExtractedEntities"
            and isinstance(payload, dict)
            and isinstance(payload.get("extracted_entities"), list)
        ):
            type_map = CompatOpenAIGenericClient._extract_entity_type_map(messages)
            normalized_entities = []
            for item in payload["extracted_entities"]:
                if not isinstance(item, dict):
                    normalized_entities.append(item)
                    continue

                normalized = dict(item)
                if "name" not in normalized and "entity_name" in normalized:
                    normalized["name"] = normalized.pop("entity_name")

                if "entity_type_id" not in normalized and "entity_type_name" in normalized:
                    normalized["entity_type_id"] = type_map.get(str(normalized["entity_type_name"]), 0)

                normalized_entities.append(normalized)

            payload["extracted_entities"] = normalized_entities

        return payload

    @staticmethod
    def _extract_entity_type_map(messages: list[Message]) -> dict[str, int]:
        pattern = re.compile(r"<ENTITY TYPES>\s*(.*?)\s*</ENTITY TYPES>", re.DOTALL)
        for message in messages:
            match = pattern.search(message.content)
            if not match:
                continue
            block = match.group(1).strip()
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue

            mapping = {}
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("entity_type_name")
                    entity_type_id = item.get("entity_type_id")
                    if isinstance(name, str) and isinstance(entity_type_id, int):
                        mapping[name] = entity_type_id
            return mapping

        return {}

    async def _generate_response(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        model_size: ModelSize = ModelSize.medium,
    ) -> dict[str, Any]:
        openai_messages = []
        for message in messages:
            message.content = self._clean_input(message.content)
            if message.role in {"user", "system"}:
                openai_messages.append({"role": message.role, "content": message.content})

        try:
            response_format: dict[str, Any] = {"type": "json_object"}
            if response_model is not None:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": getattr(response_model, "__name__", "structured_response"),
                        "schema": response_model.model_json_schema(),
                    },
                }

            response = await self.client.chat.completions.create(
                model=self.model or DEFAULT_MODEL,
                messages=openai_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format=response_format,  # type: ignore[arg-type]
            )

            raw_content = response.choices[0].message.content or ""
            normalized = self._extract_json_text(raw_content)
            if not normalized:
                raise json.JSONDecodeError("Empty content", raw_content, 0)

            parsed = json.loads(normalized)
            return self._normalize_payload(parsed, response_model, messages)
        except openai.RateLimitError as exc:
            raise RateLimitError from exc
        except Exception as exc:
            logger.error("Error in generating LLM response: %s", exc)
            raise
