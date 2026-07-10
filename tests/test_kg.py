import pytest

pytest.importorskip("fastapi")
pytest.importorskip("pydantic")

from pydantic import ValidationError

from api.generator import GeneratorError
from api.kg import KGExecutionError, UnsupportedCypherError, extract_graph_elements, serialize_records, validate_read_only_cypher
from api.models import KGRequest, KGResponse


def test_kg_request_model_validation():
    assert KGRequest(question="ما المادة المرتبطة بالإجازة؟").question

    with pytest.raises(ValidationError):
        KGRequest(question="x")


def test_read_only_cypher_acceptance():
    cypher = """
    MATCH (law:Law)-[:HAS_ARTICLE]->(article:Article)
    WHERE article.number = $number
    RETURN law, article
    ORDER BY article.number
    LIMIT $limit;
    """

    validated = validate_read_only_cypher(cypher, max_chars=4000)

    assert validated.startswith("MATCH")
    assert validated.endswith("LIMIT $limit")


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
