import asyncio
import os
import sys
import json
from typing import Any, List, Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Check if mcp is installed
try:
    from mcp.server.lowlevel import Server
    import mcp.types as types
except ImportError:
    try:
        from mcp.server import Server
        import mcp.types as types
    except ImportError:
        print("Error: 'mcp' library is not installed. Please install it via 'pip install mcp'.", file=sys.stderr)
        sys.exit(1)

# Check if ragflow_sdk is installed
try:
    from ragflow_sdk import RAGFlow
except ImportError:
    print("Error: 'ragflow_sdk' library is not installed. Please install it via 'pip install ragflow-sdk'.", file=sys.stderr)
    sys.exit(1)

# Configuration
RAGFLOW_API_KEY = os.environ.get("RAGFLOW_API_KEY", "ragflow-YOUR-API-KEY")
RAGFLOW_BASE_URL = os.environ.get("RAGFLOW_BASE_URL", "http://localhost:9380")

# Initialize Server
app = Server("ragflow-mcp-test")

# Initialize RAGFlow Client
rag_client = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="retrieve_knowledge",
            description="Retrieve knowledge from RAGFlow knowledge base.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query."
                    },
                    "dataset_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of dataset IDs."
                    },
                     "top_k": {
                        "type": "integer",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="list_datasets",
            description="List all available datasets.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if name == "list_datasets":
        try:
            datasets = rag_client.list_datasets()
            result_text = "Available Datasets:\n"
            for ds in datasets:
                result_text += f"- ID: {ds.id}, Name: {ds.name}\n"
            return [types.TextContent(type="text", text=result_text)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error listing datasets: {str(e)}")]

    if name == "retrieve_knowledge":
        query = arguments.get("query")
        dataset_ids = arguments.get("dataset_ids")
        top_k = arguments.get("top_k", 5)

        if not query:
             return [types.TextContent(type="text", text="Error: Query is required.")]

        try:
            if not dataset_ids:
                try:
                    datasets = rag_client.list_datasets()
                    dataset_ids = [ds.id for ds in datasets]
                except Exception as e:
                     return [types.TextContent(type="text", text=f"Error fetching datasets: {str(e)}")]
            
            if not dataset_ids:
                return [types.TextContent(type="text", text="No datasets found.")]

            chunks = rag_client.retrieve(
                question=query,
                dataset_ids=dataset_ids,
                top_k=top_k
            )
            
            results = []
            if chunks:
                for i, chunk in enumerate(chunks):
                    content = "N/A"
                    if hasattr(chunk, 'content_with_weight'): content = chunk.content_with_weight
                    elif hasattr(chunk, 'content'): content = chunk.content
                    elif isinstance(chunk, dict): content = chunk.get('content_with_weight') or chunk.get('content') or str(chunk)
                    else: content = str(chunk)
                    
                    doc_name = "Unknown"
                    if hasattr(chunk, 'document_name'): doc_name = chunk.document_name
                    elif isinstance(chunk, dict): doc_name = chunk.get('document_name', 'Unknown')
                    
                    results.append(f"--- Result {i+1} ---\nSource: {doc_name}\nContent: {content}\n")
                
                return [types.TextContent(type="text", text="\n".join(results))]
            else:
                 return [types.TextContent(type="text", text="No results found.")]

        except Exception as e:
            return [types.TextContent(type="text", text=f"Error retrieving knowledge: {str(e)}")]

    raise ValueError(f"Tool not found: {name}")

async def main():
    try:
        from mcp.server.stdio import stdio_server
    except ImportError:
        print("Error: stdio_server not found.", file=sys.stderr)
        return

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
