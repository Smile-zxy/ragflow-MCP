import os
import sys
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import socket
from dotenv import load_dotenv

# Load .env file
load_dotenv()

try:
    from ragflow_sdk import RAGFlow
except ImportError:
    print("Error: 'ragflow_sdk' library is not installed. Please install it via 'pip install ragflow-sdk'.", file=sys.stderr)
    sys.exit(1)

app = Flask(__name__)
CORS(app)

RAGFLOW_API_KEY = os.environ.get("RAGFLOW_API_KEY", "ragflow-YOUR-API-KEY")
RAGFLOW_BASE_URL = os.environ.get("RAGFLOW_BASE_URL", "http://localhost:9380")
RAGFLOW_CHAT_ID = os.environ.get("RAGFLOW_CHAT_ID", "")

rag_client = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)


# Get server's IP address
def get_server_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

SERVER_IP = get_server_ip()
WEB_DIR = os.path.join(os.path.dirname(__file__), "web")


# Cache: reuse chat and session per request context
_chat = None
_session = None
_current_dataset_ids = None
_current_agent_id = None
_agent_chat_sessions = {}  # Cache chat sessions per agent


def get_chat():
    global _chat
    if _chat:
        return _chat
    if RAGFLOW_CHAT_ID:
        chats = rag_client.list_chats(id=RAGFLOW_CHAT_ID)
    else:
        chats = rag_client.list_chats()
    if not chats:
        return None
    _chat = chats[0]
    return _chat


def get_or_create_session():
    global _session
    if _session:
        return _session
    chat = get_chat()
    if not chat:
        return None
    _session = chat.create_session("web_qa")
    return _session


