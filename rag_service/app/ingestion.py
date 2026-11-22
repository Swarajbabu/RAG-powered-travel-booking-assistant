import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pymongo import UpdateOne
from pymongo.collection import Collection


def split_text_into_chunks(
	text: str,
	chunk_size: int = 900,
	overlap: int = 180,
) -> list[str]:
	if chunk_size < 1:
		raise ValueError("chunk_size must be greater than zero.")
	if overlap < 0 or overlap >= chunk_size:
		raise ValueError("overlap must be at least zero and smaller than chunk_size.")

	normalized_text = re.sub(r"\s+", " ", text).strip()
	if not normalized_text:
		return []

	chunks = []
	start = 0
	while start < len(normalized_text):
		end = min(start + chunk_size, len(normalized_text))
		if end < len(normalized_text):
			boundary = normalized_text.rfind(" ", start, end)
			if boundary > start + max(1, chunk_size // 2):
				end = boundary

		chunk = normalized_text[start:end].strip()
		if chunk:
			chunks.append(chunk)

		if end >= len(normalized_text):
			break
		start = max(start + 1, end - overlap)

	return chunks


def _document_id(source_file: str) -> str:
	stem = Path(source_file).stem.lower()
	slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
	return slug or hashlib.sha256(source_file.encode("utf-8")).hexdigest()[:16]


def extract_pdf_chunks(
	pdf_path: Path,
	chunk_size: int = 900,
	overlap: int = 180,
) -> list[dict[str, Any]]:
	reader = PdfReader(str(pdf_path))
	document_id = _document_id(pdf_path.name)
	records = []
	chunk_index = 0

	for page_number, page in enumerate(reader.pages, start=1):
		page_text = page.extract_text() or ""
		for text in split_text_into_chunks(page_text, chunk_size, overlap):
			hash_input = f"{document_id}\0{page_number}\0{chunk_index}\0{text}"
			content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
			records.append({
				"documentId": document_id,
				"sourceFile": pdf_path.name,
				"pageNumber": page_number,
				"chunkIndex": chunk_index,
				"text": text,
				"contentHash": content_hash,
			})
			chunk_index += 1

	return records


def _write_chunk_batch(collection: Collection, operations: list[UpdateOne]) -> None:
	if operations:
		collection.bulk_write(operations, ordered=False)


def ingest_pdf_directory(
	documents_dir: Path,
	collection: Collection,
	model: Any,
	embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
	chunk_size: int = 900,
	overlap: int = 180,
	batch_size: int = 32,
) -> list[dict[str, Any]]:
	documents_dir = Path(documents_dir)
	if not documents_dir.is_dir():
		raise FileNotFoundError(f"PDF directory does not exist: {documents_dir}")

	pdf_files = sorted(
		(path for path in documents_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
		key=lambda path: path.name.lower(),
	)
	if not pdf_files:
		raise FileNotFoundError(f"No PDF files found in: {documents_dir}")
	if batch_size < 1:
		raise ValueError("batch_size must be greater than zero.")

	collection.create_index("contentHash", unique=True, name="rag_content_hash_unique")
	summaries = []

	for pdf_path in pdf_files:
		records = extract_pdf_chunks(pdf_path, chunk_size, overlap)
		if not records:
			raise ValueError(
				f"No extractable text found in {pdf_path.name}; existing chunks were left unchanged."
			)

		embeddings = model.encode(
			[record["text"] for record in records],
			batch_size=batch_size,
			normalize_embeddings=True,
			show_progress_bar=True,
			convert_to_numpy=True,
		)
		if len(embeddings) != len(records):
			raise RuntimeError(f"Embedding count did not match chunk count for {pdf_path.name}.")

		now = datetime.now(timezone.utc)
		operations = []
		content_hashes = []
		for record, embedding in zip(records, embeddings):
			vector = [float(value) for value in embedding.tolist()]
			if len(vector) != 384:
				raise ValueError(
					f"Expected 384 embedding values for {pdf_path.name}, got {len(vector)}."
				)

			content_hashes.append(record["contentHash"])
			stored_record = {
				**record,
				"embedding": vector,
				"embeddingModel": embedding_model,
				"embeddingDimensions": len(vector),
				"updatedAt": now,
			}
			operations.append(UpdateOne(
				{"contentHash": record["contentHash"]},
				{
					"$set": stored_record,
					"$setOnInsert": {"createdAt": now},
				},
				upsert=True,
			))

		_write_chunk_batch(collection, operations)
		stale_result = collection.delete_many({
			"sourceFile": pdf_path.name,
			"contentHash": {"$nin": content_hashes},
		})
		summaries.append({
			"sourceFile": pdf_path.name,
			"chunksUpserted": len(records),
			"staleChunksRemoved": stale_result.deleted_count,
		})

	return summaries
