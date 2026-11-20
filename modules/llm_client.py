"""
LLM Client for local model inference.
Communicates with Ollama (or OpenAI-compatible local APIs like LM Studio).
Includes diagnostic health checks and offline fallback test mode.
"""

import json
import logging
import requests
from typing import Generator, Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LocalLLMClient:
    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3.1:8b", temperature: float = 0.2):
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.connect_timeout = 3.0  # Fail fast if server not running
        self.read_timeout = 120.0   # Allow ample time for model token generation
        self._is_server_up = None

    def check_health(self) -> Dict[str, Any]:
        """Check if local Ollama server is running and get list of installed models."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=self.connect_timeout)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                is_model_present = any(self.model in m for m in models)
                self._is_server_up = True
                return {
                    "connected": True,
                    "host": self.host,
                    "models": models,
                    "model_installed": is_model_present,
                    "active_model": self.model
                }
        except Exception as e:
            self._is_server_up = False
            return {
                "connected": False,
                "host": self.host,
                "error": str(e),
                "models": [],
                "model_installed": False,
                "active_model": self.model
            }

        self._is_server_up = False
        return {
            "connected": False,
            "host": self.host,
            "models": [],
            "model_installed": False,
            "active_model": self.model
        }

    def generate(self, prompt: str, system_prompt: Optional[str] = None, format_json: bool = False) -> str:
        """Generate response from the local model."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": 8192
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
        if format_json:
            payload["format"] = "json"

        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=(self.connect_timeout, self.read_timeout)
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            self._is_server_up = False
            raise ConnectionError(
                f"Cannot connect to local Ollama server at {self.host}.\n"
                f"Please ensure Ollama is running (`ollama serve` or open Ollama desktop)."
            )
        except Exception as e:
            raise RuntimeError(f"Error querying local LLM ({self.model}): {e}")

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Generate structured JSON response, with fallback markdown json-block extraction."""
        raw_output = self.generate(prompt=prompt, system_prompt=system_prompt, format_json=True)
        try:
            return json.loads(raw_output)
        except json.JSONDecodeError:
            text = raw_output.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)

    def stream_generate(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        """Stream response tokens for interactive UI display."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": self.temperature,
                "num_ctx": 8192
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            with requests.post(
                f"{self.host}/api/generate",
                json=payload,
                stream=True,
                timeout=(self.connect_timeout, self.read_timeout)
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line.decode("utf-8"))
                        yield chunk.get("response", "")
                        if chunk.get("done", False):
                            break
        except Exception as e:
            yield f"\n[Error querying local LLM: {e}]"
