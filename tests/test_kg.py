import sys
import types

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
    build_cypher_prompt,
    build_schema_context,
    execute_cypher,
    extract_cypher,
    extract_graph_elements,
    query_knowledge_graph,
    serialize_neo4j_value,
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


class FakeSettings:
    neo4j_uri = "bolt://neo4j:7687"
    neo4j_user = "neo4j"
    neo4j_password = "secret"
    neo4j_database = "neo4j"
    kg_timeout_seconds = 7
    kg_max_cypher_chars = 4000
    kg_query_limit = 5


class FakeNode(dict):
    def __init__(self, element_id, labels, properties):
        super().__init__(properties)
        self.element_id = element_id
        self.labels = set(labels)


class FakeRelationship(dict):
    def __init__(self, element_id, rel_type, source, target, properties):
        super().__init__(properties)
        self.element_id = element_id
        self.type = rel_type
        self.start_node = source
        self.end_node = target


class FakePath:
    def __init__(self, nodes, relationships):
        self.nodes = nodes
        self.relationships = relationships


class FakeRecord:
    def __init__(self, data):
        self._data = data

    def items(self):
        return self._data.items()

    def data(self):
        raise AssertionError("record.data() must not be used for graph values")


def install_fake_neo4j(monkeypatch, records=(), error=None, capture=None):
    capture = capture if capture is not None else {}

    class FakeQuery:
        def __init__(self, text, timeout=None):
            self.text = text
            self.timeout = timeout

    class FakeSession:
        def __init__(self, database=None, default_access_mode=None):
            capture["database"] = database
            capture["default_access_mode"] = default_access_mode

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def run(self, query, parameters=None):
            if error == "run":
                raise RuntimeError("boom")
            capture["query"] = query.text
            capture["timeout"] = query.timeout
            capture["parameters"] = parameters
            return records

    class FakeDriver:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def session(self, database=None, default_access_mode=None):
            return FakeSession(database=database, default_access_mode=default_access_mode)

    class FakeGraphDatabase:
        @staticmethod
        def driver(uri, auth=None):
            if error == "driver":
                raise RuntimeError("boom")
            capture["uri"] = uri
            capture["auth"] = auth
            return FakeDriver()

    fake_module = types.SimpleNamespace(
        READ_ACCESS="READ",
        GraphDatabase=FakeGraphDatabase,
        Query=FakeQuery,
    )
    monkeypatch.setitem(sys.modules, "neo4j", fake_module)
    return capture


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


def test_schema_context_is_deterministic_and_schema_bounded():
    context = build_schema_context()

    assert context == build_schema_context()
    assert "Node labels and properties:" in context
    assert "Relationship types:" in context
    assert "Relationship directions:" in context
    assert "- Article {id, jurisdiction, law_id, number, reference, source_name, source_type, summary, title}" in context
    assert "- HAS_TOPIC" in context
    assert "- (:Article)-[:HAS_TOPIC]->(:Topic)" in context
    assert "RELATES_TO" not in context
    assert "Article.text" not in context


def test_cypher_prompt_contains_schema_question_and_output_rules():
    question = "ما المواد المرتبطة بالإجازات؟"
    prompt = build_cypher_prompt(question)

    assert question in prompt
    assert build_schema_context() in prompt
    assert "Return exactly one Neo4j Cypher query." in prompt
    assert "Use only the labels, properties, relationship types, and relationship directions" in prompt
    assert "Do not invent exact property values" in prompt
    assert "traverse the Law node without adding an inferred exact name property filter" in prompt
    assert "WHERE ... CONTAINS" in prompt
    assert "bind the relationship to a variable" in prompt
    assert "RETURN a, r, t" in prompt
    assert "LIMIT $limit" in prompt
    assert "Do not include Markdown fences" in prompt


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


def test_extract_cypher_accepts_raw_and_fenced_queries():
    raw = "MATCH (article:Article) RETURN article LIMIT $limit"
    fenced = f"```cypher\n{raw}\n```"

    assert extract_cypher(raw) == raw
    assert extract_cypher(fenced) == raw


@pytest.mark.parametrize(
    "llm_output",
    [
        "",
        "```cypher\nMATCH (n:Article) RETURN n LIMIT $limit\n```\nextra",
        "```cypher\nMATCH (n:Article) RETURN n LIMIT $limit\n```\n```cypher\nMATCH (m:Topic) RETURN m LIMIT $limit\n```",
        "MATCH (n:Article) RETURN n; MATCH (m:Topic) RETURN m",
        "Here is the query: MATCH (n:Article) RETURN n LIMIT $limit",
        "```cypher\n\n```",
    ],
)
def test_extract_cypher_rejects_empty_explanatory_or_multiple_queries(llm_output):
    with pytest.raises(UnsupportedCypherError):
        extract_cypher(llm_output)


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


def test_read_only_cypher_requires_limit_unless_clearly_bounded():
    with pytest.raises(UnsupportedCypherError):
        validate_read_only_cypher("MATCH (article:Article) RETURN article", max_chars=4000)

    bounded = "MATCH (article:Article {id: $id}) RETURN article"
    assert validate_read_only_cypher(bounded, max_chars=4000) == bounded


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


