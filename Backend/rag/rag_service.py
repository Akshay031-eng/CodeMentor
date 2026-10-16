"""
RAG-powered AI mentor: retrieve relevant knowledge from Supabase pgvector,
then ask Gemini for structured, beginner-friendly feedback.
"""

import json
import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

import config
from database import supabase
from rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)

MENTOR_FIELDS = (
    "answer",
    "approach",
    "how_it_works",
    "time_complexity",
    "space_complexity",
    "good_points",
    "improvements",
)

MAX_CODE_CHARS_IN_PROMPT = 12_000


class MentorUnavailableError(RuntimeError):
    """Raised when every configured Gemini model failed."""


@lru_cache(maxsize=None)
def _get_llm(model: str):
    if not config.GEMINI_API_KEY:
        raise MentorUnavailableError("GEMINI_API_KEY is missing from Backend/.env")

    # Imported lazily: LangChain is the slowest import of the whole backend,
    # so loading it on first use halves server start-up (cold starts).
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=config.GEMINI_API_KEY,
        temperature=0.2,
        max_output_tokens=2048,
        response_mime_type="application/json",
        timeout=60,
        max_retries=1,
    )


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve_knowledge(
    query: str,
    match_count: int = config.RAG_MATCH_COUNT,
    match_threshold: float = config.RAG_MATCH_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant knowledge from Supabase pgvector.
    Retrieval problems never break the mentor - it just answers without context.
    """
    try:
        query_embedding = get_embeddings().embed_query(query)
        response = supabase.rpc(
            "match_knowledge_documents",
            {
                "query_embedding": query_embedding,
                "match_threshold": match_threshold,
                "match_count": match_count,
            },
        ).execute()
        return response.data or []
    except Exception as error:  # noqa: BLE001
        logger.warning("Knowledge retrieval failed, continuing without context: %r", error)
        return []


def build_context(documents: List[Dict[str, Any]]) -> str:
    if not documents:
        return "No relevant knowledge was found."

    parts = []
    for document in documents:
        parts.append(
            f"SOURCE: {document.get('title', 'Unknown')}\n"
            f"CATEGORY: {document.get('category', 'Unknown')}\n"
            f"CONTENT:\n{(document.get('content') or '').strip()}"
        )
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def message_text(message: Any) -> str:
    """Plain text from a LangChain message (content may be a string or a list of parts)."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
        return "".join(parts)
    return str(content or "")


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON even if the model wrapped it in ```json fences or added extra text."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()

    candidates = [text]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])

    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    return None


def _to_text(value: Any) -> str:
    """The frontend renders plain strings; never hand it lists/objects."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return "\n".join(f"• {_to_text(item)}" for item in value if _to_text(item))
    if isinstance(value, dict):
        return "\n".join(f"{key}: {_to_text(item)}" for key, item in value.items())
    return str(value)


def normalize_mentor_response(raw_text: str) -> Dict[str, str]:
    data = extract_json(raw_text)
    if data is None:
        # Model ignored the JSON instruction - still show what it said.
        text = (raw_text or "").strip() or "The mentor returned an empty response."
        return {field: "" for field in MENTOR_FIELDS} | {"answer": text}

    result = {field: _to_text(data.get(field)) for field in MENTOR_FIELDS}
    if not result["answer"]:
        result["answer"] = result["approach"] or result["how_it_works"]
    return result


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """You are an expert, encouraging AI Coding Mentor for programming students.

PROBLEM: {title}
DIFFICULTY: {difficulty}
TOPIC: {topic}

PROBLEM STATEMENT:
{description}

LANGUAGE: {language}

STUDENT CODE:
```{language}
{code}
```

LATEST RUN RESULT:
{run_summary}

PREVIOUS CONVERSATION (most recent last):
{history}

STUDENT'S CURRENT QUESTION:
{question}

RELEVANT KNOWLEDGE (retrieved with RAG):
---------------- CONTEXT ----------------
{context}
-------------- END CONTEXT --------------

Return ONLY a JSON object with exactly these string fields:
{{
  "answer": "A direct answer to the student's current question.",
  "approach": "The approach the student's code takes (or should take).",
  "how_it_works": "Step-by-step explanation of how the algorithm / their code works.",
  "time_complexity": "e.g. O(n) - with a one-line reason",
  "space_complexity": "e.g. O(1) - with a one-line reason",
  "good_points": "What the student did well.",
  "improvements": "Concrete, prioritized improvements or bug fixes and why."
}}

Rules:
- "answer" must directly address the CURRENT QUESTION. If they ask for a hint, give a hint only.
- Analyze the student's ACTUAL code; quote the exact line when pointing out a bug.
- Use the LATEST RUN RESULT (if any) to find why a test fails.
- Do not give a complete solution unless the student explicitly asks for it. Teach the concept.
- Use the retrieved knowledge when it is relevant; ignore it when it is not.
- Do not repeat earlier answers from the conversation unless asked.
- Keep it beginner-friendly and concise. Plain text inside the JSON strings (no Markdown headings).
"""


def ask_mentor(
    question: str,
    problem_title: str = "",
    code: str = "",
    language: str = "",
    *,
    problem_description: str = "",
    difficulty: str = "",
    topic: str = "",
    history: str = "",
    run_summary: str = "",
) -> Dict[str, Any]:
    question = (question or "").strip()

    # Embed only the problem + current question: long chat history or code
    # dilutes the embedding and hurts retrieval quality.
    retrieval_query = f"{problem_title} ({topic}). {question}".strip()
    documents = retrieve_knowledge(retrieval_query)

    trimmed_code = code or ""
    if len(trimmed_code) > MAX_CODE_CHARS_IN_PROMPT:
        trimmed_code = trimmed_code[:MAX_CODE_CHARS_IN_PROMPT] + "\n... (code truncated)"

    prompt = PROMPT_TEMPLATE.format(
        title=problem_title or "Unknown",
        difficulty=difficulty or "Unknown",
        topic=topic or "Unknown",
        description=(problem_description or "Not provided.").strip(),
        language=language or "unknown",
        code=trimmed_code,
        run_summary=(run_summary or "The student has not run the code yet.").strip(),
        history=(history or "None.").strip(),
        question=question,
        context=build_context(documents),
    )

    last_error: Optional[Exception] = None
    for model in config.GEMINI_MODELS:
        try:
            response = _get_llm(model).invoke(prompt)
            mentor_data = normalize_mentor_response(message_text(response))
            break
        except MentorUnavailableError:
            raise
        except Exception as error:  # noqa: BLE001
            logger.warning("Gemini model %s failed: %r", model, error)
            last_error = error
    else:
        raise MentorUnavailableError(
            "AI Mentor is temporarily unavailable. Please try again in a moment."
        ) from last_error

    return {
        **mentor_data,
        "sources": [
            {
                "title": document.get("title"),
                "category": document.get("category"),
                "similarity": document.get("similarity"),
            }
            for document in documents
        ],
    }
