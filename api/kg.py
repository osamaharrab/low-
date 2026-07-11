from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from typing import Any

from api.generator import generate_structured_text
from api.models import KGNode, KGRelationship, KGResponse
from api.settings import Settings


KG_DISCLAIMER = "هذا شرح أولي مبني على رسم معرفي تجريبي ولا يُعد استشارة قانونية ولا يغني عن مراجعة النص القانوني الرسمي أو محامٍ مختص."

KG_SCHEMA = """Jordanian legal knowledge graph schema:

Node labels and properties:
- Law {id, jurisdiction, name, number, source_type, year}
- Article {id, jurisdiction, law_id, number, reference, source_name, source_type, summary, title}
- Topic {description, id, name}
- Regulation {}

Relationship types:
- (:Law)-[:HAS_ARTICLE]->(:Article)
- (:Article)-[:HAS_TOPIC]->(:Topic)
- (:Article)-[:REFERS_TO]->(:Article)
- (:Article)-[:RELATED_TO]->(:Article)

Use only these labels, relationship types, and properties.
Prefer MATCH patterns that bind Law, Article, Topic, and Regulation nodes.
Always return useful node, relationship, and scalar fields for the answer.
Use LIMIT $limit unless the query already returns a clearly bounded result."""

KG_NODE_PROPERTIES = {
    "Law": frozenset({"id", "jurisdiction", "name", "number", "source_type", "year"}),
    "Article": frozenset(
        {"id", "jurisdiction", "law_id", "number", "reference", "source_name", "source_type", "summary", "title"}
    ),
    "Topic": frozenset({"description", "id", "name"}),
    "Regulation": frozenset(),
}
KG_RELATIONSHIP_TYPES = frozenset({"HAS_ARTICLE", "HAS_TOPIC", "REFERS_TO", "RELATED_TO"})
KG_RELATIONSHIP_PATTERNS = frozenset(
    {
        ("Law", "HAS_ARTICLE", "Article"),
        ("Article", "HAS_TOPIC", "Topic"),
        ("Article", "REFERS_TO", "Article"),
        ("Article", "RELATED_TO", "Article"),
    }
)

TEXT2CYPHER_SYSTEM_PROMPT = """You generate Neo4j Cypher for a Jordanian legal knowledge graph.
Return one read-only Cypher query only.
Do not include markdown fences, comments, explanations, prose, or multiple statements.
Use only the provided schema.
Use parameters instead of literal limits where possible, especially $limit.
Allowed clauses: MATCH, OPTIONAL MATCH, WHERE, RETURN, WITH, ORDER BY, LIMIT, UNION, UNWIND.
Never use CREATE, MERGE, DELETE, DETACH DELETE, SET, REMOVE, DROP, CALL, LOAD CSV, FOREACH, GRANT, DENY, or REVOKE."""

FENCED_BLOCK_RE = re.compile(r"```(?:cypher)?\s*\n(?P<body>.*?)\n```", flags=re.IGNORECASE | re.DOTALL)
FORBIDDEN_PATTERNS = (
    r"\bDETACH\s+DELETE\b",
    r"\bLOAD\s+CSV\b",
    r"\bCREATE\b",
    r"\bMERGE\b",
    r"\bDELETE\b",
    r"\bSET\b",
    r"\bREMOVE\b",
    r"\bDROP\b",
    r"\bCALL\b",
    r"\bFOREACH\b",
    r"\bGRANT\b",
    r"\bDENY\b",
    r"\bREVOKE\b",
)
READ_ONLY_START_RE = re.compile(r"^(MATCH|OPTIONAL\s+MATCH|WHERE|RETURN|WITH|UNWIND)\b", flags=re.IGNORECASE)
IDENTIFIER_RE = r"[A-Za-z_][A-Za-z0-9_]*"
NODE_PATTERN_RE = re.compile(r"\((?P<body>[^()\[\]]*)\)")
RELATIONSHIP_PATTERN_RE = re.compile(r"\[(?P<body>[^\[\]]*)\]")
PROPERTY_ACCESS_RE = re.compile(rf"(?<![$\w])(?P<variable>{IDENTIFIER_RE})\.(?P<property>{IDENTIFIER_RE})")
ALIAS_RE = re.compile(rf"\b(?P<source>{IDENTIFIER_RE})\s+AS\s+(?P<alias>{IDENTIFIER_RE})\b", flags=re.IGNORECASE)


