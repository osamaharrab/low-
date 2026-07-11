from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.settings import get_settings


SEED_PATH = Path(__file__).with_name("seed_graph.json")
NODE_GROUPS = {
    "laws": "Law",
    "articles": "Article",
    "topics": "Topic",
    "regulations": "Regulation",
}
ALLOWED_LABELS = set(NODE_GROUPS.values())
ALLOWED_RELATIONSHIP_TYPES = {
    "HAS_ARTICLE",
    "HAS_TOPIC",
    "REFERS_TO",
    "RELATED_TO",
}
ALLOWED_RELATIONSHIP_PATTERNS = {
    ("Law", "HAS_ARTICLE", "Article"),
    ("Article", "HAS_TOPIC", "Topic"),
    ("Article", "REFERS_TO", "Article"),
    ("Article", "RELATED_TO", "Article"),
}


def load_seed_graph(path: Path = SEED_PATH) -> dict[str, list[dict[str, Any]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object.")

    graph: dict[str, list[dict[str, Any]]] = {}
    for key in [*NODE_GROUPS, "relationships"]:
        rows = data.get(key, [])
        if not isinstance(rows, list):
            raise SystemExit(f"{path}:{key} must be a JSON array.")
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise SystemExit(f"{path}:{key}[{index}] must be an object.")
        graph[key] = rows

    # TODO(KG data owner): Populate api/seed_graph.json with reviewed Jordanian
    # legal laws, articles, topics, regulations, and relationship rows.
    return graph


def require_id(row: dict[str, Any], label: str, index: int) -> str:
    node_id = str(row.get("id") or "").strip()
    if not node_id:
        raise SystemExit(f"{label} row {index} is missing id.")
    return node_id


def create_constraints(session) -> None:
    for label in ("Law", "Article", "Topic", "Regulation"):
        session.run(
            f"CREATE CONSTRAINT {label.lower()}_id_unique IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
        )


def merge_node(tx, label: str, row: dict[str, Any]) -> None:
    properties = {str(key): value for key, value in row.items()}
    tx.run(
        f"MERGE (n:{label} {{id: $id}}) SET n += $properties",
        id=str(properties["id"]),
        properties=properties,
    )


def relationship_value(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = str(row.get(name) or "").strip()
        if value:
            return value
    return ""


def build_node_label_index(graph: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    node_labels: dict[str, str] = {}
    for group, label in NODE_GROUPS.items():
        for index, row in enumerate(graph[group], start=1):
            node_id = require_id(row, label, index)
            if node_id in node_labels:
                raise SystemExit(f"Duplicate node id across seed graph: {node_id}")
            node_labels[node_id] = label
    return node_labels


def validate_relationship(row: dict[str, Any], index: int, node_labels: dict[str, str]) -> dict[str, Any]:
    rel_type = relationship_value(row, "type", "relationship_type")
    if rel_type not in ALLOWED_RELATIONSHIP_TYPES:
        raise SystemExit(f"Relationship row {index} has unsupported type: {rel_type or '<missing>'}")

    source_id = relationship_value(row, "source_id", "from_id", "source")
    target_id = relationship_value(row, "target_id", "to_id", "target")
    if not source_id or not target_id:
        raise SystemExit(f"Relationship row {index} must include source and target.")
    if source_id not in node_labels:
        raise SystemExit(f"Relationship row {index} has unknown source id: {source_id}")
    if target_id not in node_labels:
        raise SystemExit(f"Relationship row {index} has unknown target id: {target_id}")

    source_label = node_labels[source_id]
    target_label = node_labels[target_id]
    if (source_label, rel_type, target_label) not in ALLOWED_RELATIONSHIP_PATTERNS:
        raise SystemExit(
            f"Relationship row {index} has unsupported pattern: "
            f"(:{source_label})-[:{rel_type}]->(:{target_label})"
        )

    properties = row.get("properties") or {}
    if not isinstance(properties, dict):
        raise SystemExit(f"Relationship row {index} properties must be an object.")

    return {
        "type": rel_type,
        "source_label": source_label,
        "source_id": source_id,
        "target_label": target_label,
        "target_id": target_id,
        "properties": {str(key): value for key, value in properties.items()},
    }


def merge_relationship(tx, relationship: dict[str, Any]) -> None:
    tx.run(
        f"""
        MATCH (source:{relationship['source_label']} {{id: $source_id}})
        MATCH (target:{relationship['target_label']} {{id: $target_id}})
        MERGE (source)-[rel:{relationship['type']}]->(target)
        SET rel += $properties
        """,
        source_id=relationship["source_id"],
        target_id=relationship["target_id"],
        properties=relationship["properties"],
    )


def main() -> None:
    from neo4j import GraphDatabase

    settings = get_settings()
    graph = load_seed_graph()
    counts = {key: len(rows) for key, rows in graph.items()}
    node_labels = build_node_label_index(graph)

    # TODO(KG data owner): Keep this seeder idempotent as new legal entities are
    # added. Do not add delete/recreate behavior for reviewed graph data.
    with GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    ) as driver:
        with driver.session(database=settings.neo4j_database) as session:
            create_constraints(session)
            for group, label in NODE_GROUPS.items():
                for index, row in enumerate(graph[group], start=1):
                    require_id(row, label, index)
                    session.execute_write(merge_node, label, row)

            for index, row in enumerate(graph["relationships"], start=1):
                relationship = validate_relationship(row, index, node_labels)
                session.execute_write(merge_relationship, relationship)

    print(f"database: {settings.neo4j_database}")
    print(f"laws_loaded: {counts['laws']}")
    print(f"articles_loaded: {counts['articles']}")
    print(f"topics_loaded: {counts['topics']}")
    print(f"regulations_loaded: {counts['regulations']}")
    print(f"relationships_loaded: {counts['relationships']}")


if __name__ == "__main__":
    main()