def test_neo4j_value_serialization_handles_nodes_relationships_paths_and_special_values():
    law = FakeNode("law-1", ["Law"], {"name": "قانون العمل"})
    article = FakeNode("article-23", ["Article"], {"number": "23"})
    relationship = FakeRelationship("rel-1", "HAS_ARTICLE", law, article, {"reason": "test"})
    path = FakePath([law, article], [relationship])

    class FakeTemporal:
        def iso_format(self):
            return "2026-07-11T12:00:00"

    class FakePoint:
        srid = 4326
        longitude = 35.9
        latitude = 31.9

    payload = serialize_neo4j_value(
        {
            "node": article,
            "relationship": relationship,
            "path": path,
            "temporal": FakeTemporal(),
            "point": FakePoint(),
            "items": (article, b"text"),
        }
    )

    assert payload["node"]["id"] == "article-23"
    assert payload["node"]["labels"] == ["Article"]
    assert payload["relationship"]["type"] == "HAS_ARTICLE"
    assert payload["relationship"]["source"] == "law-1"
    assert payload["relationship"]["target"] == "article-23"
    assert payload["path"]["nodes"][0]["id"] == "law-1"
    assert payload["temporal"] == "2026-07-11T12:00:00"
    assert payload["point"]["srid"] == 4326
    assert payload["items"][1] == "text"


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


def test_execute_cypher_serializes_raw_record_items_and_preserves_graph_metadata(monkeypatch):
    law = FakeNode("law-1", ["Law"], {"id": "jordan_labor_law_8_1996", "name": "قانون العمل"})
    article = FakeNode("article-23", ["Article"], {"id": "labor_law_article_023", "number": "23"})
    relationship = FakeRelationship("rel-1", "HAS_ARTICLE", law, article, {"reason": "included"})
    path = FakePath([law, article], [relationship])
    install_fake_neo4j(
        monkeypatch,
        records=[
            FakeRecord(
                {
                    "article": article,
                    "relationship": relationship,
                    "path": path,
                    "nested": [{"duplicate_article": article}, [relationship]],
                }
            )
        ],
    )

    records = execute_cypher(
        "MATCH (law:Law)-[r:HAS_ARTICLE]->(article:Article) RETURN law, r, article LIMIT $limit",
        {"limit": 5},
        FakeSettings(),
    )

    assert records[0]["article"] == {
        "id": "article-23",
        "labels": ["Article"],
        "properties": {"id": "labor_law_article_023", "number": "23"},
    }
    assert records[0]["relationship"] == {
        "id": "rel-1",
        "type": "HAS_ARTICLE",
        "source": "law-1",
        "target": "article-23",
        "properties": {"reason": "included"},
    }
    assert records[0]["path"]["nodes"][0]["id"] == "law-1"
    assert records[0]["path"]["relationships"][0]["id"] == "rel-1"

    nodes, relationships = extract_graph_elements(records)

    assert sorted(node.id for node in nodes) == ["article-23", "law-1"]
    assert [relationship.id for relationship in relationships] == ["rel-1"]


def test_execute_cypher_empty_results(monkeypatch):
    capture = install_fake_neo4j(monkeypatch, records=[])

    records = execute_cypher("MATCH (article:Article) RETURN article LIMIT $limit", {"limit": 5}, FakeSettings())

    assert records == []
    assert capture["database"] == "neo4j"
    assert capture["default_access_mode"] == "READ"
    assert capture["parameters"] == {"limit": 5}
    assert capture["timeout"] == 7


def test_execute_cypher_failure_raises_kg_execution_error(monkeypatch):
    install_fake_neo4j(monkeypatch, error="run")

    with pytest.raises(KGExecutionError):
        execute_cypher("MATCH (article:Article) RETURN article LIMIT $limit", {"limit": 5}, FakeSettings())


def test_query_knowledge_graph_orchestration_with_mocked_llm_and_neo4j(monkeypatch):
    law = FakeNode("law-1", ["Law"], {"id": "jordan_labor_law_8_1996", "name": "قانون العمل"})
    article = FakeNode("article-23", ["Article"], {"id": "labor_law_article_023", "number": "23"})
    relationship = FakeRelationship("rel-1", "HAS_ARTICLE", law, article, {})
    capture = install_fake_neo4j(
        monkeypatch,
        records=[FakeRecord({"law": law, "article": article, "relationship": relationship})],
    )
    generated = "MATCH (law:Law)-[:HAS_ARTICLE]->(article:Article) RETURN law, article LIMIT $limit"
    prompt_capture = {}

    def fake_generate(system_prompt, user_prompt, settings):
        prompt_capture["system"] = system_prompt
        prompt_capture["user"] = user_prompt
        return generated

    monkeypatch.setattr("api.kg.generate_structured_text", fake_generate)

    response = query_knowledge_graph("ما المادة 23؟", FakeSettings())

    assert response.generated_cypher == generated
    assert response.parameters == {"limit": 5}
    assert response.row_count == 1
    assert response.nodes[0].id == "law-1"
    assert response.relationships[0].type == "HAS_ARTICLE"
    assert capture["parameters"] == {"limit": 5}
    assert "ما المادة 23؟" in prompt_capture["user"]
    assert "Jordanian legal knowledge graph schema" in prompt_capture["user"]


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
