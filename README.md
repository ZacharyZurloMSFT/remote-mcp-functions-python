<!--
---
name: Remote MCP with Azure Functions (Python)
description: Run a remote MCP server on Azure functions.  
page_type: sample
languages:
- python
- bicep
- azdeveloper
products:
- azure-functions
- azure
urlFragment: remote-mcp-functions-python
---
-->

# Getting Started with Remote MCP Servers using Azure Functions (Python)

This is a quickstart template to easily build and deploy a custom remote MCP server to the cloud using Azure Functions with Python. You can clone/restore/run on your local machine with debugging, and `azd up` to have it in the cloud in a couple minutes. The sample MCP tools include a weather assistant that can report temperature, humidity, wind, and precipitation for cities around the world, plus an invoice analyzer that uses Azure AI Content Understanding to extract structured vendor, total, and line item data from uploaded invoices or PDF/image files included with the repo.

The MCP server is secured by design using keys and HTTPS, and allows more options for OAuth using built-in auth and/or [API Management](https://aka.ms/mcp-remote-apim-auth) as well as network isolation using VNET.

If you're looking for this sample in more languages check out the [.NET/C#](https://github.com/Azure-Samples/remote-mcp-functions-dotnet) and [Node.js/TypeScript](https://github.com/Azure-Samples/remote-mcp-functions-typescript) versions.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Azure-Samples/remote-mcp-functions-python)

Below is the architecture diagram for the Remote MCP Server using Azure Functions:

![Architecture Diagram](architecture-diagram.png)

## Prerequisites

+ [Python](https://www.python.org/downloads/) version 3.11 or higher
+ [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local?pivots=programming-language-python#install-the-azure-functions-core-tools) >= `4.0.7030`
+ [Azure Developer CLI](https://aka.ms/azd)
+ To use Visual Studio Code to run and debug locally:
  + [Visual Studio Code](https://code.visualstudio.com/)
  + [Azure Functions extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions)

## Prepare your local environment

No extra emulators or services are required. The sample calls the public [Open-Meteo](https://open-meteo.com/) APIs to gather weather data, so you just need internet access.

To enable the invoice analyzer locally, supply your Azure AI Content Understanding resource details in `src/local.settings.json` (or via environment variables) before starting the Functions host:

```json
"CONTENT_UNDERSTANDING_ENDPOINT": "https://<your-resource-name>.cognitiveservices.azure.com/",
"CONTENT_UNDERSTANDING_API_KEY": "<your-api-key>",
"CONTENT_UNDERSTANDING_ANALYZER_ID": "prebuilt-invoice"
```

Leave `CONTENT_UNDERSTANDING_API_KEY` empty if the function app should use managed identity instead of an API key. You can also override the default analyzer, API version, and polling behavior with the optional `CONTENT_UNDERSTANDING_API_VERSION`, `CONTENT_UNDERSTANDING_POLL_INTERVAL_SECONDS`, and `CONTENT_UNDERSTANDING_POLL_TIMEOUT_SECONDS` settings.

Sample invoices live under the repository's `data/` folder (for example `data/invoice_sample.jpg`). You can copy your own test files into that directory when running locally, and they will be packaged with the Function app when you deploy with `azd`. Pass the `fileName` argument to reference a file inside the `data/` folder (use paths such as `invoice_sample.jpg`). You can optionally supply `invoiceId` when referencing nested folders or for backward compatibility. Optional `contentType` and `analyzerId` values let you override metadata when needed. The Azure Function now reads invoice bytes directly from disk—no base64 conversion is required or requested from the MCP client.

## Run your MCP Server locally from the terminal
1. Change to the src folder in a new terminal window:

   ```shell
   cd src
   ```

1. Install Python dependencies:

   ```shell
   pip install -r requirements.txt
   ```

>**Note** it is a best practice to create a Virtual Environment before doing the `pip install` to avoid dependency issues/collisions, or if you are running in CodeSpaces.  See [Python Environments in VS Code](https://code.visualstudio.com/docs/python/environments#_creating-environments) for more information.

1. Start the Functions host locally:

   ```shell
   func start
   ```

> **Note** by default this will use the webhooks route: `/runtime/webhooks/mcp/sse`.  Later we will use this in Azure to set the key on client/host calls: `/runtime/webhooks/mcp/sse?code=<system_key>`

## Connect to the *local* MCP server from a client/host

### VS Code - Copilot agent mode

1. **Add MCP Server** from command palette and add URL to your running Function app's SSE endpoint:

    ```shell
    http://0.0.0.0:7071/runtime/webhooks/mcp/sse
    ```

1. **List MCP Servers** from command palette and start the server
1. In Copilot chat agent mode enter a prompt to trigger the tool, e.g., select some code and enter this prompt

    ```plaintext
    Say Hello
    ```

    ```plaintext
    What's the weather in Seattle?
    ```

    ```plaintext
    Give me the temperature, humidity, and wind details for Tokyo, JP
    ```

    ```plaintext
    Extract the vendor, invoice number, due date, total, and line items from invoice.pdf
    ```

1. When prompted to run the tool, consent by clicking **Continue**

1. When you're done, press Ctrl+C in the terminal window to stop the Functions host process.

### MCP Inspector

1. In a **new terminal window**, install and run MCP Inspector

    ```shell
    npx @modelcontextprotocol/inspector
    ```

2. CTRL click to load the MCP Inspector web app from the URL displayed by the app (e.g. http://0.0.0.0:5173/#resources)
3. Set the transport type to `SSE`
4. Set the URL to your running Function app's SSE endpoint and **Connect**:

    ```shell
    http://0.0.0.0:7071/runtime/webhooks/mcp/sse
    ```

>**Note** this step will not work in CodeSpaces.  Please move on to Deploy to Remote MCP.  

5. **List Tools**.  Click on a tool and **Run Tool**.  

## Deploy to Azure for Remote MCP

Run this [azd](https://aka.ms/azd) command to provision the function app, with any required Azure resources, and deploy your code:

```shell
azd up
```

You can opt-in to a VNet being used in the sample. To do so, do this before `azd up`

```bash
azd env set VNET_ENABLED true
```

Additionally, [API Management]() can be used for improved security and policies over your MCP Server, and [App Service built-in authentication](https://learn.microsoft.com/azure/app-service/overview-authentication-authorization) can be used to set up your favorite OAuth provider including Entra.  

If you plan to use the invoice analyzer in Azure, configure your Content Understanding resource values before running `azd up`:

```bash
azd env set CONTENT_UNDERSTANDING_ENDPOINT https://<your-resource-name>.cognitiveservices.azure.com/
azd env set CONTENT_UNDERSTANDING_API_KEY <your-api-key>
azd env set CONTENT_UNDERSTANDING_ANALYZER_ID prebuilt-invoice
```

Leave the API key blank when authenticating with the function app's managed identity and grant that identity access to the Content Understanding resource. If you deploy custom model versions, pass the deployment (analyzer) identifier through `CONTENT_UNDERSTANDING_ANALYZER_ID`.

Optional settings can be configured the same way when you need to override defaults:

```bash
azd env set CONTENT_UNDERSTANDING_API_VERSION 2025-11-01
azd env set CONTENT_UNDERSTANDING_USER_AGENT remote-mcp-functions-python/1.0
azd env set CONTENT_UNDERSTANDING_POLL_INTERVAL_SECONDS 2
azd env set CONTENT_UNDERSTANDING_POLL_TIMEOUT_SECONDS 180
```

### Configure Content Understanding model deployments

Azure Content Understanding GA requires a chat-completion model deployment (for example `gpt-4.1` or `gpt-4o-mini`) and an embeddings deployment (for example `text-embedding-3-large`) to be mapped to your Foundry resource. Without these defaults, the analyze APIs return errors such as `MissingModelDeploymentMapping`. Follow the [official guidance](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/models-deployments) to connect your analyzer to the correct deployments before you run the `analyze_invoice` tool:

1. In the Azure portal, open your Microsoft Foundry resource and configure **Defaults** for both chat-completion and embeddings models, or issue a `PATCH /contentunderstanding/defaults` call with the desired `modelDeployments` payload.
2. (Optional) Override those defaults per analyzer by including the `models.completion` and `models.embedding` entries in your custom analyzer definition if you need different model pairings.

After the defaults are in place, re-run your analyzer request—no code changes are required in the function app, and the service will automatically route your invoices through the configured deployments.

## Connect to your *remote* MCP server function app from a client

Your client will need a key in order to invoke the new hosted SSE endpoint, which will be of the form `https://<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse`. The hosted function requires a system key by default which can be obtained from the [portal](https://learn.microsoft.com/azure/azure-functions/function-keys-how-to?tabs=azure-portal) or the CLI (`az functionapp keys list --resource-group <resource_group> --name <function_app_name>`). Obtain the system key named `mcp_extension`.

### Connect to remote MCP server in MCP Inspector
For MCP Inspector, you can include the key in the URL: 
```plaintext
https://<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse?code=<your-mcp-extension-system-key>
```

### Connect to remote MCP server in VS Code - GitHub Copilot
For GitHub Copilot within VS Code, you should instead set the key as the `x-functions-key` header in `mcp.json`, and you would just use `https://<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse` for the URL. The following example uses an input and will prompt you to provide the key when you start the server from VS Code.  Note [mcp.json](.vscode/mcp.json) has already been included in this repo and will be picked up by VS Code.  Click Start on the server to be prompted for values including `functionapp-name` (in your /.azure/*/.env file) and `functions-mcp-extension-system-key` which can be obtained from CLI command above or API Keys in the portal for the Function App.  

```json
{
    "inputs": [
        {
            "type": "promptString",
            "id": "functions-mcp-extension-system-key",
            "description": "Azure Functions MCP Extension System Key",
            "password": true
        },
        {
            "type": "promptString",
            "id": "functionapp-name",
            "description": "Azure Functions App Name"
        }
    ],
    "servers": {
        "remote-mcp-function": {
            "type": "sse",
            "url": "https://${input:functionapp-name}.azurewebsites.net/runtime/webhooks/mcp/sse",
            "headers": {
                "x-functions-key": "${input:functions-mcp-extension-system-key}"
            }
        },
        "local-mcp-function": {
            "type": "sse",
            "url": "http://0.0.0.0:7071/runtime/webhooks/mcp/sse"
        }
    }
}
```

For MCP Inspector, you can include the key in the URL: `https://<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse?code=<your-mcp-extension-system-key>`.

For GitHub Copilot within VS Code, you should instead set the key as the `x-functions-key` header in `mcp.json`, and you would just use `https://<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse` for the URL. The following example uses an input and will prompt you to provide the key when you start the server from VS Code:

```json
{
    "inputs": [
        {
            "type": "promptString",
            "id": "functions-mcp-extension-system-key",
            "description": "Azure Functions MCP Extension System Key",
            "password": true
        }
    ],
    "servers": {
        "my-mcp-server": {
            "type": "sse",
            "url": "<funcappname>.azurewebsites.net/runtime/webhooks/mcp/sse",
            "headers": {
                "x-functions-key": "${input:functions-mcp-extension-system-key}"
            }
        }
    }
}
```

## Redeploy your code

You can run the `azd up` command as many times as you need to both provision your Azure resources and deploy code updates to your function app.

>[!NOTE]
>Deployed code files are always overwritten by the latest deployment package.

## Clean up resources

When you're done working with your function app and related resources, you can use this command to delete the function app and its related resources from Azure and avoid incurring any further costs:

```shell
azd down
```

## Helpful Azure Commands

Once your application is deployed, you can use these commands to manage and monitor your application:

```bash
# Get your function app name from the environment file
FUNCTION_APP_NAME=$(cat .azure/$(cat .azure/config.json | jq -r '.defaultEnvironment')/env.json | jq -r '.FUNCTION_APP_NAME')
echo $FUNCTION_APP_NAME

# Get resource group 
RESOURCE_GROUP=$(cat .azure/$(cat .azure/config.json | jq -r '.defaultEnvironment')/env.json | jq -r '.AZURE_RESOURCE_GROUP')
echo $RESOURCE_GROUP

# View function app logs
az webapp log tail --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP

# Redeploy the application without provisioning new resources
azd deploy
```

## Source Code

The MCP tools live in `src/function_app.py`. The `get_weather` tool calls into `src/weather_service.py`, which wraps the external API calls, while the `analyze_invoice` tool uses `src/content_understanding_service.py` to reach Azure AI Content Understanding and a local helper that reads invoice samples from the `data/` directory based on the supplied `fileName` (or optional `invoiceId` override). The annotations in `function_app.py` publish both tools through the MCP extension binding while keeping the HTTP trigger secured at the host level.

Here's the relevant code from `function_app.py`:

```python
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
```

And the helper in `weather_service.py` is responsible for translating city names into coordinates and querying [Open-Meteo](https://open-meteo.com/):

```python
class WeatherService:
    _GEOCODING_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search"
    _WEATHER_ENDPOINT = "https://api.open-meteo.com/v1/forecast"

    def get_weather(self, city_name: str, country_code: Optional[str] = None) -> Dict[str, Any]:
        location = self._resolve_location(city_name, country_code)
        weather_payload = self._fetch_weather(location)
        current = weather_payload.get("current", {})
        units = weather_payload.get("current_units", {})

        return {
            "location": {
                "city": location.name,
                "country": location.country,
                "latitude": location.latitude,
                "longitude": location.longitude,
            },
            "conditions": {
                "temperature": {
                    "value": current.get("temperature_2m"),
                    "unit": units.get("temperature_2m"),
                },
                "relativeHumidity": {
                    "value": current.get("relative_humidity_2m"),
                    "unit": units.get("relative_humidity_2m"),
                },
                "wind": {
                    "speed": {
                        "value": current.get("wind_speed_10m"),
                        "unit": units.get("wind_speed_10m"),
                    },
                    "direction": {
                        "value": current.get("wind_direction_10m"),
                        "unit": units.get("wind_direction_10m"),
                    },
                },
                "precipitation": {
                    "value": current.get("precipitation"),
                    "unit": units.get("precipitation"),
                },
                "weatherCode": current.get("weather_code"),
                "time": current.get("time"),
            },
            "attribution": {
                "source": "Open-Meteo",
                "license": "CC BY 4.0",
                "url": "https://open-meteo.com/",
            },
        }
```

Note that the `host.json` file also includes a reference to the experimental bundle, which is required for apps using this feature:

```json
"extensionBundle": {
  "id": "Microsoft.Azure.Functions.ExtensionBundle.Experimental",
  "version": "[4.*, 5.0.0)"
}
```

## Next Steps

- Add [API Management](https://aka.ms/mcp-remote-apim-auth) to your MCP server (auth, gateway, policies, more!)
- Add [built-in auth](https://learn.microsoft.com/en-us/azure/app-service/overview-authentication-authorization) to your MCP server
- Enable VNET using VNET_ENABLED=true flag
- Learn more about [related MCP efforts from Microsoft](https://github.com/microsoft/mcp/tree/main/Resources)
