import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS

try:
    from ragflow_sdk import RAGFlow
except ImportError:
    print("Error: 'ragflow_sdk' library is not installed. Please install it via 'pip install ragflow-sdk'.", file=sys.stderr)
    sys.exit(1)

app = Flask(__name__)
CORS(app)

RAGFLOW_API_KEY = os.environ.get("RAGFLOW_API_KEY", "ragflow-Y0NTFkZTQ2OWFkZjExZjA4Y2NiMTJkM2")
RAGFLOW_BASE_URL = os.environ.get("RAGFLOW_BASE_URL", "http://localhost:9380")
RAGFLOW_CHAT_ID = os.environ.get("RAGFLOW_CHAT_ID", "")

rag_client = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)

# Cache: reuse chat and session per request context
_chat = None
_session = None


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


@app.route("/api/chat", methods=["POST"])
def chat_ask():
    """Use RAGFlow Chat to get AI-summarized answer with references."""
    data = request.get_json()
    if not data or not data.get("query"):
        return jsonify({"success": False, "error": "query is required"}), 400

    query = data["query"]
    new_session = data.get("new_session", False)

    try:
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
        return jsonify({"success": False, "error": str(e)}), 500


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


if __name__ == "__main__":
    print(f"RAGFlow API Server starting...")
    print(f"RAGFlow Base URL: {RAGFLOW_BASE_URL}")
    app.run(host="0.0.0.0", port=5000, debug=True)
