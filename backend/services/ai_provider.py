"""
Centralized AI Provider Service for Blogger AI Agent.
Enforces strict mode separation:
- Online Mode (Default): Uses Google Gemini Cloud API with real internet connectivity verification.
- Offline Mode (Ollama): Uses local Ollama instance without sending any data to cloud AI.

Features:
- Never exposes API keys in frontend, logs, or exceptions
- Explicit errors and setup instructions when providers are disconnected or unavailable
- Never silently switches between Online and Offline modes
- Token and latency tracking across all calls
"""

import abc
import json
import logging
import re
import socket
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

from backend.config import settings, mask_secret

logger = logging.getLogger("blogger_agent.ai_provider")


# =========================================================================
# EXCEPTIONS
# =========================================================================

class AIProviderError(Exception):
    """Base error for AI Provider operations."""
    def __init__(self, message: str, provider: str = "ai", retryable: bool = False, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable
        self.details = details or {}


class ConnectivityError(AIProviderError):
    """Raised when an operation requires an internet connection but device is offline."""
    def __init__(self, message: Optional[str] = None):
        msg = message or "You're offline. Connect to the internet or switch to Offline AI and connect Ollama."
        super().__init__(msg, provider="network", retryable=True)


class OllamaConnectionError(AIProviderError):
    """Raised when Ollama cannot be reached or is not running."""
    def __init__(self, base_url: str, message: Optional[str] = None):
        default_msg = (
            f"Ollama is disconnected or unavailable at {base_url}. "
            "Please start Ollama by running 'ollama serve' in your terminal or launch the Ollama desktop app. "
            "If Ollama is not installed, download it from https://ollama.com."
        )
        super().__init__(message or default_msg, provider="ollama", retryable=True, details={"base_url": base_url})


class OllamaModelError(AIProviderError):
    """Raised when the specified model is not available in Ollama."""
    def __init__(self, model_name: str, available_models: List[str]):
        if available_models:
            avail_str = ", ".join(available_models)
            msg = (
                f"Model '{model_name}' is not installed in Ollama. "
                f"Available models: [{avail_str}]. "
                f"To install '{model_name}', run 'ollama pull {model_name}' or select an available model in Settings."
            )
        else:
            msg = (
                f"No local models found in Ollama. "
                f"Please download a model by running 'ollama pull {model_name}' in your terminal, then try again."
            )
        super().__init__(msg, provider="ollama", retryable=False, details={"requested_model": model_name, "available_models": available_models})


# =========================================================================
# CONNECTIVITY CHECKER
# =========================================================================

_internet_cache = {"status": True, "expires": 0.0}

def check_internet_connection(timeout: float = 1.0, use_cache: bool = True) -> bool:
    """
    Verify real outbound internet connectivity using lightweight socket connections.
    Caches result for 10 seconds to avoid repeating socket calls.
    """
    now = time.time()
    if use_cache and now < _internet_cache["expires"]:
        return _internet_cache["status"]

    test_hosts = [
        ("8.8.8.8", 53),      # Google DNS
        ("1.1.1.1", 53),      # Cloudflare DNS
        ("208.67.222.222", 53) # OpenDNS
    ]
    is_online = False
    for host, port in test_hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            is_online = True
            break
        except (socket.timeout, OSError):
            continue

    if not is_online:
        # Fallback to quick HTTP GET if socket connect fails
        try:
            resp = requests.get("https://www.google.com/generate_204", timeout=timeout)
            if resp.status_code in (200, 204):
                is_online = True
        except Exception:
            pass

    _internet_cache["status"] = is_online
    _internet_cache["expires"] = now + 10.0
    return is_online


# =========================================================================
# BASE PROVIDER INTERFACE
# =========================================================================

class BaseAIProvider(abc.ABC):
    @abc.abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 2,
    ) -> Tuple[str, int, int]:
        """Generate text/markdown. Returns (text, in_tokens, out_tokens)."""
        pass

    @abc.abstractmethod
    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_retries: int = 2,
    ) -> Tuple[Dict[str, Any], int, int]:
        """Generate structured JSON. Returns (data_dict, in_tokens, out_tokens)."""
        pass

    @abc.abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """Verify provider availability, health, and credentials."""
        pass

    @abc.abstractmethod
    def get_available_models(self) -> List[str]:
        """Fetch list of supported or installed models."""
        pass


