import logging
import json
from datetime import date, datetime, timezone
from typing import Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from graphiti_core.edges import EntityEdge
from graphiti_core.embedder.openai import OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.nodes import EntityNode, EpisodeType
from graphiti_core.utils import bulk_utils as graphiti_bulk_utils

from engine.compat_embedder import CompatOpenAIEmbedder
from config import Settings
from engine.compat_openai_client import CompatOpenAIGenericClient
from engine.data_ingestion import normalize_episode_body, normalize_episode_type

_GRAPHITI_SAVE_PATCHED = False
_ORIGINAL_ADD_NODES_AND_EDGES_BULK_TX = graphiti_bulk_utils.add_nodes_and_edges_bulk_tx
_ORIGINAL_ENTITY_NODE_SAVE = EntityNode.save
_ORIGINAL_ENTITY_EDGE_SAVE = EntityEdge.save


def _is_property_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def _to_json_safe(value: Any) -> Any:
    if value is None or _is_property_scalar(value):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(item) for item in value]
    return str(value)


def _sanitize_attribute_value(value: Any) -> Any:
    if value is None or _is_property_scalar(value):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        raw_items = list(value)
        if any(
            item is not None
            and not _is_property_scalar(item)
            and not isinstance(item, (datetime, date))
            for item in raw_items
        ):
            return json.dumps(_to_json_safe(raw_items), ensure_ascii=False, sort_keys=True)

        items = [_sanitize_attribute_value(item) for item in raw_items]
        if not items:
            return []
        if all(_is_property_scalar(item) for item in items) and len({type(item) for item in items}) == 1:
            return items
        return json.dumps(_to_json_safe(raw_items), ensure_ascii=False, sort_keys=True)
    if isinstance(value, dict):
        return json.dumps(_to_json_safe(value), ensure_ascii=False, sort_keys=True)
    return str(value)


def sanitize_graph_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    return {
        str(key): _sanitize_attribute_value(value)
        for key, value in (attributes or {}).items()
    }


async def _patched_add_nodes_and_edges_bulk_tx(
    tx,
    episodic_nodes,
    episodic_edges,
    entity_nodes,
    entity_edges,
    embedder,
    driver,
):
    for node in entity_nodes:
        node.attributes = sanitize_graph_attributes(getattr(node, "attributes", None))
    for edge in entity_edges:
        edge.attributes = sanitize_graph_attributes(getattr(edge, "attributes", None))
    return await _ORIGINAL_ADD_NODES_AND_EDGES_BULK_TX(
        tx,
        episodic_nodes,
        episodic_edges,
        entity_nodes,
        entity_edges,
        embedder,
        driver,
    )


async def _patched_entity_node_save(self, driver):
    self.attributes = sanitize_graph_attributes(getattr(self, "attributes", None))
    return await _ORIGINAL_ENTITY_NODE_SAVE(self, driver)


async def _patched_entity_edge_save(self, driver):
    self.attributes = sanitize_graph_attributes(getattr(self, "attributes", None))
    return await _ORIGINAL_ENTITY_EDGE_SAVE(self, driver)


def patch_graphiti_save_paths() -> None:
    global _GRAPHITI_SAVE_PATCHED
    if _GRAPHITI_SAVE_PATCHED:
        return

    graphiti_bulk_utils.add_nodes_and_edges_bulk_tx = _patched_add_nodes_and_edges_bulk_tx
    EntityNode.save = _patched_entity_node_save
    EntityEdge.save = _patched_entity_edge_save
    _GRAPHITI_SAVE_PATCHED = True


def create_graphiti(s: Settings) -> Graphiti:
    patch_graphiti_save_paths()

    if s.graph_db == "neo4j":
        driver = Neo4jDriver(uri=s.neo4j_uri, user=s.neo4j_user, password=s.neo4j_password)
    else:
        driver = FalkorDriver(host=s.falkordb_host, port=s.falkordb_port)

    llm_config = LLMConfig(
        api_key=s.llm_api_key,
        model=s.llm_model,
        base_url=s.llm_base_url,
        small_model=s.llm_small_model,
    )
    llm_client = CompatOpenAIGenericClient(llm_config)

    embed_config = OpenAIEmbedderConfig(
        api_key=s.embedder_api_key or s.llm_api_key,
        base_url=s.embedder_base_url or s.llm_base_url,
        embedding_model=s.embedder_model,
    )
    embedder = CompatOpenAIEmbedder(embed_config)

    reranker = OpenAIRerankerClient(
        config=LLMConfig(
            api_key=s.llm_api_key,
            model=s.llm_small_model or s.llm_model,
            base_url=s.llm_base_url,
        )
    )

    return Graphiti(graph_driver=driver, llm_client=llm_client, embedder=embedder, cross_encoder=reranker)