class UnsupportedCypherError(ValueError):
    """Raised when generated Cypher is empty, unsafe, or outside the KG read-only subset."""


class KGExecutionError(RuntimeError):
    """Raised when Neo4j cannot execute an already validated KG query."""


def build_schema_context() -> str:
    """Return the schema text used to bound Text2Cypher generation."""
    # TODO(KG teammate): Replace this static context with the final course-aligned
    # schema text once the legal KG seed data and naming are finalized.
    return KG_SCHEMA.strip()


def build_cypher_prompt(question: str) -> str:
    """Build a schema-bounded Text2Cypher prompt for a natural-language question."""
    # TODO(KG teammate): Tune examples and few-shot guidance after the graph data
    # owner finalizes the Jordanian legal graph shape.
    return f"""Schema:
{build_schema_context()}

Question:
{question.strip()}

Return exactly one read-only Cypher query. No prose."""


def generate_cypher(question: str, settings: Settings) -> str:
    """Generate and extract one Cypher query using the configured LLM provider."""
    raw_text = generate_structured_text(
        TEXT2CYPHER_SYSTEM_PROMPT,
        build_cypher_prompt(question),
        settings,
    )
    return extract_cypher(raw_text)


def extract_cypher(text: str) -> str:
    """Extract a single Cypher query from model output."""
    # TODO(KG teammate): Tighten extraction rules against the final prompt format.
    candidate = (text or "").strip()
    if not candidate:
        return ""

    matches = list(FENCED_BLOCK_RE.finditer(candidate))
    if matches:
        if len(matches) != 1:
            raise UnsupportedCypherError("Expected one Cypher query, got multiple fenced blocks.")
        before = candidate[: matches[0].start()].strip()
        after = candidate[matches[0].end() :].strip()
        if before or after:
            raise UnsupportedCypherError("Model returned explanatory text around Cypher.")
        return matches[0].group("body").strip()

    return candidate


def _semicolon_positions_outside_strings(text: str) -> list[int]:
    positions: list[int] = []
    quote: str | None = None
    escaped = False

    for index, char in enumerate(text):
        if quote:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = None
            continue

        if char in {"'", '"'}:
            quote = char
            continue
        if char == ";":
            positions.append(index)

    return positions


def _mask_string_literals(text: str) -> str:
    chars: list[str] = []
    quote: str | None = None
    escaped = False

    for char in text:
        if quote:
            if escaped:
                escaped = False
                chars.append(" ")
                continue
            if char == "\\":
                escaped = True
                chars.append(" ")
                continue
            if char == quote:
                quote = None
                chars.append(char)
            else:
                chars.append(" ")
            continue

        if char in {"'", '"'}:
            quote = char
            chars.append(char)
            continue
        chars.append(char)

    return "".join(chars)


def _labels_from_node_body(body: str) -> list[str]:
    before_properties = body.split("{", 1)[0]
    return re.findall(rf":\s*({IDENTIFIER_RE})", before_properties)


def _variable_from_node_body(body: str) -> str:
    before_properties = body.split("{", 1)[0]
    variable = before_properties.split(":", 1)[0].strip()
    if re.fullmatch(IDENTIFIER_RE, variable):
        return variable
    return ""


def _property_keys_from_node_body(body: str) -> list[str]:
    match = re.search(r"\{(?P<properties>[^{}]*)\}", body)
    if not match:
        return []
    return re.findall(rf"\b({IDENTIFIER_RE})\s*:", match.group("properties"))


def _relationship_types_from_body(body: str) -> list[str]:
    before_properties = body.split("{", 1)[0]
    return re.findall(rf"(?::|\|)\s*:?\s*({IDENTIFIER_RE})", before_properties)


