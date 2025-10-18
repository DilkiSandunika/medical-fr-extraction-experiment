# build_index.py
import llama_index.core as lci
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

# NO NEED FOR API KEY HERE ANYMORE

def build_and_save_index():
    """Builds the vector index from the knowledge base using a local model."""
    print("Building RAG index from knowledge base using a local embedding model...")
    try:
        documents = SimpleDirectoryReader("./data/knowledge_base").load_data()
        if not documents:
            print("No documents found in the knowledge base. Aborting.")
            return

        # *** THIS IS THE KEY CHANGE ***
        # Tell LlamaIndex to use a free, local model instead of OpenAI
        index = VectorStoreIndex.from_documents(documents, embed_model="local:BAAI/bge-small-en-v1.5")
        # ***************************

        index.storage_context.persist("./index_storage")
        print("Index built and saved successfully to './index_storage'.")
    except Exception as e:
        print(f"An error occurred while building the index: {e}")

if __name__ == "__main__":
    build_and_save_index()