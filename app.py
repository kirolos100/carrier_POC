# app.py
import logging
import os
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, request
from azure.core.credentials import AzureKeyCredential
from azure.identity import AzureDeveloperCliCredential, DefaultAzureCredential
from dotenv import load_dotenv
from ragtools import attach_rag_tools
from rtmt import RTMiddleTier
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voicerag")

# Initialize Flask app with static folder
app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)



def initialize_components():
    """Initialize Azure components and RAG pipeline"""
    if not os.environ.get("RUNNING_IN_PRODUCTION"):
        logger.info("Running in development mode, loading from .env file")
        load_dotenv()

    # Azure credentials setup
    llm_key = os.environ.get("AZURE_OPENAI_API_KEY")
    search_key = os.environ.get("AZURE_SEARCH_API_KEY")
    
    credential = None
    if not llm_key or not search_key:
        if tenant_id := os.environ.get("AZURE_TENANT_ID"):
            logger.info(f"Using AzureDeveloperCliCredential with tenant_id {tenant_id}")
            credential = AzureDeveloperCliCredential(tenant_id=tenant_id, process_timeout=60)
        else:
            logger.info("Using DefaultAzureCredential")
            credential = DefaultAzureCredential()
    
    llm_credential = AzureKeyCredential(llm_key) if llm_key else credential
    search_credential = AzureKeyCredential(search_key) if search_key else credential

    # Initialize middleware
    rtmt = RTMiddleTier(
        credentials=llm_credential,
        endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        deployment=os.environ["AZURE_OPENAI_REALTIME_DEPLOYMENT"],
        voice_choice=os.environ.get("AZURE_OPENAI_REALTIME_VOICE_CHOICE") or "alloy"
    )
    
    # Configure system message
    rtmt.system_message = """
        You are a helpful assistant. Only answer questions based on information you searched in the knowledge base. 
        Keep answers very short - one sentence if possible. Never reveal technical details about sources.
        1. Always use the 'search' tool first
        2. Use 'report_grounding' to cite sources
        3. If unsure, say you don't know
    """.strip()

    # Attach RAG tools
    attach_rag_tools(
        rtmt,
        credentials=search_credential,
        search_endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        search_index=os.environ["AZURE_SEARCH_INDEX"],
        semantic_configuration=os.environ.get("AZURE_SEARCH_SEMANTIC_CONFIGURATION"),
        identifier_field=os.environ.get("AZURE_SEARCH_IDENTIFIER_FIELD", "chunk_id"),
        content_field=os.environ.get("AZURE_SEARCH_CONTENT_FIELD", "chunk"),
        embedding_field=os.environ.get("AZURE_SEARCH_EMBEDDING_FIELD", "text_vector"),
        title_field=os.environ.get("AZURE_SEARCH_TITLE_FIELD", "title"),
        use_vector_query=os.environ.get("AZURE_SEARCH_USE_VECTOR_QUERY", "true").lower() == "true"
    )
    
    return rtmt

# Initialize components
rtmt = initialize_components()

@app.route('/')
def serve_index():
    """Serve main interface"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/realtime', methods=['POST'])
def handle_realtime():
    """Process user queries through RAG pipeline"""
    try:
        data = request.get_json()
        user_input = data.get('message', '')
        
        if not user_input:
            return jsonify({"error": "Empty message"}), 400
        
        # Process message through RAG system
        response = rtmt.process_query(user_input)
        
        return jsonify({
            "response": response.text,
            "sources": response.sources,
            "voice": rtmt.voice_choice
        })
        
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory(app.static_folder, path)

if __name__ == "__main__":
    app.run(debug=True)
