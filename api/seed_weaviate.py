from __future__ import annotations

import json
from pathlib import Path

import weaviate

from api.rag import encode_texts, format_passage_for_embedding
from api.settings import get_settings


SEED_PATH = Path(__file__).with_name("seed_chunks.json")


def load_seed_chunks(path: Path = SEED_PATH) -> list[dict]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(rows, list):
        raise SystemExit(f"{path} must contain a JSON array.")

    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        chunk_id = row.get("chunk_id")
        if not chunk_id:
            raise SystemExit(f"Chunk {index} is missing chunk_id.")
        if chunk_id in seen:
            raise SystemExit(f"Duplicate chunk_id found: {chunk_id}")
        seen.add(chunk_id)
    return rows


def build_schema(class_name: str) -> dict:
    return {
        "class": class_name,
        "vectorizer": "none",
        "vectorIndexConfig": {"distance": "cosine"},
        "properties": [
            {"name": "chunk_id", "dataType": ["text"]},
            {"name": "source_name", "dataType": ["text"]},
            {"name": "reference", "dataType": ["text"]},
            {"name": "topic", "dataType": ["text"]},
            {"name": "text", "dataType": ["text"]},
            {"name": "source_page", "dataType": ["int"]},
            {"name": "source_type", "dataType": ["text"]},
            {"name": "jurisdiction", "dataType": ["text"]},
        ],
    }


def recreate_class(client, class_name: str) -> None:
    existing = client.schema.get().get("classes", [])
    if any(item.get("class") == class_name for item in existing):
        client.schema.delete_class(class_name)
    client.schema.create_class(build_schema(class_name))


def chunk_properties(chunk: dict) -> dict:
    allowed = [
        "chunk_id",
        "source_name",
        "reference",
        "topic",
        "text",
        "source_page",
        "source_type",
        "jurisdiction",
    ]
    return {key: chunk.get(key) for key in allowed if chunk.get(key) is not None}


def main() -> None:
    settings = get_settings()
    chunks = load_seed_chunks()
    client = weaviate.Client(url=settings.weaviate_url)
    recreate_class(client, settings.weaviate_class)

    embedding_inputs = [
        format_passage_for_embedding(str(chunk.get("embedding_text") or ""), settings.embedding_model)
        for chunk in chunks
    ]
    vectors = encode_texts(embedding_inputs, settings.embedding_model)

    client.batch.configure(batch_size=20)
    with client.batch as batch:
        for chunk, vector in zip(chunks, vectors):
            batch.add_data_object(
                data_object=chunk_properties(chunk),
                class_name=settings.weaviate_class,
                vector=vector,
            )

    print(f"class: {settings.weaviate_class}")
    print(f"chunks_loaded: {len(chunks)}")
    print(f"embedding_model: {settings.embedding_model}")
    print(f"first_chunk_id: {chunks[0]['chunk_id']}")
    print(f"last_chunk_id: {chunks[-1]['chunk_id']}")


if __name__ == "__main__":
    main()
