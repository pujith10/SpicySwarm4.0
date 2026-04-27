import os
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

def ingest_docs(file_path: str):
    print(f"Ingesting {file_path}...")
    
    # Read DOCX
    doc = Document(file_path)
    text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
    
    # Split text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_text(text)
    print(f"Created {len(chunks)} chunks.")
    
    # Embed and store
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = FAISS.from_texts(chunks, embeddings)
    
    # Save index
    index_path = os.getenv("FAISS_INDEX_PATH", "./data/faiss.index")
    vectorstore.save_local(index_path)
    print(f"Saved FAISS index to {index_path}")

if __name__ == "__main__":
    # For initial run, we use the provided docx
    docx_path = "../HAA_Complete_Documentation.docx"
    if os.path.exists(docx_path):
        ingest_docs(docx_path)
    else:
        print(f"File not found: {docx_path}")
