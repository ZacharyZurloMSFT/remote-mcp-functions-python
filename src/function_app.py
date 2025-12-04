import json
import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional

import azure.functions as func

from content_understanding_service import (
    ContentUnderstandingService,
    ContentUnderstandingServiceError,
    InvoiceAnalysisRequest,
)
from weather_service import WeatherService, WeatherServiceError

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Constants for tool argument names
_CITY_NAME_PROPERTY_NAME = "city"
_COUNTRY_CODE_PROPERTY_NAME = "countryCode"
_INVOICE_FILE_NAME_PROPERTY_NAME = "fileName"
_INVOICE_CONTENT_TYPE_PROPERTY_NAME = "contentType"
_INVOICE_ANALYZER_ID_PROPERTY_NAME = "analyzerId"
_INVOICE_ID_PROPERTY_NAME = "invoiceId"


class ToolProperty:
    def __init__(self, property_name: str, property_type: str, description: str, required: bool = True):
        self.propertyName = property_name
        self.propertyType = property_type
        self.description = description
        self.required = required

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "propertyName": self.propertyName,
            "propertyType": self.propertyType,
            "description": self.description,
        }
        if not self.required:
            payload["required"] = False
        return payload


# Define the tool properties using the ToolProperty class
tool_properties_get_weather_object = [
    ToolProperty(_CITY_NAME_PROPERTY_NAME, "string", "City or town to retrieve weather for."),
    ToolProperty(
        _COUNTRY_CODE_PROPERTY_NAME,
        "string",
        "Optional two-letter ISO 3166 country code to disambiguate the location (e.g. US, GB).",
        required=False,
    ),
]

# Convert the tool properties to JSON
tool_properties_get_weather_json = json.dumps([prop.to_dict() for prop in tool_properties_get_weather_object])

tool_properties_analyze_invoice_object = [
    ToolProperty(
        _INVOICE_FILE_NAME_PROPERTY_NAME,
        "string",
        "File located under the data directory (for example invoice_sample.jpg).",
    ),
    ToolProperty(
        _INVOICE_ID_PROPERTY_NAME,
        "string",
        "Optional relative path override when referencing nested folders inside data/.",
        required=False,
    ),
    ToolProperty(
        _INVOICE_ANALYZER_ID_PROPERTY_NAME,
        "string",
        "Optional Content Understanding analyzer ID. Defaults to prebuilt-invoice when omitted.",
        required=False,
    ),
    ToolProperty(
        _INVOICE_CONTENT_TYPE_PROPERTY_NAME,
        "string",
        "Optional MIME type override, e.g. application/pdf or image/png.",
        required=False,
    ),
]

tool_properties_analyze_invoice_json = json.dumps(
    [prop.to_dict() for prop in tool_properties_analyze_invoice_object]
)


weather_service = WeatherService()
content_understanding_service = ContentUnderstandingService()

_DATA_DIRECTORY = (Path(__file__).resolve().parent.parent / "data").resolve()


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="Hello world.",
    toolProperties="[]",
)
def hello_mcp(context) -> None:
    """
    A simple function that returns a greeting message.

    Args:
        context: The trigger context (not used in this function).

    Returns:
        str: A greeting message.
    """
    return "Hello I am MCPTool!"


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="get_weather",
    description="Get current weather conditions for a specific city, including temperature, humidity, wind, and precipitation.",
    toolProperties=tool_properties_get_weather_json,
)
def get_weather(context) -> str:
    """Retrieve near real-time weather readings for a requested location."""

    try:
        content = json.loads(context)
        arguments = content.get("arguments", {})
        city_name = (arguments.get(_CITY_NAME_PROPERTY_NAME) or "").strip()
        country_code = arguments.get(_COUNTRY_CODE_PROPERTY_NAME)
    except (TypeError, json.JSONDecodeError) as err:
        logging.exception("Failed to decode tool arguments for get_weather")
        return json.dumps({"error": "Invalid request payload", "details": str(err)})

    if not city_name:
        return json.dumps({"error": "City name is required"})

    try:
        weather_summary = weather_service.get_weather(city_name=city_name, country_code=country_code)
    except WeatherServiceError as exc:
        logging.warning("Weather lookup failed for %s (%s)", city_name, country_code or "no country")
        return json.dumps({"error": "Unable to retrieve weather information", "details": str(exc)})

    return json.dumps(weather_summary)