def _validate_cypher_schema(cypher: str) -> None:
    """Reject explicit labels, relationship types, and node properties outside the seed schema."""
    variable_labels: dict[str, set[str]] = {}

    for match in NODE_PATTERN_RE.finditer(cypher):
        body = match.group("body")
        labels = _labels_from_node_body(body)
        for label in labels:
            if label not in KG_NODE_PROPERTIES:
                raise UnsupportedCypherError(f"Cypher uses unknown node label: {label}")

        if not labels:
            continue

        allowed_properties = set().union(*(KG_NODE_PROPERTIES[label] for label in labels))
        for property_name in _property_keys_from_node_body(body):
            if property_name not in allowed_properties:
                raise UnsupportedCypherError(f"Cypher uses unknown property: {property_name}")

        variable = _variable_from_node_body(body)
        if variable:
            variable_labels.setdefault(variable, set()).update(labels)

    for match in RELATIONSHIP_PATTERN_RE.finditer(cypher):
        for rel_type in _relationship_types_from_body(match.group("body")):
            if rel_type not in KG_RELATIONSHIP_TYPES:
                raise UnsupportedCypherError(f"Cypher uses unknown relationship type: {rel_type}")

    for _ in range(2):
        for match in ALIAS_RE.finditer(cypher):
            source = match.group("source")
            alias = match.group("alias")
            if source in variable_labels:
                variable_labels.setdefault(alias, set()).update(variable_labels[source])

    for match in PROPERTY_ACCESS_RE.finditer(cypher):
        variable = match.group("variable")
        if variable not in variable_labels:
            continue
        property_name = match.group("property")
        allowed_properties = set().union(*(KG_NODE_PROPERTIES[label] for label in variable_labels[variable]))
        if property_name not in allowed_properties:
            raise UnsupportedCypherError(f"Cypher uses unknown property: {property_name}")


def validate_read_only_cypher(cypher: str, max_chars: int) -> str:
    """Validate and return one read-only Cypher statement without a trailing semicolon."""
    # TODO(KG teammate): Replace this conservative lexical validator with the final
    # course-aligned Cypher safety validator if Module 10/11 provides a parser.
    if max_chars <= 0:
        raise UnsupportedCypherError("Maximum Cypher length must be positive.")

    cleaned = (cypher or "").strip()
    if not cleaned:
        raise UnsupportedCypherError("Cypher query is empty.")
    if len(cleaned) > max_chars:
        raise UnsupportedCypherError("Cypher query is too long.")
    if "```" in cleaned:
        raise UnsupportedCypherError("Cypher query must not contain markdown fences.")

    semicolons = _semicolon_positions_outside_strings(cleaned)
    if len(semicolons) > 1:
        raise UnsupportedCypherError("Multiple Cypher statements are not allowed.")
    if semicolons:
        semicolon_index = semicolons[0]
        if cleaned[semicolon_index + 1 :].strip():
            raise UnsupportedCypherError("Multiple Cypher statements are not allowed.")
        cleaned = cleaned[:semicolon_index].strip()
        if not cleaned:
            raise UnsupportedCypherError("Cypher query is empty.")

    masked = _mask_string_literals(cleaned)
    normalized = re.sub(r"\s+", " ", masked).strip().upper()

    if not READ_ONLY_START_RE.match(normalized):
        raise UnsupportedCypherError("Cypher must start with a read-only clause.")
    if not re.search(r"\bRETURN\b", normalized):
        raise UnsupportedCypherError("Cypher query must include RETURN.")

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, normalized):
            raise UnsupportedCypherError("Cypher contains an unsupported write or admin clause.")

    _validate_cypher_schema(masked)

    return cleaned


def execute_cypher(cypher: str, parameters: dict[str, Any], settings: Settings) -> list[dict[str, Any]]:
    """Execute validated read-only Cypher against Neo4j and return raw record dictionaries."""
    # TODO(KG teammate): Add richer retry/logging behavior if the course reference
    # expects it. Keep validation outside this function so unsafe Cypher never runs.
    try:
        from neo4j import GraphDatabase, Query

        auth = (settings.neo4j_user, settings.neo4j_password)
        query = Query(cypher, timeout=settings.kg_timeout_seconds)
        with GraphDatabase.driver(settings.neo4j_uri, auth=auth) as driver:
            with driver.session(database=settings.neo4j_database) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
    except Exception as exc:  # pragma: no cover - exercised with monkeypatches/unit tests.
        raise KGExecutionError("Neo4j query execution failed.") from exc


def _element_id(value: Any) -> str:
    element_id = getattr(value, "element_id", None)
    if element_id is not None:
        return str(element_id)
    legacy_id = getattr(value, "id", None)
    if legacy_id is not None:
        return str(legacy_id)
    return ""


def _node_payload(value: Any) -> dict[str, Any]:
    return {
        "id": _element_id(value),
        "labels": sorted(str(label) for label in getattr(value, "labels", [])),
        "properties": {
            str(key): serialize_neo4j_value(item)
            for key, item in dict(value).items()
        },
    }


