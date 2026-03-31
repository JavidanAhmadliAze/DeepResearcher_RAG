import os

from dotenv import load_dotenv
from langchain.tools import tool

load_dotenv()

RAG_ENABLED = os.getenv("ENABLE_RAG", "false").strip().lower() in {"1", "true", "yes", "on"}
_vector_store = None


def get_vector_store():
    """
    Returns a Chroma Cloud vector store, or None if RAG is disabled.
    Local Chroma is intentionally not supported — use Chroma Cloud when enabling RAG.
    Set ENABLE_RAG=true and provide CHROMA_CLOUD_HOST + CHROMA_CLOUD_API_KEY.
    """
    global _vector_store

    if not RAG_ENABLED:
        return None

    if _vector_store is None:
        import chromadb
        from langchain_chroma import Chroma
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        chroma_host = os.getenv("CHROMA_CLOUD_HOST")
        if not chroma_host:
            raise EnvironmentError(
                "ENABLE_RAG=true but CHROMA_CLOUD_HOST is not set. "
                "Provide your Chroma Cloud host or disable RAG."
            )

        api_key = os.getenv("CHROMA_CLOUD_API_KEY")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        client = chromadb.HttpClient(
            host=chroma_host,
            port=int(os.getenv("CHROMA_CLOUD_PORT", "443")),
            ssl=True,
            headers=headers,
        )
        embedding = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")
        _vector_store = Chroma(
            client=client,
            collection_name="deep_research_texts",
            embedding_function=embedding,
            collection_metadata={"hnsw:space": "cosine"},
        )

    return _vector_store


@tool
def retrieve_data_with_score(research_brief: str):
    """
    Retrieve relevant documents from Chroma Cloud using the research brief.
    Returns needs_research=True when RAG is disabled or no sufficiently similar
    documents exist (cosine distance > 0.30).
    """
    vector_store = get_vector_store()
    if vector_store is None:
        return {"needs_research": True, "serialized": "", "rag_disabled": True}

    results = vector_store.similarity_search_with_score(query=research_brief, k=10)

    best_score = min(score for _, score in results) if results else 1.0
    if best_score > 0.30:
        return {"needs_research": True, "serialized": ""}

    serialized = "\n\n".join(f"Content: {doc.page_content}" for doc, _ in results)
    return {"needs_research": False, "serialized": serialized}