patch_graphiti_save_paths()


async def add_single_episode(
    graphiti: Graphiti,
    graph_id: str,
    data: str,
    ep_type: str = "text",
    source_description: str = "user",
    created_at: datetime | None = None,
    entity_types: dict[str, type[BaseModel]] | None = None,
    edge_types: dict[str, type[BaseModel]] | None = None,
    edge_type_map: dict[tuple[str, str], list[str]] | None = None,
) -> tuple[str, str]:
    """Add a single episode to the graph, return (uuid, name)."""
    ref_time = created_at or datetime.now(timezone.utc)
    name = f"ep_{graph_id}_{ref_time.timestamp()}"
    source = normalize_episode_type(ep_type)
    episode_body = normalize_episode_body(data, ep_type)
    result = await graphiti.add_episode(
        name=name,
        episode_body=episode_body,
        source_description=source_description,
        reference_time=ref_time,
        source=source,
        group_id=graph_id,
        entity_types=entity_types,
        edge_types=edge_types,
        edge_type_map=edge_type_map,
    )
    return result.episode.uuid, name


async def add_messages_to_graph(
    graphiti: Graphiti,
    session_id: str,
    messages: list[dict[str, Any]],
) -> None:
    """Add a list of {role, content} messages to the knowledge graph."""
    logger.info("Adding %d messages to graph for session %s", len(messages), session_id)
    try:
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            episode_body = f"{role}: {content}"
            await graphiti.add_episode(
                name=f"msg_{session_id}_{datetime.now(timezone.utc).timestamp()}",
                episode_body=episode_body,
                source_description="conversation",
                reference_time=datetime.now(timezone.utc),
                source=EpisodeType.message,
                group_id=session_id,
            )
        logger.info("Successfully added messages for session %s", session_id)
    except Exception as e:
        logger.error("Failed to add messages for session %s: %s", session_id, e, exc_info=True)


async def search_graph(
    graphiti: Graphiti,
    session_id: str,
    query: str,
    num_results: int = 10,
) -> list[dict[str, Any]]:
    """Search the knowledge graph for a session, return serializable facts."""
    if not query or not query.strip():
        # No query: use a broad query to get recent EntityEdge facts
        query = "recent facts"
    edges = await graphiti.search(
        query=query,
        group_ids=[session_id],
        num_results=num_results,
    )
    return [
        {
            "fact": e.fact,
            "uuid": e.uuid,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in edges
    ]


async def clear_session_graph(graphiti: Graphiti, session_id: str) -> None:
    """Delete all episodes for a session group."""
    episodes = await graphiti.retrieve_episodes(
        reference_time=datetime.now(timezone.utc),
        last_n=10000,
        group_ids=[session_id],
    )
    for ep in episodes:
        await graphiti.remove_episode(ep.uuid)


async def get_fact_by_uuid(graphiti: Graphiti, uuid: str) -> dict[str, Any] | None:
    """Get a single fact (EntityEdge) by UUID."""
    try:
        edge = await EntityEdge.get_by_uuid(graphiti.driver, uuid)
        return {
            "uuid": edge.uuid,
            "fact": edge.fact,
            "created_at": edge.created_at.isoformat() if edge.created_at else None,
        }
    except Exception:
        return None


async def delete_fact_by_uuid(graphiti: Graphiti, uuid: str) -> bool:
    """Delete a single fact (EntityEdge) by UUID."""
    try:
        edge = await EntityEdge.get_by_uuid(graphiti.driver, uuid)
        await edge.delete(graphiti.driver)
        return True
    except Exception:
        return False


async def delete_episode_by_uuid(graphiti: Graphiti, uuid: str) -> bool:
    """Delete a single episode by UUID.

    Returns True if the episode was found and removed, False otherwise.
    Uses graphiti.remove_episode for full cascade cleanup (edges, entities).
    """
    try:
        await graphiti.remove_episode(uuid)
        return True
    except Exception:
        logger.exception("Failed to delete episode %s", uuid)
        return False