@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="analyze_invoice",
    description="Extract structured fields and line items from an invoice using Azure AI Content Understanding.",
    toolProperties=tool_properties_analyze_invoice_json,
)
def analyze_invoice(context) -> str:
    """Analyze an invoice document stored under the data directory."""

    try:
        content = json.loads(context)
        arguments: Dict[str, Any] = content.get("arguments", {})
    except (TypeError, json.JSONDecodeError) as err:
        logging.exception("Failed to decode tool arguments for analyze_invoice")
        return json.dumps({"error": "Invalid request payload", "details": str(err)})

    invoice_id = _get_trimmed_argument(arguments, _INVOICE_ID_PROPERTY_NAME)
    file_name_argument = _get_trimmed_argument(arguments, _INVOICE_FILE_NAME_PROPERTY_NAME)
    content_type = _get_trimmed_argument(arguments, _INVOICE_CONTENT_TYPE_PROPERTY_NAME)

    source_identifier = invoice_id or file_name_argument
    if not source_identifier:
        return json.dumps(
            {
                "error": "fileName is required",
                "details": "Provide the file name relative to the data directory, for example invoice_sample.jpg.",
            }
        )

    try:
        stored_invoice = _load_invoice_from_data(source_identifier)
    except FileNotFoundError:
        logging.error("Invoice '%s' was not found under %s", source_identifier, _DATA_DIRECTORY)
        return json.dumps(
            {
                "error": "Invoice sample not found",
                "details": f"Add {source_identifier} to the data directory.",
            }
        )
    except ValueError as exc:
        logging.error("Invalid invoice identifier '%s': %s", source_identifier, exc)
        return json.dumps({"error": "Invalid file reference", "details": str(exc)})

    file_name = file_name_argument or stored_invoice["file_name"]
    if not content_type and stored_invoice["content_type"]:
        content_type = stored_invoice["content_type"]

    analyzer_id = _get_trimmed_argument(arguments, _INVOICE_ANALYZER_ID_PROPERTY_NAME)
    logging.info(
        "Starting invoice analysis: file=%s, path=%s, contentType=%s, analyzerId=%s",
        file_name,
        stored_invoice["path"],
        content_type or stored_invoice["content_type"],
        analyzer_id or "<default>",
    )

    request = InvoiceAnalysisRequest(
        file_path=stored_invoice["path"],
        content_type=content_type or None,
        file_name=file_name or None,
        analyzer_id=analyzer_id or None,
    )

    try:
        analysis = content_understanding_service.analyze_invoice(request)
    except ContentUnderstandingServiceError as exc:
        logging.error("Invoice analysis failed: %s", exc)
        return json.dumps({"error": "Unable to analyze invoice", "details": str(exc)})

    return json.dumps(analysis)


def _get_trimmed_argument(arguments: Dict[str, Any], key: str) -> Optional[str]:
    value = arguments.get(key)
    if isinstance(value, str):
        return value.strip()
    return None


def _load_invoice_from_data(invoice_id: str) -> Dict[str, Optional[str]]:
    sanitized_id = (invoice_id or "").strip()
    if not sanitized_id:
        raise ValueError("invoiceId must be a relative path inside the data directory.")

    request_path = Path(sanitized_id)
    if request_path.is_absolute() or ".." in request_path.parts:
        raise ValueError("invoiceId must not be absolute or traverse outside the data directory.")

    request_parts = list(request_path.parts)
    data_segment = _DATA_DIRECTORY.name.lower()
    if request_parts and request_parts[0].lower() == data_segment:
        if len(request_parts) == 1:
            raise ValueError("invoiceId must specify a file within the data directory.")
        request_path = Path(*request_parts[1:])

    data_root = _DATA_DIRECTORY
    target_path = (data_root / request_path).resolve()
    if not str(target_path).startswith(str(data_root)):
        raise ValueError("invoiceId must resolve inside the data directory.")

    if not target_path.exists():
        raise FileNotFoundError(target_path)

    guessed_type, _ = mimetypes.guess_type(target_path.name)

    logging.debug(
        "Resolved invoiceId '%s' to %s (contentType=%s)",
        sanitized_id,
        target_path,
        guessed_type,
    )

    return {"path": target_path, "content_type": guessed_type, "file_name": target_path.name}
