import pytest

pytest.importorskip("fastapi")
pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from pydantic import ValidationError

from api.generator import GeneratorError
from api.kg import (
    KG_NODE_PROPERTIES,
    KG_RELATIONSHIP_PATTERNS,
    KG_RELATIONSHIP_TYPES,
    KG_SCHEMA,
    KGExecutionError,
    UnsupportedCypherError,
    extract_graph_elements,
    serialize_records,
    validate_read_only_cypher,
)
from api.models import KGRequest, KGResponse
from api.seed_neo4j import (
    ALLOWED_RELATIONSHIP_PATTERNS,
    ALLOWED_RELATIONSHIP_TYPES,
    NODE_GROUPS,
    build_node_label_index,
    load_seed_graph,
    validate_relationship,
)


def seed_node_properties():
    graph = load_seed_graph()
    properties = {}
    for group, label in NODE_GROUPS.items():
        keys = set()
        for row in graph[group]:
            keys.update(str(key) for key in row)
        properties[label] = frozenset(keys)
    return properties


def seed_relationship_types():
    graph = load_seed_graph()
    return frozenset(str(row["type"]) for row in graph["relationships"])


def seed_relationship_patterns():
    graph = load_seed_graph()
    node_labels = build_node_label_index(graph)
    return frozenset(
        (node_labels[str(row["source"])], str(row["type"]), node_labels[str(row["target"])])
        for row in graph["relationships"]
    )


def test_kg_request_model_validation():
    assert KGRequest(question="ما المادة المرتبطة بالإجازة؟").question

    with pytest.raises(ValidationError):
        KGRequest(question="x")


def test_kg_schema_matches_seed_graph_labels_properties_and_relationships():
    expected_properties = seed_node_properties()
    expected_relationship_types = seed_relationship_types()
    expected_relationship_patterns = seed_relationship_patterns()

    assert KG_NODE_PROPERTIES == expected_properties
    assert KG_RELATIONSHIP_TYPES == expected_relationship_types
    assert KG_RELATIONSHIP_PATTERNS == expected_relationship_patterns

    for label, properties in expected_properties.items():
        property_list = ", ".join(sorted(properties))
        assert f"- {label} {{{property_list}}}" in KG_SCHEMA

    for source_label, rel_type, target_label in expected_relationship_patterns:
        assert f"(:{source_label})-[:{rel_type}]->(:{target_label})" in KG_SCHEMA

    for obsolete_name in (
        "BELONGS_TO",
        "RELATES_TO",
        "REFERENCES",
        "IMPLEMENTS",
        "Article.text",
        "Article.source_page",
        "Law.title",
        "Law.status",
    ):
        assert obsolete_name not in KG_SCHEMA


def test_seed_relationship_ids_exist_and_directions_match_schema():
    graph = load_seed_graph()
    node_labels = build_node_label_index(graph)

    for row in graph["relationships"]:
        assert row["source"] in node_labels
        assert row["target"] in node_labels

    assert seed_relationship_patterns() == KG_RELATIONSHIP_PATTERNS
    assert seed_relationship_patterns() == ALLOWED_RELATIONSHIP_PATTERNS


def test_seed_relationship_validation_infers_labels_and_accepts_seed_types():
    graph = load_seed_graph()
    node_labels = build_node_label_index(graph)
    accepted_types = set()

    for index, row in enumerate(graph["relationships"], start=1):
        assert "source_label" not in row
        assert "target_label" not in row

        relationship = validate_relationship(row, index, node_labels)

        assert relationship["source_label"] == node_labels[row["source"]]
        assert relationship["target_label"] == node_labels[row["target"]]
        assert relationship["source_id"] == row["source"]
        assert relationship["target_id"] == row["target"]
        assert relationship["properties"] == row["properties"]
        accepted_types.add(relationship["type"])

    assert frozenset(accepted_types) == seed_relationship_types()
    assert ALLOWED_RELATIONSHIP_TYPES == seed_relationship_types()


def test_read_only_cypher_acceptance():
    cypher = """
    MATCH (law:Law)-[:HAS_ARTICLE]->(article:Article)-[:HAS_TOPIC]->(topic:Topic)
    WHERE article.summary CONTAINS $term
    RETURN law.name, article.title, article.summary, topic.name
    ORDER BY article.number
    LIMIT $limit;
    """

    validated = validate_read_only_cypher(cypher, max_chars=4000)

    assert validated.startswith("MATCH")
    assert validated.endswith("LIMIT $limit")


@pytest.mark.parametrize(
    "cypher",
    [
        "MATCH (article:Article)-[:RELATES_TO]->(topic:Topic) RETURN article, topic",
        "MATCH (article:Article)-[:REFERENCES]->(other:Article) RETURN article, other",
        "MATCH (article:Article)-[:HAS_TOPIC]->(unknown:Concept) RETURN article, unknown",
        "MATCH (article:Article) RETURN article.text LIMIT $limit",
        "MATCH (law:Law) RETURN law.title LIMIT $limit",
    ],
)
def test_schema_invalid_read_only_cypher_rejection(cypher):
    with pytest.raises(UnsupportedCypherError):
        validate_read_only_cypher(cypher, max_chars=4000)


