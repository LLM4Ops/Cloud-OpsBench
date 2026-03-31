# runtime/model_runner.py

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from openai import OpenAI


class ModelRunner:
    """
    Minimal model runner for an OpenAI-compatible chat completion endpoint.

    MVP scope:
    - single model
    - single prompt string
    - returns normalized generation metadata
    """

    def __init__(
        self,
        model_name: str,
        provider: str,
        api_base: str,
        api_key: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: Optional[float] = None,
    ):
        """
        Args:
            model_name: Model identifier, e.g. "qwen3-14b".
            provider: Provider label for bookkeeping. Currently only
                "openai_compatible" is expected in MVP.
            api_base: Base URL of the OpenAI-compatible endpoint.
            api_key: API key string. Can be dummy for local servers.
            temperature: Sampling temperature.
            max_tokens: Maximum generation tokens.
            timeout: Optional client timeout in seconds.
        """
        self.model_name = model_name
        self.provider = provider
        self.api_base = api_base
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        if self.provider != "openai_compatible":
            raise ValueError(
                f"Unsupported provider for MVP: {self.provider}. "
                "Only 'openai_compatible' is supported right now."
            )

        client_kwargs: Dict[str, Any] = {
            "base_url": self.api_base,
            "api_key": self.api_key,
        }
        if self.timeout is not None:
            client_kwargs["timeout"] = self.timeout

        self.client = OpenAI(**client_kwargs)

    def generate(self, prompt: str) -> Dict[str, Any]:
        """
        Generate one response from the model.

        Args:
            prompt: Full prompt string.

        Returns:
            {
                "text": str,
                "latency": float | None,
                "input_tokens": int | None,
                "output_tokens": int | None,
                "raw_response": Any
            }

        Raises:
            RuntimeError: If the response is malformed or generation fails.
        """
        start_time = time.perf_counter()

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                extra_body={"enable_thinking": False},
                # stream=True
            )
            latency = time.perf_counter() - start_time
            print('----------',response)
            text = self._extract_text(response)
            usage = getattr(response, "usage", None)

            input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
            output_tokens = getattr(usage, "completion_tokens", None) if usage else None

            return {
                "text": text,
                "latency": latency,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "raw_response": response,
            }

        except Exception as e:
            raise RuntimeError(f"Model generation failed: {e}") from e

    def _extract_text(self, response: Any) -> str:
        """
        Extract assistant text from a chat completion response.
        """
        try:
            choices = getattr(response, "choices", None)
            if not choices:
                raise ValueError("Response has no choices.")

            message = choices[0].message
            content = getattr(message, "content", None)

            if content is None:
                raise ValueError("Response message content is None.")

            if not isinstance(content, str):
                content = str(content)

            return content.strip()

        except Exception as e:
            raise RuntimeError(f"Failed to extract model text: {e}") from e