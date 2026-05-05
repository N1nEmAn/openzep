import unittest

from graphiti_core.prompts.extract_edges import ExtractedEdges
from graphiti_core.prompts.extract_nodes import ExtractedEntities

from engine.compat_openai_client import CompatOpenAIGenericClient


class CompatOpenAIClientTests(unittest.TestCase):
    def test_builds_strict_openai_schema_for_extracted_entities(self):
        schema = CompatOpenAIGenericClient._openai_strict_schema(
            ExtractedEntities.model_json_schema(),
        )

        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(schema["required"], ["extracted_entities"])

        entity_schema = schema["$defs"]["ExtractedEntity"]
        self.assertIs(entity_schema["additionalProperties"], False)
        self.assertEqual(
            entity_schema["required"],
            ["name", "entity_type_id", "episode_indices"],
        )

    def test_wraps_single_edge_payload_for_extracted_edges(self):
        payload = {
            "source_entity_name": "Alice",
            "target_entity_name": "Bob",
            "relation_type": "KNOWS",
            "fact": "Alice knows Bob",
            "valid_at": None,
            "invalid_at": None,
        }

        normalized = CompatOpenAIGenericClient._normalize_payload(
            payload,
            ExtractedEdges,
            [],
        )

        self.assertEqual(list(normalized.keys()), ["edges"])
        self.assertEqual(len(normalized["edges"]), 1)
        self.assertEqual(normalized["edges"][0]["relation_type"], "KNOWS")

    def test_wraps_nested_single_edge_payload_for_extracted_edges(self):
        payload = {
            "edges": {
                "source_entity_name": "Alice",
                "target_entity_name": "Bob",
                "relation_type": "KNOWS",
                "fact": "Alice knows Bob",
                "valid_at": None,
                "invalid_at": None,
            }
        }

        normalized = CompatOpenAIGenericClient._normalize_payload(
            payload,
            ExtractedEdges,
            [],
        )

        self.assertEqual(len(normalized["edges"]), 1)
        self.assertEqual(normalized["edges"][0]["fact"], "Alice knows Bob")

    def test_wraps_entity_list_and_maps_entity_type_names(self):
        payload = [
            {
                "entity_name": "Alice",
                "entity_type_name": "Person",
            }
        ]
        messages = [
            type(
                "Message",
                (),
                {
                    "content": """
<ENTITY TYPES>
[{"entity_type_name":"Person","entity_type_id":7}]
</ENTITY TYPES>
""",
                },
            )()
        ]

        normalized = CompatOpenAIGenericClient._normalize_payload(
            payload,
            ExtractedEntities,
            messages,
        )

        self.assertEqual(len(normalized["extracted_entities"]), 1)
        self.assertEqual(normalized["extracted_entities"][0]["name"], "Alice")
        self.assertEqual(normalized["extracted_entities"][0]["entity_type_id"], 7)


if __name__ == "__main__":
    unittest.main()
