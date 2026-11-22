from rag_service.app.retrieval import MIN_RELEVANCE_SCORE, retrieve_chunks


class MockCollection:
    def __init__(self, results):
        self.results = results

    def aggregate(self, pipeline):
        return iter(self.results)


def test_retrieve_chunks_filters_low_scores():
    collection = MockCollection([
        {
            "documentId": "01-project-overview",
            "sourceFile": "01. project_overview.pdf",
            "pageNumber": 1,
            "chunkIndex": 0,
            "text": "Wanderlust supports solo travel.",
            "score": MIN_RELEVANCE_SCORE,
        },
        {
            "documentId": "01-project-overview",
            "sourceFile": "01. project_overview.pdf",
            "pageNumber": 2,
            "chunkIndex": 1,
            "text": "This chunk is unrelated.",
            "score": 0.20,
        },
    ])

    chunks = retrieve_chunks(collection, [0.1] * 384)

    assert len(chunks) == 1
    assert chunks[0]["sourceFile"] == "01. project_overview.pdf"


def test_retrieve_chunks_deduplicates_repeated_text():
    repeated = {
        "documentId": "04-room-share",
        "sourceFile": "04. room_share.pdf",
        "pageNumber": 3,
        "chunkIndex": 0,
        "text": "Room sharing allows travelers to split a stay.",
        "score": 0.80,
    }
    collection = MockCollection([repeated, dict(repeated, pageNumber=4, chunkIndex=1)])

    chunks = retrieve_chunks(collection, [0.1] * 384)

    assert len(chunks) == 1
