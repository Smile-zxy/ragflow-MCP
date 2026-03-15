import os
import sys
import json
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



# Debug endpoint to check document structure
@app.route("/api/debug/document/<dataset_id>/<document_id>", methods=["GET"])
def debug_document(dataset_id, document_id):
    """Debug: check document info from RAGFlow."""
    import requests
    try:
        headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}"}
        
        # Get document info
        response = requests.get(
            f"{RAGFLOW_BASE_URL}/api/v1/datasets/{dataset_id}/documents/{document_id}",
            headers=headers,
            timeout=10
        )
        
        return jsonify({
            "status_code": response.status_code,
            "response": response.json() if response.status_code == 200 else response.text
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Document download endpoint
@app.route("/api/datasets/<dataset_id>/documents/<document_id>/download", methods=["GET"])
def download_document(dataset_id, document_id):
    """Download a specific document from the knowledge base using RAGFlow SDK."""
    try:
        # Get document name from list
        doc_name = f"{document_id}.pdf"
        try:
            list_response = requests.get(
                f"{RAGFLOW_BASE_URL}/api/v1/datasets/{dataset_id}/documents?page=1&page_size=50",
                headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
                timeout=5
            )
            if list_response.status_code == 200:
                list_data = list_response.json()
                docs = list_data.get("data", [])
                for doc in docs:
                    if doc.get("id") == document_id:
                        doc_name = doc.get("name", doc_name)
                        break
        except Exception:
            pass  # Use default name if this fails

        # Use RAGFlow SDK to download document
        from ragflow_sdk import RAGFlow
        from ragflow_sdk.modules.document import Document
        
        client = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)
        
        # Get the document object
        datasets = client.list_datasets()
        target_dataset = None
        for ds in datasets:
            if ds.id == dataset_id:
                target_dataset = ds
                break
        
        if not target_dataset:
            return jsonify({"success": False, "error": "Dataset not found"}), 404
        
        # List documents to find our document
        documents = target_dataset.list_documents()
        target_doc = None
        for doc in documents:
            if doc.id == document_id:
                target_doc = doc
                break
        
        if not target_doc:
            return jsonify({"success": False, "error": "Document not found"}), 404
        
        # Download the document
        file_content = target_doc.download()
        
        # Determine content type based on file extension
        import os
        ext = os.path.splitext(doc_name)[1].lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.txt': 'text/plain',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
        }
        content_type = content_types.get(ext, 'application/octet-stream')
        
        from flask import Response
        return Response(
            file_content,
            mimetype=content_type,
            headers={
                'Content-Disposition': f'attachment; filename="{doc_name}"',
                'Content-Length': len(file_content)
            }
        )
    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/api/datasets/<dataset_id>/documents/<document_id>/content", methods=["GET"])
