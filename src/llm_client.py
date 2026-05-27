"""LLM Client for OpenAI-compatible APIs."""

import os
import time
import json
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import requests

load_dotenv()

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for calling LLM APIs with retry logic and timeout support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 60,
        max_retries: int = 3,
        retry_delay: int = 2,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        if not self.api_key:
            logger.warning("LLM_API_KEY not set. API calls will fail.")

    def _make_request(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Make a single request to the LLM API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        url = f"{self.base_url.rstrip('/')}/chat/completions"

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        parse_json: bool = True,
    ) -> Any:
        """
        Send a chat request to the LLM.

        Args:
            system_prompt: System message for role definition.
            user_prompt: User message with task instructions.
            parse_json: If True, attempt to parse JSON from response.

        Returns:
            Parsed response (dict/list if JSON, otherwise str).
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"LLM request attempt {attempt + 1}/{self.max_retries}")
                response = self._make_request(messages)

                content = response["choices"][0]["message"]["content"].strip()

                if parse_json:
                    # Extract JSON from markdown code block if present
                    json_content = self._extract_json(content)
                    return json_content

                return content

            except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
                last_error = e
                logger.warning(f"Request failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                continue

        raise RuntimeError(f"LLM request failed after {self.max_retries} attempts: {last_error}")

    def _extract_json(self, content: str) -> Any:
        """Extract JSON from markdown code block or raw string."""
        # Try to find JSON in ```json ... ``` block
        import re

        json_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(json_pattern, content)

        if match:
            json_str = match.group(1).strip()
        else:
            # Try to parse the entire content as JSON
            json_str = content

        return json.loads(json_str)