@app.route("/api/datasets", methods=["GET"])
def list_datasets():
    try:
        datasets = rag_client.list_datasets()
        result = [{"id": ds.id, "name": ds.name} for ds in datasets]
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/datasets/<dataset_id>/documents", methods=["GET"])
def list_dataset_documents(dataset_id):
    """List all documents in a specific dataset."""
    import requests
    try:
        headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}"}
        page = 1
        page_size = 100
        all_docs = []

        while page <= 50:
            response = requests.get(
                f"{RAGFLOW_BASE_URL}/api/v1/datasets/{dataset_id}/documents?page={page}&page_size={page_size}",
                headers=headers,
                timeout=10
            )
            if response.status_code != 200:
                break

            # Check if response is valid JSON
            try:
                data = response.json()
            except Exception:
                break

            # Ensure data is a dict before calling .get()
            if not isinstance(data, dict):
                break

            if data.get("code") != 0:
                break

            # RAGFlow API returns: {"code": 0, "data": {"docs": [...]}}
            # Need to extract "docs" from "data"
            data_obj = data.get("data", {})
            if isinstance(data_obj, dict):
                items = data_obj.get("docs", [])
            else:
                items = []

            # Ensure items is a list before iterating
            if not isinstance(items, list):
                break

            if not items:
                break

            for item in items:
                # Ensure item is a dict before calling .get()
                if not isinstance(item, dict):
                    continue
                all_docs.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "size": item.get("size", 0),
                    "status": item.get("status"),
                    "created_at": item.get("created_at")
                })
            if len(items) < page_size:
                break
            page += 1

        return jsonify({"success": True, "data": all_docs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/chats", methods=["GET"])
def list_chats():
    """List all available knowledge bases (datasets) for search."""
    try:
        datasets = rag_client.list_datasets()
        result = []
        for ds in datasets:
            result.append({"id": ds.id, "name": ds.name})
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500




@app.route("/api/canvas", methods=["GET"])
def list_canvases():
    """List all available agents (canvases) from RAGFlow."""
    import requests
    headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}"}
    result = []
    
    # Method 1: Try /api/v1/agents with pagination
    page = 1
    page_size = 50
    while page <= 100:
        try:
            response = requests.get(
                f"{RAGFLOW_BASE_URL}/api/v1/agents?page={page}&page_size={page_size}&orderby=create_time&desc=true",
                headers=headers, 
                timeout=10
            )
            if response.status_code != 200:
                break
            data = response.json()
            if data.get("code") != 0:
                break
            items = data.get("data", [])
            if not items:
                break
            for item in items:
                result.append({
                    "id": item.get("id"),
                    "name": item.get("title") or item.get("name") or "Unnamed Agent",
                    "description": item.get("description", "")
                })
            if len(items) < page_size:
                break
            page += 1
        except Exception as e:
            print(f"Error on page {page}: {e}")
            break
    
    # Method 2: If no results, try /v1/canvas/listteam
    if not result:
        try:
            response = requests.get(f"{RAGFLOW_BASE_URL}/v1/canvas/listteam?page_size=150", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0 and data.get("data", {}).get("canvas"):
                    for item in data["data"]["canvas"]:
                        result.append({
                            "id": item.get("id"),
                            "name": item.get("title"),
                            "description": item.get("description", "")
                        })
        except Exception as e:
            print(f"Error with listteam: {e}")
    
    # Method 3: Fallback to /v1/canvas/list with pagination
    if not result:
        page = 1
        while page <= 100:
            try:
                response = requests.get(f"{RAGFLOW_BASE_URL}/v1/canvas/list?page={page}&page_size=50", headers=headers, timeout=10)
                if response.status_code != 200:
                    break
                data = response.json()
                if data.get("code") != 0:
                    break
                items = data.get("data", [])
                if not items:
                    break
                for item in items:
                    result.append({
                        "id": item.get("id"),
                        "name": item.get("title"),
                        "description": item.get("description", "")
                    })
                if len(items) < 50:
                    break
                page += 1
            except Exception as e:
                print(f"Error on canvas list page {page}: {e}")
                break
    
    if result:
        return jsonify({"success": True, "data": result})
    else:
        return jsonify({"success": False, "error": "No agents found"}), 500




@app.route("/api/canvas/set", methods=["POST"])
def set_current_canvas():
    """Set the current agent (canvas) and create/fetch its chat session."""
    import requests
    global _current_agent_id, _agent_chat_sessions, _chat, _session

    data = request.get_json()
    agent_id = data.get("agent_id")

    print(f"[DEBUG] canvas/set called with agent_id: {agent_id}")

    if not agent_id:
        return jsonify({"success": False, "error": "agent_id is required"}), 400

    try:
        _current_agent_id = agent_id

        # Check if we already have a session for this agent
        if agent_id in _agent_chat_sessions:
            cached = _agent_chat_sessions[agent_id]
            _session = cached.get("session")
            if _session:
                return jsonify({"success": True, "chat_id": agent_id, "name": cached.get("agent_name", "Agent Session")})

        # Find the agent and get/create its sessions
        headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}"}
        session_obj = None
        agent_name = "Agent Session"
        
        # Try to get agent details
        try:
            response = requests.get(f"{RAGFLOW_BASE_URL}/api/v1/agents/{agent_id}", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    agent_name = data.get("data", {}).get("title", "Agent Session")
        except Exception:
            pass
        
        # Try to list existing sessions for this agent
        try:
            response = requests.get(
                f"{RAGFLOW_BASE_URL}/api/v1/agents/{agent_id}/sessions?page=1&page_size=1&orderby=create_time&desc=true",
                headers=headers, 
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0 and data.get("data"):
                    sessions = data["data"]
                    if sessions:
                        session_obj = sessions[0]
        except Exception as e:
            print(f"Error listing agent sessions: {e}")

        # If no session found, create a new one
        if not session_obj:
            try:
                response = requests.post(
                    f"{RAGFLOW_BASE_URL}/api/v1/agents/{agent_id}/sessions",
                    headers=headers,
                    json={"name": "Web Session"},
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        session_obj = data.get("data")
            except Exception as e:
                print(f"Error creating agent session: {e}")

        if session_obj:
            _session = session_obj
            _agent_chat_sessions[agent_id] = {"session": session_obj, "agent_name": agent_name}
            return jsonify({
                "success": True, 
                "chat_id": agent_id, 
                "name": agent_name,
                "session_id": session_obj.get("id") if isinstance(session_obj, dict) else None
            })
        else:
            return jsonify({"success": False, "error": "Could not get or create agent session"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/chats/set", methods=["POST"])
def set_current_chat():
    """Set the current knowledge base for search."""
    global _current_dataset_ids
    data = request.get_json()
    chat_id = data.get("chat_id")

    if not chat_id:
        return jsonify({"success": False, "error": "chat_id is required"}), 400

    try:
        # Find the dataset by ID
        datasets = rag_client.list_datasets()
        selected_ds = None
        for ds in datasets:
            if ds.id == chat_id:
                selected_ds = ds
                break

        if not selected_ds:
            return jsonify({"success": False, "error": "Dataset not found"}), 404

        _current_dataset_ids = [chat_id]
        return jsonify({"success": True, "name": selected_ds.name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat_ask():
    """Use RAGFlow Chat or Agent to get AI-summarized answer with references."""
    import requests
    data = request.get_json()
    if not data or not data.get("query"):
        return jsonify({"success": False, "error": "query is required"}), 400

    query = data["query"]
    new_session = data.get("new_session", False)
    headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}", "Content-Type": "application/json"}

    try:
        # Check if we have a selected agent
        if _current_agent_id:
            session_id = None

            # Always get the latest session from RAGFlow (not cached)
            # This ensures we use the same session as RAGFlow web interface
            if not new_session:
                try:
                    response = requests.get(
                        f"{RAGFLOW_BASE_URL}/api/v1/agents/{_current_agent_id}/sessions?page=1&page_size=1&orderby=create_time&desc=true",
                        headers=headers,
                        timeout=10
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("code") == 0 and result.get("data"):
                            sessions = result["data"]
                            if sessions:
                                session_id = sessions[0].get("id")
                except Exception as e:
                    print(f"Error getting latest session: {e}")

            # Create new session only if requested or no existing session
            if new_session or not session_id:
                response = requests.post(
                    f"{RAGFLOW_BASE_URL}/api/v1/agents/{_current_agent_id}/sessions",
                    headers=headers,
                    json={"name": "Web Session"},
                    timeout=30
                )
                if response.status_code == 200:
                    result = response.json()
                    if result.get("code") == 0:
                        session_id = result.get("data", {}).get("id")

            if session_id:
                # Send message to agent
                response = requests.post(
                    f"{RAGFLOW_BASE_URL}/api/v1/agents/{_current_agent_id}/completions",
                    headers=headers,
                    json={"question": query, "stream": False, "session_id": session_id},
                    timeout=60
                )
                if response.status_code == 200:
                    result = response.json()
                    if result.get("code") == 0:
                        answer_text = result.get("data", {}).get("data", {}).get("content", "")
                        references = []
                        raw_refs = result.get("data", {}).get("reference", {}).get("chunks", [])
                        for ref in raw_refs:
                            references.append({
                                "source": ref.get("document_name", ref.get("doc_name", "Unknown")),
                                "content": ref.get("content", ref.get("content_with_weight", "")),
                            })
                        return jsonify({
                            "success": True,
                            "answer": answer_text,
                            "references": references
                        })
                    else:
                        return jsonify({"success": False, "error": result.get("message", "Agent error")}), 500
                else:
                    return jsonify({"success": False, "error": f"Agent API error: {response.text}"}), 500
            else:
                return jsonify({"success": False, "error": "No agent session available"}), 500
        
        # Fallback to regular chat session (RAGFlow SDK)
        if new_session:
            global _session
            _session = None

        session = get_or_create_session()
        if not session:
            return jsonify({"success": False, "error": "No chat assistant found in RAGFlow. Please create one first."}), 500

        answer_text = ""
        references = []

        for msg in session.ask(query, stream=False):
            d = msg.to_json()
            answer_text = d.get("content", "")
            raw_refs = d.get("reference", [])
            if raw_refs and isinstance(raw_refs, list):
                for ref in raw_refs:
                    if isinstance(ref, dict):
                        references.append({
                            "source": ref.get("document_name", ref.get("doc_name", "Unknown")),
                            "content": ref.get("content", ref.get("content_with_weight", "")),
                        })

        return jsonify({
            "success": True,
            "answer": answer_text,
            "references": references
        })

    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/api/retrieve", methods=["POST"])
def retrieve_knowledge():
    data = request.get_json()
    if not data or not data.get("query"):
        return jsonify({"success": False, "error": "query is required"}), 400

    query = data["query"]
    dataset_ids = data.get("dataset_ids")
    top_k = data.get("top_k", 5)

    try:
        if not dataset_ids:
            datasets = rag_client.list_datasets()
            dataset_ids = [ds.id for ds in datasets]

        if not dataset_ids:
            return jsonify({"success": True, "data": [], "answer": "No datasets found."})

        results = []

        def extract_chunks(chunks):
            for chunk in chunks:
                content = "N/A"
                if hasattr(chunk, 'content_with_weight'):
                    content = chunk.content_with_weight
                elif hasattr(chunk, 'content'):
                    content = chunk.content
                elif isinstance(chunk, dict):
                    content = chunk.get('content_with_weight') or chunk.get('content') or str(chunk)
                else:
                    content = str(chunk)

                doc_name = "Unknown"
                if hasattr(chunk, 'document_name'):
                    doc_name = chunk.document_name
                elif isinstance(chunk, dict):
                    doc_name = chunk.get('document_name', 'Unknown')

                results.append({"source": doc_name, "content": content})

        try:
            chunks = rag_client.retrieve(question=query, dataset_ids=dataset_ids, top_k=top_k)
            if chunks:
                extract_chunks(chunks)
        except Exception:
            for ds_id in dataset_ids:
                try:
                    chunks = rag_client.retrieve(question=query, dataset_ids=[ds_id], top_k=max(1, top_k // len(dataset_ids)))
                    if chunks:
                        extract_chunks(chunks)
                except Exception:
                    continue

        answer = "\n\n".join([r["content"] for r in results]) if results else "No results found."
        return jsonify({"success": True, "data": results, "answer": answer})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# API endpoint to get server IP
@app.route("/api/server-ip", methods=["GET"])
def get_current_server_ip():
    """Return the server's IP address for frontend configuration."""
    return jsonify({"success": True, "ip": SERVER_IP})


# Static file serving
@app.route("/")
def index():
    """Serve the main QA page."""
    return send_from_directory(WEB_DIR, "qa.html")


@app.route("/<path:filename>")
def serve_static(filename):
    """Serve static files from the web directory."""
    return send_from_directory(WEB_DIR, filename)


if __name__ == "__main__":
    print(f"RAGFlow API Server starting...")
    print(f"RAGFlow Base URL: {RAGFLOW_BASE_URL}")
    print(f"Server IP: {SERVER_IP}")
    print(f"Access the web UI at: http://{SERVER_IP}:5000/")
    app.run(host="0.0.0.0", port=5000, debug=True)