def get_document_content(dataset_id, document_id):
    """Get the content/chunks of a specific document."""
    import requests
    try:
        headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}"}

        # First, get document info
        doc_response = requests.get(
            f"{RAGFLOW_BASE_URL}/api/v1/datasets/{dataset_id}/documents/{document_id}",
            headers=headers,
            timeout=10
        )

        doc_name = "Unknown"
        if doc_response.status_code == 200:
            try:
                doc_data = doc_response.json()
                if doc_data.get("code") == 0:
                    doc_name = doc_data.get("data", {}).get("name", "Unknown")
            except Exception:
                pass

        # Get document chunks
        chunks_result = []
        page = 1
        page_size = 100

        while page <= 50:
            try:
                chunks_response = requests.get(
                    f"{RAGFLOW_BASE_URL}/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks?page={page}&page_size={page_size}",
                    headers=headers,
                    timeout=10
                )

                if chunks_response.status_code != 200:
                    break

                try:
                    chunks_data = chunks_response.json()
                except Exception:
                    break

                if chunks_data.get("code") != 0:
                    break

                chunks_list = chunks_data.get("data", {}).get("chunks", [])
                if not chunks_list:
                    break

                for chunk in chunks_list:
                    if isinstance(chunk, dict):
                        chunks_result.append({
                            "id": chunk.get("id"),
                            "content": chunk.get("content", ""),
                            "position": chunk.get("position", ""),
                        })

                if len(chunks_list) < page_size:
                    break
                page += 1
            except Exception as e:
                print(f"Error getting chunks: {e}")
                break

        # If no chunks found, try to get the document content directly
        if not chunks_result and doc_response.status_code == 200:
            try:
                doc_data = doc_response.json()
                if doc_data.get("code") == 0:
                    doc_info = doc_data.get("data", {})
                    chunks_result.append({
                        "id": document_id,
                        "content": doc_info.get("content", ""),
                        "position": "1",
                    })
            except Exception:
                pass

        return jsonify({
            "success": True,
            "data": {
                "name": doc_name,
                "chunks": chunks_result
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
                    timeout=120
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
                    timeout=120
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
@app.route("/api/retrieve-with-summary", methods=["POST"])
def retrieve_with_summary():
    """Retrieve knowledge and use AI to summarize the results."""
    import requests
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

        # First, retrieve the content
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

        if not results:
            return jsonify({
                "success": True,
                "data": [],
                "answer": "未找到相关内容。",
                "summary": "未找到与「" + query + "」相关的内容，无法生成总结。"
            })

        # Build context from retrieved results
        context = "\n\n".join([f"[{r['source']}]\n{r['content']}" for r in results])
        
        # Use AI to summarize
        summary_prompt = f"""请根据以下检索到的内容，对用户的问题「{query}」进行总结和回答。

检索到的内容：
{context}

请给出一个清晰、简洁的回答，并标注信息来源。"""

        # Try to use agent if available
        if _current_agent_id:
            headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}", "Content-Type": "application/json"}
            # Create new session for summary
            response = requests.post(
                f"{RAGFLOW_BASE_URL}/api/v1/agents/{_current_agent_id}/sessions",
                headers=headers,
                json={"name": "Web Summary Session"},
                timeout=120
            )
            if response.status_code == 200:
                result_data = response.json()
                if result_data.get("code") == 0:
                    session_id = result_data.get("data", {}).get("id")
                    # Send summary request
                    response = requests.post(
                        f"{RAGFLOW_BASE_URL}/api/v1/agents/{_current_agent_id}/completions",
                        headers=headers,
                        json={"question": summary_prompt, "stream": False, "session_id": session_id},
                        timeout=120
                    )
                    if response.status_code == 200:
                        result_data = response.json()
                        if result_data.get("code") == 0:
                            summary = result_data.get("data", {}).get("data", {}).get("content", "")
                            return jsonify({
                                "success": True,
                                "data": results,
                                "answer": "\n\n".join([r["content"] for r in results]),
                                "summary": summary
                            })
        
        # Fallback: use RAGFlow chat session
        session = get_or_create_session()
        if session:
            summary = ""
            for msg in session.ask(summary_prompt, stream=False):
                d = msg.to_json()
                summary = d.get("content", "")
            return jsonify({
                "success": True,
                "data": results,
                "answer": "\n\n".join([r["content"] for r in results]),
                "summary": summary
            })
        else:
            # No chat session available, return raw results as summary
            summary = "以下是检索到的相关内容：\n\n" + "\n\n".join([f"【{r['source']}】\n{r['content']}" for r in results[:3]])
            return jsonify({
                "success": True,
                "data": results,
                "answer": "\n\n".join([r["content"] for r in results]),
                "summary": summary
            })

    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/api/server-ip", methods=["GET"])
def get_current_server_ip():
    """Return the server's IP address for frontend configuration."""
    return jsonify({"success": True, "ip": SERVER_IP})


# API endpoint to get chat session messages
@app.route("/api/chat/<chat_id>/messages", methods=["GET"])
def get_chat_messages(chat_id):
    """Get messages from a specific chat session (智能体或知识库)."""
    import requests
    headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}", "Content-Type": "application/json"}

    try:
        # Get session_id from query parameter or use cached session
        session_id = request.args.get('session_id')
        
        # If no session_id provided, try to get it from agent sessions cache
        if not session_id and chat_id in _agent_chat_sessions:
            cached = _agent_chat_sessions[chat_id]
            session_obj = cached.get("session")
            if session_obj:
                session_id = session_obj.id

        if not session_id:
            return jsonify({"success": False, "error": "Session not found"}), 404

        # Try to get messages from agent sessions API first
        try:
            response = requests.get(
                f"{RAGFLOW_BASE_URL}/api/v1/agents/{chat_id}/sessions/{session_id}/messages?page=1&page_size=50",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                messages = data.get("data", [])
                return jsonify({"success": True, "messages": messages})
        except Exception as e:
            print(f"Error getting agent messages via API: {e}")

        # Fallback: try chat sessions API
        try:
            response = requests.get(
                f"{RAGFLOW_BASE_URL}/api/v1/chats/{chat_id}/sessions/{session_id}/messages?page=1&page_size=50",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                messages = data.get("data", [])
                return jsonify({"success": True, "messages": messages})
        except Exception as e:
            print(f"Error getting chat messages via API: {e}")

        return jsonify({"success": True, "messages": []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# FAQ data file path
FAQ_FILE = os.path.join(os.path.dirname(__file__), "data", "faqs.json")


@app.route("/api/faqs", methods=["GET"])
def get_faqs():
    """Get all FAQs from the local file."""
    try:
        if os.path.exists(FAQ_FILE):
            with open(FAQ_FILE, "r", encoding="utf-8") as f:
                faqs = json.load(f)
            return jsonify({"success": True, "data": faqs})
        else:
            return jsonify({"success": True, "data": {}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/faqs", methods=["POST"])
def save_faqs():
    """Save FAQs to the local file."""
    import json
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Ensure data directory exists
        os.makedirs(os.path.dirname(FAQ_FILE), exist_ok=True)

        with open(FAQ_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


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