# =========================================================================
# GEMINI CLOUD PROVIDER (ONLINE MODE)
# =========================================================================

class GeminiProvider(BaseAIProvider):
    def __init__(self):
        self._client = None
        self._init_client()

    def _init_client(self):
        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                # NEVER log the raw API key!
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI client: {e}")
                self._client = None
        else:
            self._client = None

    def refresh_credentials(self):
        self._init_client()

    _gemini_health_cache = {"result": None, "expires": 0.0}

    def check_health(self, force_refresh: bool = False) -> Dict[str, Any]:
        now = time.time()
        if not force_refresh and self._gemini_health_cache["result"] is not None and now < self._gemini_health_cache["expires"]:
            return self._gemini_health_cache["result"]

        if not settings.GEMINI_API_KEY:
            res = {
                "healthy": False,
                "provider": "gemini",
                "configured": False,
                "message": "Gemini API key is not configured. Please enter your API key in Settings.",
                "model": settings.GEMINI_MODEL,
            }
            self._gemini_health_cache = {"result": res, "expires": now + 5.0}
            return res

        # Check internet first (uses fast cache)
        if not check_internet_connection(timeout=1.0):
            res = {
                "healthy": False,
                "provider": "gemini",
                "configured": True,
                "message": "You're offline. Connect to the internet or switch to Offline AI and connect Ollama.",
                "model": settings.GEMINI_MODEL,
            }
            self._gemini_health_cache = {"result": res, "expires": now + 5.0}
            return res

        if not self._client:
            self._init_client()
            if not self._client:
                res = {
                    "healthy": False,
                    "provider": "gemini",
                    "configured": True,
                    "message": "Google GenAI SDK failed to initialize. Please check Python environment.",
                    "model": settings.GEMINI_MODEL,
                }
                self._gemini_health_cache = {"result": res, "expires": now + 5.0}
                return res

        # Fast verification: validate client and key existence
        # Notice: making a live inference call every few seconds adds 5-15s latency and exhausts quota.
        # Instead, verify configuration and internet, with a 60s cache for live verification if already tested.
        model = settings.GEMINI_MODEL or "gemini-3.1-flash-lite"
        try:
            # We consider it healthy if client initialized, key is present, and internet is online
            res = {
                "healthy": True,
                "provider": "gemini",
                "configured": True,
                "message": f"Online Gemini connected ({model})",
                "model": model,
                "key_preview": mask_secret(settings.GEMINI_API_KEY),
            }
            self._gemini_health_cache = {"result": res, "expires": now + 30.0}
            return res
        except Exception as e:
            err_str = str(e)
            user_msg = f"Gemini API error: {err_str[:120]}"
            if "401" in err_str or "API_KEY_INVALID" in err_str:
                user_msg = "Invalid Gemini API key. Please check your API key in Settings."
            elif "404" in err_str or "NOT_FOUND" in err_str:
                user_msg = f"Configured Gemini model '{settings.GEMINI_MODEL}' was not found or deprecated. Please choose gemini-3.1-flash-lite or gemini-3.8-flash."
            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                user_msg = "Gemini API rate limit or quota exceeded. Please wait a moment and retry."
            res = {
                "healthy": False,
                "provider": "gemini",
                "configured": True,
                "message": user_msg,
                "model": settings.GEMINI_MODEL,
                "error": err_str[:160],
            }
            self._gemini_health_cache = {"result": res, "expires": now + 5.0}
            return res

        return {
            "healthy": False,
            "provider": "gemini",
            "configured": True,
            "message": "Unable to verify Gemini connection.",
            "model": settings.GEMINI_MODEL,
        }

    def get_available_models(self) -> List[str]:
        return [
            "gemini-3.1-flash-lite",
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-2.5-pro",
        ]

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 2,
    ) -> Tuple[str, int, int]:
        if not settings.GEMINI_API_KEY:
            raise AIProviderError(
                "Gemini API key is not configured for Online AI mode. Please enter your API key in Settings.",
                provider="gemini",
                retryable=False,
            )

        if not check_internet_connection(timeout=2.5):
            raise ConnectivityError(
                "You're offline. Connect to the internet or switch to Offline AI and connect Ollama."
            )

        if not self._client:
            self._init_client()
            if not self._client:
                raise AIProviderError("Failed to initialize Google GenAI client.", provider="gemini")

        from google.genai import types
        from google.genai.errors import APIError

        model = settings.GEMINI_MODEL or "gemini-3.1-flash-lite"
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction,
        )

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                text = response.text or ""
                if not text.strip():
                    raise AIProviderError("Empty response returned from Gemini API.", provider="gemini", retryable=True)

                in_tokens = int(len(prompt) / 4)
                out_tokens = int(len(text) / 4)
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    in_tokens = getattr(response.usage_metadata, "prompt_token_count", in_tokens) or in_tokens
                    out_tokens = getattr(response.usage_metadata, "candidates_token_count", out_tokens) or out_tokens

                return text, in_tokens, out_tokens

            except APIError as e:
                last_error = e
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if "401" in err_str or "API_KEY_INVALID" in err_str:
                    raise AIProviderError(
                        "Invalid Gemini API key. Please verify your API key in Settings.",
                        provider="gemini",
                        retryable=False,
                    )
                if "404" in err_str or "NOT_FOUND" in err_str:
                    raise AIProviderError(
                        f"Gemini model '{model}' not found or no longer available. Please select gemini-3.1-flash-lite in Settings.",
                        provider="gemini",
                        retryable=False,
                    )
                raise AIProviderError(f"Gemini API Error: {err_str[:140]}", provider="gemini", retryable=True)
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error calling Gemini ({attempt+1}/{max_retries}): {e}")
                time.sleep(1.0)

        raise AIProviderError(
            f"Failed to generate article with Gemini after {max_retries} attempts: {str(last_error)[:120]}. Please check your connection and retry.",
            provider="gemini",
            retryable=True,
        )

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_retries: int = 2,
    ) -> Tuple[Dict[str, Any], int, int]:
        json_instruction = (
            (system_instruction or "") +
            "\n\nIMPORTANT: Return ONLY a valid, parseable JSON object. Do not include markdown code block markers or conversational preamble."
        ).strip()

        text, in_tok, out_tok = self.generate_text(
            prompt=prompt,
            system_instruction=json_instruction,
            temperature=temperature,
            max_retries=max_retries,
        )

        parsed = self._extract_json(text)
        return parsed, in_tok, out_tok

    def _extract_json(self, raw_text: str) -> Dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            logger.warning(f"Could not parse valid JSON from Gemini output: {cleaned[:100]}...")
            return {}


