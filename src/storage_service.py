"""Utilities for loading invoice documents from Azure Blob Storage."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient, BlobServiceClient


class InvoiceStorageError(RuntimeError):
    """Raised when invoice content cannot be retrieved from storage."""


@dataclass(frozen=True)
class StoredInvoice:
    """Represents invoice bytes and associated metadata."""

    content: bytes
    content_type: Optional[str]
    file_name: str


class InvoiceStorageClient:
    """Minimal client for fetching invoice files from Azure Blob Storage."""

    _CONTAINER_ENV = "INVOICE_STORAGE_CONTAINER_NAME"
    _ACCOUNT_URL_ENV = "INVOICE_STORAGE_ACCOUNT_URL"
    _CONNECTION_STRING_ENV = "INVOICE_STORAGE_CONNECTION_STRING"
    _SAS_TOKEN_ENV = "INVOICE_STORAGE_SAS_TOKEN"

    def __init__(self) -> None:
        self._container_name = (os.getenv(self._CONTAINER_ENV) or "").strip()
        self._connection_string = (os.getenv(self._CONNECTION_STRING_ENV) or "").strip() or None
        self._account_url = (os.getenv(self._ACCOUNT_URL_ENV) or "").strip() or None
        self._sas_token = (os.getenv(self._SAS_TOKEN_ENV) or "").strip() or None
        self._service_client: Optional[BlobServiceClient] = None

    def fetch_invoice(self, invoice_id: str) -> StoredInvoice:
        """Download an invoice blob and return its bytes and metadata."""

        blob_name = (invoice_id or "").strip()
        if not blob_name:
            raise InvoiceStorageError("Invoice ID is required to download from storage.")
        client = self._get_blob_client(blob_name)

        try:
            downloader = client.download_blob()
            data = downloader.readall()
        except ResourceNotFoundError as exc:
            raise InvoiceStorageError(
                f"Invoice '{blob_name}' was not found in storage container '{self._container_name}'."
            ) from exc
        except AzureError as exc:  # pragma: no cover - network failure paths
            raise InvoiceStorageError(f"Failed to download invoice '{blob_name}' from storage: {exc}") from exc

        props = downloader.properties
        content_type = None
        if props and getattr(props, "content_settings", None):
            content_type = props.content_settings.content_type

        file_name = props.name if props and getattr(props, "name", None) else blob_name
        return StoredInvoice(content=data, content_type=content_type, file_name=file_name)

    # --- internal helpers -------------------------------------------------

    def _ensure_container(self) -> None:
        if not self._container_name:
            raise InvoiceStorageError(
                "Set INVOICE_STORAGE_CONTAINER_NAME to the blob container that stores invoices before using invoiceId."
            )

    def _get_blob_client(self, blob_name: str) -> BlobClient:
        self._ensure_container()
        service_client = self._get_service_client()
        return service_client.get_blob_client(container=self._container_name, blob=blob_name)

    def _get_service_client(self) -> BlobServiceClient:
        if self._service_client:
            return self._service_client

        if self._connection_string:
            self._service_client = BlobServiceClient.from_connection_string(self._connection_string)
            return self._service_client

        if not self._account_url:
            raise InvoiceStorageError(
                "Provide either INVOICE_STORAGE_CONNECTION_STRING or INVOICE_STORAGE_ACCOUNT_URL for invoice downloads."
            )

        account_url = self._account_url.rstrip("?")
        credential = None

        if self._sas_token:
            sas = self._sas_token.lstrip("?")
            account_url = f"{account_url}?{sas}"
        else:
            credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)

        self._service_client = BlobServiceClient(account_url=account_url, credential=credential)
        return self._service_client


__all__ = ["InvoiceStorageClient", "InvoiceStorageError", "StoredInvoice"]