def _relationship_payload(value: Any) -> dict[str, Any]:
    source = getattr(value, "start_node", None)
    target = getattr(value, "end_node", None)
    return {
        "id": _element_id(value),
        "type": str(getattr(value, "type", "")),
        "source": _element_id(source),
        "target": _element_id(target),
        "properties": {
            str(key): serialize_neo4j_value(item)
            for key, item in dict(value).items()
        },
    }


def serialize_neo4j_value(value: Any) -> Any:
    """Convert Neo4j values into JSON-safe Python values."""
    # TODO(KG teammate): Extend this serializer if seed data introduces points,
    # durations, vectors, or additional Neo4j temporal classes.
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    if hasattr(value, "nodes") and hasattr(value, "relationships"):
        return {
            "nodes": [serialize_neo4j_value(node) for node in value.nodes],
            "relationships": [serialize_neo4j_value(rel) for rel in value.relationships],
        }

    if hasattr(value, "labels") and isinstance(getattr(value, "labels"), (set, frozenset)):
        return _node_payload(value)

    if hasattr(value, "start_node") and hasattr(value, "end_node") and hasattr(value, "type"):
        return _relationship_payload(value)

    if isinstance(value, Mapping):
        return {str(key): serialize_neo4j_value(item) for key, item in value.items()}

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [serialize_neo4j_value(item) for item in value]

    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")

    return str(value)


def serialize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Serialize all Neo4j records into JSON-safe dictionaries."""
    return [
        {str(key): serialize_neo4j_value(value) for key, value in record.items()}
        for record in records
    ]


def _is_serialized_node(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("id"), str)
        and isinstance(value.get("labels"), list)
        and isinstance(value.get("properties"), dict)
    )


def _is_serialized_relationship(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("id"), str)
        and isinstance(value.get("type"), str)
        and isinstance(value.get("source"), str)
        and isinstance(value.get("target"), str)
        and isinstance(value.get("properties"), dict)
    )


def extract_graph_elements(records: list[dict[str, Any]]) -> tuple[list[KGNode], list[KGRelationship]]:
    """Extract unique serialized nodes and relationships from serialized records."""
    nodes: dict[str, KGNode] = {}
    relationships: dict[str, KGRelationship] = {}

    def visit(value: Any) -> None:
        if _is_serialized_relationship(value):
            rel = KGRelationship(
                id=value["id"],
                type=value["type"],
                source=value["source"],
                target=value["target"],
                properties=value["properties"],
            )
            relationships.setdefault(rel.id, rel)
        elif _is_serialized_node(value):
            node = KGNode(
                id=value["id"],
                labels=[str(label) for label in value["labels"]],
                properties=value["properties"],
            )
            nodes.setdefault(node.id, node)

        if isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(records)
    return list(nodes.values()), list(relationships.values())


def build_kg_answer(question: str, records: list[dict[str, Any]]) -> str:
    """Build a concise Arabic summary from returned KG rows."""
    row_count = len(records)
    if row_count == 0:
        return "لم تُرجع قاعدة المعرفة التجريبية نتائج لهذا السؤال."
    return f"أرجعت قاعدة المعرفة التجريبية {row_count} صفاً مرتبطاً بالسؤال. راجع السجلات والعلاقات المعروضة للتحقق من التفاصيل القانونية."


def query_knowledge_graph(question: str, settings: Settings) -> KGResponse:
    """Run the Text2Cypher KG flow and return a typed API response."""
    # TODO(KG teammate): Complete the final Text2Cypher orchestration once the KG
    # data and evaluation fixture are populated. Keep validation before execution.
    generated_cypher = generate_cypher(question, settings)
    safe_cypher = validate_read_only_cypher(generated_cypher, settings.kg_max_cypher_chars)
    parameters = {"limit": settings.kg_query_limit}
    raw_records = execute_cypher(safe_cypher, parameters, settings)
    records = serialize_records(raw_records)
    nodes, relationships = extract_graph_elements(records)

    return KGResponse(
        answer=build_kg_answer(question, records),
        generated_cypher=safe_cypher,
        parameters=parameters,
        records=records,
        nodes=nodes,
        relationships=relationships,
        row_count=len(records),
        disclaimer=KG_DISCLAIMER,
    )
