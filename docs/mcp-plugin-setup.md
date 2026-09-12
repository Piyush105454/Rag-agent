# MCP Plugin Setup

The RAG Assistant exposes its orchestrator as a Model Context Protocol (MCP) server. This allows AI clients like Claude Desktop or Claude Code to use the knowledge base as a tool.

## Prerequisites

- The RAG Assistant backend must be running (the MCP server starts automatically on port 8001 alongside the FastAPI app).
- You must have a valid JWT token generated for your user.

## 1. Connecting Claude Desktop

1. Open your Claude Desktop configuration file:
   - **Mac**: ~/Library/Application Support/Claude/claude_desktop_config.json`n   - **Windows**: %APPDATA%\Claude\claude_desktop_config.json`n
2. Add the SSE connection to the mcpServers block:

`json
{
  "mcpServers": {
    "rag-assistant": {
      "command": "sse",
      "url": "http://localhost:8001/sse"
    }
  }
}
``n*(Note: Claude Desktop currently primarily supports stdio, but SSE support is available via proxy bridges or in specific builds. If using a pure SSE client, use the URL above).*

## 2. Using the Tools

Once connected, your AI client will have access to two tools:

### query_company_docs(question: str, token: str)

Asks a question against the knowledge base.
- **question**: The query to run.
- **token**: Your JWT string.

### list_available_documents(token: str)

Lists all documents visible to the skills/groups embedded in your token.
- **token**: Your JWT string.

## 3. Example Prompt

In your AI client, you can now say:
> "Can you check the company knowledge base to see what our return policy is? My access token is eyJhbGci..."

The AI will automatically invoke the query_company_docs tool, authenticate using your token, and provide an answer strictly grounded in the retrieved documents.