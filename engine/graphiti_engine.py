import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from graphiti_core.edges import EntityEdge
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.nodes import EpisodeType

from config import Settings


def create_graphiti(s: Settings) -> Graphiti:
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
    llm_client = OpenAIGenericClient(llm_config)

    embed_config = OpenAIEmbedderConfig(
        api_key=s.embedder_api_key or s.llm_api_key,
        base_url=s.embedder_base_url or s.llm_base_url,
        embedding_model=s.embedder_model,
    )
    embedder = OpenAIEmbedder(embed_config)

    reranker = OpenAIRerankerClient(
        config=LLMConfig(
            api_key=s.llm_api_key,
            model=s.llm_small_model or s.llm_model,
            base_url=s.llm_base_url,
        )
    )

    return Graphiti(graph_driver=driver, llm_client=llm_client, embedder=embedder, cross_encoder=reranker)


async def add_single_episode(
    graphiti: Graphiti,
    graph_id: str,
    data: str,
    ep_type: str = "text",
    source_description: str = "user",
    created_at: datetime | None = None,
) -> str:
    """Add a single episode to the graph, return its name."""
    ref_time = created_at or datetime.now(timezone.utc)
    name = f"ep_{graph_id}_{ref_time.timestamp()}"
    try:
        source = EpisodeType(ep_type)
    except ValueError:
        source = EpisodeType.text
    await graphiti.add_episode(
        name=name,
        episode_body=data,
        source_description=source_description,
        reference_time=ref_time,
        source=source,
        group_id=graph_id,
    )
    return name


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
