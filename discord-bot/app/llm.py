"""Shared LLM utilities for the project."""

import os

from langchain_google_genai import ChatGoogleGenerativeAI


def create_llm() -> ChatGoogleGenerativeAI:
    """Create the Gemini LLM instance."""
    google_api_key = os.getenv("GOOGLE_API_KEY", "")
    if not google_api_key or google_api_key == "your_google_api_key_here":
        raise RuntimeError("GOOGLE_API_KEY not set in environment")

    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        temperature=0.0,
        google_api_key=google_api_key,
    )
