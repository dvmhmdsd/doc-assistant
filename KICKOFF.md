# AI Document Assistant — Project Kickoff

## Problem Statement

Legal-tech companies handle hundreds of PDF and DOCX agreements daily. Reviewing them manually is slow and error-prone. This project builds an AI-powered assistant that lets users upload documents and ask questions in plain language, getting accurate answers instantly.

---

## What We Are Building

A self-contained web application where a user can:

1. Upload a PDF or DOCX file
2. Ask natural language questions about it
3. Receive streamed AI-generated answers
4. Continue asking follow-up questions (conversation history maintained)

---

## Core Concept: RAG (Retrieval-Augmented Generation)

Instead of sending the entire document to the LLM (expensive, limited by context window), we use a RAG pipeline:

```
INGESTION
---------
Upload file
    → Parse text from PDF / DOCX
    → Split text into overlapping chunks (~500 tokens each)
    → Convert chunks to vectors (embeddings)
    → Store vectors in ChromaDB (local vector database)

QUERYING
--------
User asks a question
    → Convert question to a vector
    → Find the top-K most similar chunks in ChromaDB
    → Send question + relevant chunks to the LLM
    → Stream the answer back to the user
```

---

## Architecture: Custom Clean Architecture

We deliberately avoid LangChain/LlamaIndex to keep the code readable and to clearly demonstrate OOP + design patterns.

### Layer Structure

```
doc-assistant/
├── src/
│   ├── parsers/          # Strategy + Factory pattern — handles PDF and DOCX
│   ├── chunker/          # Splits text into searchable pieces
│   ├── embeddings/       # Interface + implementations (local or OpenAI)
│   ├── vector_store/     # Repository pattern — ChromaDB adapter
│   ├── llm/              # Interface + implementations (Claude or OpenAI)
│   ├── services/         # Ingestion service + QA service (Facade pattern)
│   ├── history/          # Conversation store (in-memory, swappable)
│   ├── api/              # FastAPI routes + static HTML/JS chat UI
│   └── config.py         # All settings, driven by .env
├── tests/
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

### Design Patterns Applied

| Pattern    | Location                  | Purpose                                           |
|------------|---------------------------|---------------------------------------------------|
| Strategy   | `parsers/`                | PDF and DOCX parsing as interchangeable behaviors |
| Factory    | `parsers/factory.py`      | Creates the right parser from the file extension  |
| Repository | `vector_store/`, `history/` | Abstracts storage — swap ChromaDB or memory easily |
| Facade     | `services/qa_service.py`  | Hides retrieve + LLM complexity behind one method |

---

## Key Interfaces (the contracts between layers)

```python
# Every parser implements this
class DocumentParser:
    def parse(self, file_path: str) -> str: ...

# Every embedding provider implements this
class EmbeddingProvider:
    def embed(self, texts: list[str]) -> list[list[float]]: ...

# Every vector store implements this
class VectorStore:
    def add(self, chunks: list[str], embeddings: list[list[float]]) -> None: ...
    def search(self, query_embedding: list[float], k: int) -> list[str]: ...

# Every LLM client implements this
class LLMClient:
    async def stream_chat(self, messages: list[dict]) -> AsyncGenerator[str]: ...

# Every conversation store implements this
class ConversationStore:
    def add(self, session_id: str, role: str, content: str) -> None: ...
    def get(self, session_id: str) -> list[dict]: ...
```

---

## API Surface

| Method | Endpoint              | Description                              |
|--------|-----------------------|------------------------------------------|
| POST   | `/upload`             | Upload PDF/DOCX, returns `document_id`   |
| POST   | `/ask`                | Ask a question, returns SSE stream       |
| GET    | `/history/{session_id}` | Returns conversation history           |
| GET    | `/`                   | Serves the chat UI                       |

---

## Technology Stack

| Concern          | Choice                        | Why                                      |
|------------------|-------------------------------|------------------------------------------|
| Web framework    | FastAPI                       | Async, streaming support, auto docs      |
| Vector store     | ChromaDB                      | File-based, no separate server needed    |
| PDF parsing      | PyMuPDF (fitz)                | Fast, reliable                           |
| DOCX parsing     | python-docx                   | Standard library for Word files          |
| Embeddings       | sentence-transformers (default) | Runs locally, no API key required      |
| LLM (default)    | Anthropic Claude              | Best-in-class reasoning                  |
| LLM (alt)        | OpenAI GPT-4o                 | Configurable swap via .env               |
| Containerization | Docker + docker-compose       | One-command setup                        |

---

## Configuration (.env)

```env
LLM_PROVIDER=anthropic        # or: openai
EMBEDDING_PROVIDER=local      # or: openai
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K_RESULTS=5
```

---

## Bonus Features

- **Streaming responses** — answers appear word-by-word via Server-Sent Events (SSE)
- **Conversation history** — follow-up questions retain context from the session
- **Docker support** — `docker compose up` runs the full stack

---

## Success Criteria

- [ ] User can upload a PDF or DOCX and get a `document_id`
- [ ] User can ask a question and receive a streamed answer
- [ ] Follow-up questions use conversation history
- [ ] Switching `LLM_PROVIDER` or `EMBEDDING_PROVIDER` in `.env` works without code changes
- [ ] `docker compose up` starts the app on `localhost:8000`
- [ ] Unit tests cover parsers, chunker, and services

---

## What's Next

1. Scaffold project structure and install dependencies
2. Implement parsers (PDF + DOCX) with Factory
3. Implement chunker
4. Implement embeddings (local + OpenAI)
5. Implement ChromaDB vector store
6. Implement LLM clients (Claude + OpenAI) with streaming
7. Build ingestion and QA services
8. Wire up FastAPI routes + SSE streaming
9. Build minimal HTML/JS chat UI
10. Write Dockerfile + docker-compose
11. Write README with setup instructions and sample Q&A
