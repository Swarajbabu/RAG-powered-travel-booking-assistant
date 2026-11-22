from pymongo import MongoClient
from pymongo.collection import Collection


def connect_to_collection(
	connection_string: str,
	database_name: str = "wanderlust",
	collection_name: str = "rag_documents",
) -> tuple[MongoClient, Collection]:
	if not connection_string or not connection_string.strip():
		raise ValueError("A MongoDB Atlas connection string is required.")

	client = MongoClient(
		connection_string,
		appname="wanderlust-rag-ingestion",
		serverSelectionTimeoutMS=15000,
	)
	client.admin.command("ping")
	return client, client[database_name][collection_name]
