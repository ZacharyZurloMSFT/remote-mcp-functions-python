"""Helpers for working with Azure AI Content Understanding analyzers.

This module now mirrors the quickstart notebook implementation by instantiating
``AzureContentUnderstandingClient`` and delegating analyze/poll operations to it
instead of sending raw REST requests.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from python.content_understanding_client import (
    AzureContentUnderstandingClient,
    AzureContentUnderstandingClientError,
)


_LOGGER = logging.getLogger(__name__)


class ContentUnderstandingServiceError(RuntimeError):
    """Raised when the Azure AI Content Understanding service returns an error."""


@dataclass(frozen=True)
class InvoiceAnalysisRequest:
    """Represents an invoice analysis request coming from the MCP tool."""

    file_path: Path
    content_type: Optional[str] = None
    file_name: Optional[str] = None
    analyzer_id: Optional[str] = None


@dataclass(frozen=True)
class _ServiceConfig:
    endpoint: str
    analyzer_id: str
    api_version: str
    user_agent: str
    poll_interval_seconds: float
    poll_timeout_seconds: float
    subscription_key: Optional[str]


class ContentUnderstandingService:
    """Thin wrapper around the quickstart's AzureContentUnderstandingClient."""

    _DEFAULT_ANALYZER_ID = "prebuilt-invoice"
    _DEFAULT_API_VERSION = "2025-05-01-preview"
    _DEFAULT_USER_AGENT = "remote-mcp-functions-python/1.0"
    _DEFAULT_POLL_INTERVAL_SECONDS = 2.0
    _DEFAULT_POLL_TIMEOUT_SECONDS = 180.0
    _AUTH_SCOPE = "https://cognitiveservices.azure.com/.default"

    def __init__(self) -> None:
        self._config: Optional[_ServiceConfig] = None
        self._credential: Optional[DefaultAzureCredential] = None
        self._client: Optional[AzureContentUnderstandingClient] = None

    def analyze_invoice(self, request: InvoiceAnalysisRequest) -> Dict[str, Any]:
        """Analyze an invoice document and return the parsed JSON payload."""

        config = self._ensure_configuration()
        client = self._ensure_client(config)

        file_path = request.file_path
        if not file_path.exists():
            _LOGGER.error("Invoice file not found on disk: %s", file_path)
            raise ContentUnderstandingServiceError(f"Invoice file not found: {file_path}")

        analyzer_id = (request.analyzer_id or config.analyzer_id or "").strip()
        if not analyzer_id:
            raise ContentUnderstandingServiceError("Analyzer ID is required for invoice analysis.")

        _LOGGER.info(
            "Submitting invoice '%s' to analyzer '%s' (endpoint=%s, apiVersion=%s, contentType=%s)",
            request.file_name or file_path.name,
            analyzer_id,
            config.endpoint,
            config.api_version,
            request.content_type or "auto-detect",
        )

        try:
            operation = client.begin_analyze(
                analyzer_id,
                file_location=str(file_path),
                content_type=request.content_type,
            )
            result = client.poll_result(
                operation,
                timeout_seconds=config.poll_timeout_seconds,
                polling_interval_seconds=config.poll_interval_seconds,
            )
        except (AzureContentUnderstandingClientError, OSError, ValueError) as exc:
            _LOGGER.error(
                "Analyzer request failed (analyzerId=%s, endpoint=%s, file=%s): %s",
                analyzer_id,
                config.endpoint,
                file_path,
                exc,
            )
            raise ContentUnderstandingServiceError(f"Failed to analyze invoice: {exc}") from exc

        _LOGGER.info(
            "Invoice analysis succeeded (analyzerId=%s, file=%s, bytes=%s)",
            analyzer_id,
            file_path,
            file_path.stat().st_size if file_path.exists() else "unknown",
        )

        return self._build_analysis_response(analyzer_id=analyzer_id, request=request, config=config, result=result)

    # --- internal helpers -----------------------------------------------------------------

    def _ensure_configuration(self) -> _ServiceConfig:
        if self._config:
            return self._config

        endpoint = (os.getenv("CONTENT_UNDERSTANDING_ENDPOINT") or "").strip()
        subscription_key = (os.getenv("CONTENT_UNDERSTANDING_API_KEY") or "").strip() or None
        analyzer_id = (os.getenv("CONTENT_UNDERSTANDING_ANALYZER_ID") or self._DEFAULT_ANALYZER_ID).strip()
        api_version = (os.getenv("CONTENT_UNDERSTANDING_API_VERSION") or self._DEFAULT_API_VERSION).strip()

        if not analyzer_id:
            analyzer_id = self._DEFAULT_ANALYZER_ID

        if not api_version:
            api_version = self._DEFAULT_API_VERSION

        if not endpoint:
            raise ContentUnderstandingServiceError(
                "CONTENT_UNDERSTANDING_ENDPOINT is required to call Azure AI Content Understanding."
            )

        user_agent = (os.getenv("CONTENT_UNDERSTANDING_USER_AGENT") or self._DEFAULT_USER_AGENT).strip()

        poll_interval = self._get_float_env("CONTENT_UNDERSTANDING_POLL_INTERVAL_SECONDS", self._DEFAULT_POLL_INTERVAL_SECONDS)
        poll_timeout = self._get_float_env("CONTENT_UNDERSTANDING_POLL_TIMEOUT_SECONDS", self._DEFAULT_POLL_TIMEOUT_SECONDS)

        self._config = _ServiceConfig(
            endpoint=endpoint,
            analyzer_id=analyzer_id,
            api_version=api_version,
            user_agent=user_agent,
            poll_interval_seconds=poll_interval,
            poll_timeout_seconds=poll_timeout,
            subscription_key=subscription_key,
        )
        _LOGGER.info(
            "Content Understanding config resolved (endpoint=%s, analyzerId=%s, apiVersion=%s, auth=%s, pollInterval=%.1fs, pollTimeout=%.1fs)",
            endpoint,
            analyzer_id,
            api_version,
            "subscription-key" if subscription_key else "managed-identity",
            poll_interval,
            poll_timeout,
        )
        return self._config

    def _ensure_client(self, config: _ServiceConfig) -> AzureContentUnderstandingClient:
        if self._client:
            return self._client

        token_provider = None
        credential = None

        if not config.subscription_key:
            credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
            token_provider = get_bearer_token_provider(credential, self._AUTH_SCOPE)

        self._client = AzureContentUnderstandingClient(
            endpoint=config.endpoint,
            api_version=config.api_version,
            token_provider=token_provider,
            subscription_key=config.subscription_key,
            x_ms_useragent=config.user_agent,
        )

        self._credential = credential
        return self._client

    def _get_float_env(self, name: str, default: float) -> float:
        raw_value = os.getenv(name)
        if raw_value is None:
            return default
        try:
            value = float(raw_value)
            if value <= 0:
                raise ValueError("value must be positive")
            return value
        except ValueError:
            logging.warning("Ignoring invalid %s value '%s'; using default %.2f", name, raw_value, default)
            return default

    def _build_analysis_response(
        self,
        *,
        analyzer_id: str,
        request: InvoiceAnalysisRequest,
        config: _ServiceConfig,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "analyzerId": analyzer_id,
            "apiVersion": config.api_version,
            "contentType": request.content_type,
            "fileName": request.file_name,
            "result": result,
        }


__all__ = [
    "ContentUnderstandingService",
    "ContentUnderstandingServiceError",
    "InvoiceAnalysisRequest",
]
