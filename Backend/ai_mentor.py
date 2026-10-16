"""
Legacy, non-RAG mentor (the API uses rag/rag_service.py instead).
Kept as a quick way to test the Gemini key from the command line:

    python ai_mentor.py
"""

import json
import logging

from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)

_client = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is missing from Backend/.env")
        _client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=120_000),
        )
    return _client


def generate_ai_response(prompt: str) -> str:
    last_error = None
    for model in config.GEMINI_MODELS:
        try:
            logger.info("Trying model: %s", model)
            response = get_client().models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=1200),
            )
            return (response.text or "").strip() or "AI Mentor did not return a response."
        except Exception as error:  # noqa: BLE001
            logger.warning("%s failed: %s", model, error)
            last_error = error

    return f"AI Mentor temporarily unavailable. Last error: {last_error}"


def explain_code(problem: str, code: str) -> str:
    prompt = f"""
You are an AI Coding Mentor.

Analyze the student's solution.

Problem:
{problem}

Student Code:
{code}

Return ONLY valid JSON with exactly this structure:
{{
    "approach": "Explain the approach in simple language.",
    "how_it_works": "Explain how the student's code works step by step.",
    "time_complexity": "Give the time complexity such as O(n) or O(n^2).",
    "space_complexity": "Give the space complexity such as O(1) or O(n).",
    "good_points": "Explain what is good about the student's solution.",
    "improvements": "Explain what can be improved without unnecessarily replacing the whole solution."
}}

Rules:
- Keep the explanation simple for a programming student.
- Analyze the student's actual code.
"""

    last_error = None
    for model in config.GEMINI_MODELS:
        try:
            response = get_client().models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=1000,
                    response_mime_type="application/json",
                ),
            )
            return response.text or "{}"
        except Exception as error:  # noqa: BLE001
            logger.warning("GEMINI ERROR (%s): %s", model, error)
            last_error = error

    return json.dumps({
        "approach": "AI Mentor temporarily unavailable.",
        "how_it_works": "",
        "time_complexity": "",
        "space_complexity": "",
        "good_points": "",
        "improvements": str(last_error),
    })


if __name__ == "__main__":
    problem = """
Given an array of integers nums and an integer target,
return indices of two numbers that add up to target.
"""

    code = """
def two_sum(nums, target):
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] + nums[j] == target:
                return [i, j]
"""

    print("\n========== AI MENTOR ==========\n")
    print(explain_code(problem, code))
