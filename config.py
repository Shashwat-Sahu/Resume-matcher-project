"""
Configuration module for Resume Matcher Pro.
Supports local Llama models via Ollama (or any OpenAI-compatible local server like LM Studio).
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class ModelInfo:
    id: str
    name: str
    tagline: str
    recommended_vram: str
    context_window: str
    description: str

RECOMMENDED_LLAMA_MODELS: Dict[str, ModelInfo] = {
    "llama3.1:8b": ModelInfo(
        id="llama3.1:8b",
        name="Llama 3.1 (8B Instruct) - Recommended",
        tagline="Best all-around model for resume tailoring, JSON extraction, and keyword precision.",
        recommended_vram="8 GB VRAM or 16 GB System RAM",
        context_window="128k tokens",
        description="Meta's top balanced model. Highly accurate at extracting candidate accomplishments and matching JD requirements without hallucinating."
    ),
    "llama3.2:3b": ModelInfo(
        id="llama3.2:3b",
        name="Llama 3.2 (3B Instruct) - Ultra Fast & Lightweight",
        tagline="Lightning fast execution for quick screening and lighter machines.",
        recommended_vram="4 GB VRAM or 8 GB System RAM",
        context_window="128k tokens",
        description="Optimized for edge and consumer hardware. Generates responses instantly with minimal memory footprint."
    ),
    "llama3.3:70b": ModelInfo(
        id="llama3.3:70b",
        name="Llama 3.3 (70B Instruct) - Frontier Quality",
        tagline="Flagship reasoning and executive-level bullet phrasing.",
        recommended_vram="24 GB+ VRAM or 64 GB System RAM (Q4)",
        context_window="128k tokens",
        description="Top-tier reasoning matching GPT-4o class. Superb for senior/executive resumes, deep contextual rewrites, and strategic interview prep."
    )
}

# Ollama & Local API Settings
DEFAULT_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("RESUME_MATCHER_MODEL", "llama3.1:8b")
DEFAULT_TEMPERATURE = float(os.getenv("RESUME_MATCHER_TEMP", "0.2"))

# Output Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
