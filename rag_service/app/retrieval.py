from typing import Any


MIN_RELEVANCE_SCORE = 0.55


def retrieve_chunks(
    collection: Any,
    question_embedding: list[float],
    limit: int = 5,
    index_name: str = "rag_vector_index",
) -> list[dict[str, Any]]:
    pipeline = [
        {
            "$vectorSearch": {
                "index": index_name,
                "path": "embedding",
                "queryVector": question_embedding,
                "numCandidates": max(limit * 10, 50),
                "limit": limit,
            }
        },
        {
            "$project": {
                "_id": 0,
                "documentId": 1,
                "sourceFile": 1,
                "pageNumber": 1,
                "chunkIndex": 1,
                "text": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    results = list(collection.aggregate(pipeline))
    relevant = [
        result
        for result in results
        if isinstance(result.get("score"), (int, float))
        and result["score"] >= MIN_RELEVANCE_SCORE
    ]

    deduplicated = []
    seen_text = set()
    for result in relevant:
        normalized = " ".join(str(result.get("text", "")).split()).lower()
        signature = normalized[:300]
        if signature in seen_text:
            continue
        seen_text.add(signature)
        deduplicated.append(result)

    return deduplicated