@pytest.mark.parametrize(
    "cypher",
    [
        "CREATE (:Law {id: 'x'}) RETURN 1",
        "MERGE (n:Law {id: 'x'}) RETURN n",
        "MATCH (n) DELETE n RETURN n",
        "MATCH (n) DETACH DELETE n RETURN n",
        "MATCH (n) SET n.title = 'x' RETURN n",
        "MATCH (n) REMOVE n.title RETURN n",
        "DROP INDEX law_id_unique RETURN 1",
        "CALL db.labels() YIELD label RETURN label",
        "LOAD CSV FROM 'file:///x.csv' AS row RETURN row",
        "FOREACH (x IN [] | CREATE (:Law)) RETURN 1",
        "GRANT ROLE reader TO user RETURN 1",
        "DENY MATCH {*} ON GRAPH neo4j TO user RETURN 1",
        "REVOKE ROLE reader FROM user RETURN 1",
    ],
)
def test_destructive_cypher_rejection(cypher):
    with pytest.raises(UnsupportedCypherError):
        validate_read_only_cypher(cypher, max_chars=4000)


def test_multiple_statement_rejection():
    with pytest.raises(UnsupportedCypherError):
        validate_read_only_cypher("MATCH (n) RETURN n; MATCH (m) RETURN m", max_chars=4000)


def test_response_serialization_extracts_graph_elements():
    records = serialize_records(
        [
            {
                "article": {
                    "id": "article-23",
                    "labels": ["Article"],
                    "properties": {"number": "23"},
                },
                "relationship": {
                    "id": "rel-1",
                    "type": "HAS_ARTICLE",
                    "source": "law-1",
                    "target": "article-23",
                    "properties": {},
                },
            }
        ]
    )
    nodes, relationships = extract_graph_elements(records)

    response = KGResponse(
        answer="نتيجة تجريبية",
        generated_cypher="MATCH (n) RETURN n",
        parameters={"limit": 25},
        records=records,
        nodes=nodes,
        relationships=relationships,
        row_count=len(records),
        disclaimer="تنبيه",
    )

    assert response.row_count == 1
    assert response.nodes[0].id == "article-23"
    assert response.relationships[0].type == "HAS_ARTICLE"


def test_kg_query_success_with_external_operations_monkeypatched(client, monkeypatch):
    def fake_query(question, settings):
        return KGResponse(
            answer=f"إجابة عن: {question}",
            generated_cypher="MATCH (n) RETURN n LIMIT $limit",
            parameters={"limit": 25},
            records=[{"n": {"id": "n1", "labels": ["Topic"], "properties": {"name": "عمل"}}}],
            nodes=[],
            relationships=[],
            row_count=1,
            disclaimer="تنبيه",
        )

    monkeypatch.setattr("api.main.query_knowledge_graph", fake_query)

    response = client.post("/kg/query", json={"question": "ما موضوعات قانون العمل؟"})

    assert response.status_code == 200
    assert response.json()["row_count"] == 1
    assert response.json()["generated_cypher"].startswith("MATCH")


def test_kg_query_maps_generator_error_to_503(client, monkeypatch):
    def fake_query(question, settings):
        raise GeneratorError("provider unavailable")

    monkeypatch.setattr("api.main.query_knowledge_graph", fake_query)

    response = client.post("/kg/query", json={"question": "ما المواد؟"})

    assert response.status_code == 503
    assert "LLM provider unavailable" in response.json()["detail"]


def test_kg_query_maps_unsupported_cypher_to_400(client, monkeypatch):
    def fake_query(question, settings):
        raise UnsupportedCypherError("unsafe")

    monkeypatch.setattr("api.main.query_knowledge_graph", fake_query)

    response = client.post("/kg/query", json={"question": "ما المواد؟"})

    assert response.status_code == 400
    assert response.json()["detail"] == "unsafe"


def test_kg_query_maps_execution_error_to_503(client, monkeypatch):
    def fake_query(question, settings):
        raise KGExecutionError("neo4j failed")

    monkeypatch.setattr("api.main.query_knowledge_graph", fake_query)

    response = client.post("/kg/query", json={"question": "ما المواد؟"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Neo4j unavailable or query failed."


def test_readyz_includes_neo4j(client):
    response = client.get("/readyz")

    assert response.status_code == 200
    assert "neo4j" in response.json()["dependencies"]


def test_healthz_does_not_require_neo4j(client, monkeypatch):
    def fail_neo4j(settings):
        raise AssertionError("healthz should not contact Neo4j")

    monkeypatch.setattr("api.main.check_neo4j_ready", fail_neo4j)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