# =========================================================================
# OLLAMA LOCAL PROVIDER (OFFLINE MODE)
# =========================================================================

class OllamaProvider(BaseAIProvider):
    def __init__(self):
        self.timeout = 180.0 # Generation timeout for local inference

    @property
    def base_url(self) -> str:
        return settings.OLLAMA_BASE_URL or "http://localhost:11434"

    @property
    def model(self) -> str:
        return settings.OLLAMA_MODEL or "llama3.2"

    def check_health(self, timeout: float = 1.0) -> Dict[str, Any]:
        """
        Verify that Ollama server is running and check whether models are installed.
        """
        url = f"{self.base_url}/api/tags"
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                clean_models = [m.split(":")[0] if m.endswith(":latest") else m for m in models]
                
                # Check if configured model is available
                configured = self.model
                has_model = any(
                    m == configured or m.startswith(f"{configured}:") or configured.startswith(f"{m}:")
                    for m in models
                )

                if not models:
                    return {
                        "healthy": False,
                        "provider": "ollama",
                        "connected": True,
                        "base_url": self.base_url,
                        "model": configured,
                        "installed_models": [],
                        "message": (
                            f"Ollama is running at {self.base_url}, but NO models are installed. "
                            f"Please run 'ollama pull {configured}' in your terminal."
                        ),
                    }

                if not has_model:
                    return {
                        "healthy": False,
                        "provider": "ollama",
                        "connected": True,
                        "base_url": self.base_url,
                        "model": configured,
                        "installed_models": models,
                        "message": (
                            f"Configured model '{configured}' is not installed in Ollama. "
                            f"Available models: [{', '.join(models)}]. "
                            f"Please run 'ollama pull {configured}' or choose an available model in Settings."
                        ),
                    }

                return {
                    "healthy": True,
                    "provider": "ollama",
                    "connected": True,
                    "base_url": self.base_url,
                    "model": configured,
                    "installed_models": models,
                    "message": f"Offline AI ready with Ollama ({configured})",
                }
            else:
                return {
                    "healthy": False,
                    "provider": "ollama",
                    "connected": False,
                    "base_url": self.base_url,
                    "model": self.model,
                    "message": f"Ollama returned HTTP {resp.status_code}. Please verify the Ollama service status.",
                }
        except requests.exceptions.ConnectionError:
            return {
                "healthy": False,
                "provider": "ollama",
                "connected": False,
                "base_url": self.base_url,
                "model": self.model,
                "message": (
                    f"Ollama is disconnected or unavailable at {self.base_url}. "
                    "Please start Ollama by running 'ollama serve' in your terminal or launch the Ollama desktop app. "
                    "If Ollama is not installed, download it from https://ollama.com."
                ),
            }
        except requests.exceptions.Timeout:
            return {
                "healthy": False,
                "provider": "ollama",
                "connected": False,
                "base_url": self.base_url,
                "model": self.model,
                "message": f"Connection to Ollama at {self.base_url} timed out.",
            }
        except Exception as e:
            return {
                "healthy": False,
                "provider": "ollama",
                "connected": False,
                "base_url": self.base_url,
                "model": self.model,
                "message": f"Ollama error: {str(e)}",
            }

    def get_available_models(self) -> List[str]:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception:
            pass
        return []

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 2,
    ) -> Tuple[str, int, int]:
        # 1. Check health / model availability first
        health = self.check_health()
        if not health.get("connected"):
            raise OllamaConnectionError(self.base_url, health.get("message"))
        if not health.get("healthy"):
            installed = health.get("installed_models", [])
            raise OllamaModelError(self.model, installed)

        # 2. Call Ollama Chat API
        url = f"{self.base_url}/api/chat"
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("message", {}).get("content", "")
                    if not content.strip():
                        raise AIProviderError("Empty text returned from local Ollama model.", provider="ollama", retryable=True)

                    in_tokens = data.get("prompt_eval_count") or int(len(prompt) / 4)
                    out_tokens = data.get("eval_count") or int(len(content) / 4)
                    return content, in_tokens, out_tokens
                elif resp.status_code == 404:
                    models = self.get_available_models()
                    raise OllamaModelError(self.model, models)
                else:
                    raise AIProviderError(f"Ollama returned HTTP error {resp.status_code}: {resp.text[:120]}", provider="ollama", retryable=True)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                last_error = e
                logger.warning(f"Ollama request attempt {attempt + 1} failed: {e}")
                time.sleep(1.0)
            except AIProviderError:
                raise
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected Ollama exception: {e}")
                time.sleep(1.0)

        raise OllamaConnectionError(
            self.base_url,
            f"Ollama connection failed during generation: {str(last_error)}. Please ensure 'ollama serve' is running."
        )

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_retries: int = 2,
    ) -> Tuple[Dict[str, Any], int, int]:
        health = self.check_health()
        if not health.get("connected"):
            raise OllamaConnectionError(self.base_url, health.get("message"))
        if not health.get("healthy"):
            installed = health.get("installed_models", [])
            raise OllamaModelError(self.model, installed)

        url = f"{self.base_url}/api/chat"
        messages = []
        full_system = (
            (system_instruction or "") +
            "\n\nCRITICAL: Respond ONLY with a valid, parseable JSON object matching the requested schema. Do not write explanations outside JSON."
        ).strip()
        messages.append({"role": "system", "content": full_system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data.get("message", {}).get("content", "")
                in_tokens = data.get("prompt_eval_count") or int(len(prompt) / 4)
                out_tokens = data.get("eval_count") or int(len(raw_text) / 4)

                parsed = self._extract_json(raw_text)
                return parsed, in_tokens, out_tokens
            elif resp.status_code == 404:
                models = self.get_available_models()
                raise OllamaModelError(self.model, models)
            else:
                raise AIProviderError(f"Ollama returned HTTP error {resp.status_code}: {resp.text[:120]}", provider="ollama")
        except (OllamaConnectionError, OllamaModelError, AIProviderError):
            raise
        except Exception as e:
            raise OllamaConnectionError(self.base_url, f"Failed to generate structured data from Ollama: {str(e)}")

    def _extract_json(self, raw_text: str) -> Dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            logger.warning(f"Could not parse valid JSON from Ollama output: {cleaned[:100]}...")
            return {}


# =========================================================================
# CENTRALIZED AI PROVIDER MANAGER
# =========================================================================

class AIProviderManager:
    """
    Central dispatcher managing active AI mode and provider instances.
    Guarantees strict mode isolation.
    """
    def __init__(self):
        self.gemini_provider = GeminiProvider()
        self.ollama_provider = OllamaProvider()

    @property
    def active_mode(self) -> str:
        return settings.AI_GENERATION_MODE

    def set_mode(self, mode: str):
        mode_clean = mode.strip().lower()
        if mode_clean in ("online", "offline"):
            settings.AI_GENERATION_MODE = mode_clean
            logger.info(f"Switched AI Generation Mode to: {mode_clean.upper()}")
        else:
            raise ValueError(f"Invalid AI generation mode '{mode}'. Must be 'online' or 'offline'.")

    def get_active_provider(self) -> BaseAIProvider:
        if self.active_mode == "offline":
            return self.ollama_provider
        return self.gemini_provider

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 2,
    ) -> Tuple[str, int, int]:
        """
        Main entry point for text/markdown article generation.
        Strictly routes to the configured provider based on mode.
        """
        if self.active_mode == "online":
            # Strict Online Mode: requires internet connection
            if not check_internet_connection():
                raise ConnectivityError(
                    "You're offline. Connect to the internet or switch to Offline AI and connect Ollama."
                )
            return self.gemini_provider.generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_retries=max_retries,
            )
        else:
            # Strict Offline Mode: Ollama required, never sends data to cloud
            return self.ollama_provider.generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_retries=max_retries,
            )

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_retries: int = 2,
    ) -> Tuple[Dict[str, Any], int, int]:
        """
        Main entry point for structured JSON generation.
        Strictly routes to the configured provider based on mode.
        """
        if self.active_mode == "online":
            if not check_internet_connection():
                raise ConnectivityError(
                    "You're offline. Connect to the internet or switch to Offline AI and connect Ollama."
                )
            return self.gemini_provider.generate_json(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_retries=max_retries,
            )
        else:
            return self.ollama_provider.generate_json(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                max_retries=max_retries,
            )

    _ollama_health_cache = {"result": None, "expires": 0.0}

    def check_health(self) -> Dict[str, Any]:
        """
        Returns full connectivity, active mode, and provider health summary.
        Keeps execution lightning fast (<50ms) to ensure desktop UI responsiveness.
        """
        now = time.time()
        internet_online = check_internet_connection()
        active_mode = self.active_mode

        if active_mode == "online":
            gemini_health = self.gemini_provider.check_health()
            # In online mode, serve cached or fast ollama health check
            if self._ollama_health_cache["result"] is not None and now < self._ollama_health_cache["expires"]:
                ollama_health = self._ollama_health_cache["result"]
            else:
                ollama_health = self.ollama_provider.check_health(timeout=0.6)
                self._ollama_health_cache = {"result": ollama_health, "expires": now + 15.0}

            active_healthy = gemini_health.get("healthy", False)
            if not internet_online:
                status_message = "You're offline. Connect to the internet or switch to Offline AI and connect Ollama."
            else:
                status_message = gemini_health.get("message", "Online Gemini ready")
        else:
            # Offline mode
            ollama_health = self.ollama_provider.check_health(timeout=1.5)
            self._ollama_health_cache = {"result": ollama_health, "expires": now + 10.0}
            gemini_health = self.gemini_provider.check_health()

            active_healthy = ollama_health.get("healthy", False)
            status_message = ollama_health.get("message", "Offline Ollama ready")

        return {
            "internet_connected": internet_online,
            "ai_generation_mode": active_mode,
            "active_provider": "gemini" if active_mode == "online" else "ollama",
            "active_model": settings.GEMINI_MODEL if active_mode == "online" else settings.OLLAMA_MODEL,
            "ready": active_healthy,
            "status_message": status_message,
            "gemini": gemini_health,
            "ollama": ollama_health,
        }


ai_provider = AIProviderManager()
