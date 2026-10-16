from functools import lru_cache

import config


@lru_cache(maxsize=1)
def get_embeddings():
    """
    Shared embeddings client.

    The dimensionality must match the vector(...) column of
    knowledge_documents.embedding in Supabase (768 by default).
    """
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing from Backend/.env")

    # Lazy import keeps server start-up fast (see rag_service._get_llm).
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(
        model=config.EMBEDDING_MODEL,
        google_api_key=config.GEMINI_API_KEY,
        output_dimensionality=config.EMBEDDING_DIMENSIONS,
    )
