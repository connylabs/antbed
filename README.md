# Antbed

Antbed is an asynchronous backend system for building Retrieval-Augmented Generation (RAG) applications. It provides a workflow-driven pipeline for document ingestion, processing, and retrieval, leveraging Temporal.io for orchestration.

## Overview

The primary goal of Antbed is to provide a scalable and reliable foundation for managing the document lifecycle in RAG systems. It handles complex, long-running processes such as document chunking, embedding generation, summarization, and indexing into vector databases.

By using Temporal.io, Antbed ensures that these processes are fault-tolerant and observable, making it suitable for production environments where reliability is critical. The system is designed to be modular, with support for multiple vector stores and configurable processing steps.

## Core Features

-   **Temporal.io Workflow Orchestration**: Manages document processing pipelines as durable, stateful workflows, providing reliability and visibility into each step.
-   **Pluggable Vector Storage**: Integrated support for Qdrant and OpenAI Vector Stores, with a clear interface for adding new storage backends.
-   **Configurable Text Processing**: Implements multiple text splitting strategies (e.g., recursive character, semantic) via `langchain_text_splitters`.
-   **Automated Summarization**: Generate multiple, distinct summaries for each document using LLM-based agents. The system can produce different variants, such as a machine-readable summary designed to reduce token count for subsequent LLM processing while preserving all critical information, and a more descriptive, human-readable "pretty" version. This allows for flexible use of document content in different RAG contexts and enables querying capabilities based on document summaries.
-   **REST API**: A FastAPI-based server provides endpoints for document management, search, and interaction with the workflow engine.
-   **Scalable Architecture**: The clear separation of the API server, database, and Temporal workers allows each component to be scaled independently.
-   **Structured Data Model**: Uses a PostgreSQL database to maintain metadata and relationships between documents, splits, embeddings, and summaries.

## Architecture

Antbed's architecture consists of the following core components:

1.  **API Server**: A FastAPI application that serves as the main entry point for client interactions. It receives API requests for tasks like document uploads and searches and initiates the corresponding Temporal workflows.
2.  **Temporal Cluster**: The orchestration engine responsible for managing the execution of workflows and scheduling activities.
3.  **Temporal Workers**: Processes that host the implementation of workflow activities. These workers execute the business logic, such as calling an LLM for summarization or writing embeddings to a vector database.
4.  **PostgreSQL Database**: Serves as the primary data store for all application metadata, including information about virtual files (`VFiles`), collections, splits, and summaries.
5.  **Vector Database**: Stores document embeddings to enable efficient semantic search. Antbed currently supports Qdrant and OpenAI Vector Stores.
6.  **LLM & Embedding Services**: External APIs (e.g., OpenAI) that are called by Temporal activities to generate text embeddings and summaries.

A typical document ingestion workflow follows this sequence:
`API Request` → `FastAPI Server` → `Temporal Workflow Start` → `Worker Executes Activities (Split, Summarize, Embed)` → `Metadata and Embeddings Stored`.

## Getting Started

### Prerequisites

-   Docker and Docker Compose
-   Python 3.11+ with `uv`
-   A running instance of a Temporal.io cluster
-   A PostgreSQL database
-   A Qdrant instance (if using the Qdrant vector store)

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/ant31/antbed.git
    cd antbed
    ```

2.  Install dependencies:
    ```bash
    uv pip install -e .
    ```

### Configuration

Configuration is managed through a `config.yaml` file and can be overridden by environment variables.

1.  Generate a default configuration file:
    ```bash
    antbed default-config > config.yaml
    ```

2.  Modify `config.yaml` with your environment's details, including database connection strings, Temporal server address, and API keys for external services.

### Running the Application

1.  **Apply Database Migrations**:
    The project uses `goose` for schema migrations. The `Makefile` provides a command to apply them.
    ```bash
    make migrate-up
    ```

2.  **Start the Temporal Worker**:
    The worker process must be running to execute workflow activities.
    ```bash
    antbed looper
    ```

3.  **Start the API Server**:
    ```bash
    antbed server
    ```
    The API will be available at `http://localhost:8000` by default. Interactive documentation is available at `http://localhost:8000/docs`.

## API Usage Example

To upload a document for processing, you can send a POST request to the `/upload` endpoint.

1.  Create a JSON file named `upload.json` with the document content and configuration:
    ```json
    {
      "doc": {
        "subject_id": "my-doc-123",
        "subject_type": "external",
        "source_filename": "my_document.txt",
        "pages": [
          "This is the first page of my document.",
          "This is the second page, containing more important information."
        ]
      },
      "collection_name": "my_test_collection",
      "summarize": true,
      "manager": "qdrant"
    }
    ```

2.  Use `curl` to send the request:
    ```bash
    curl -X POST http://localhost:8000/api/v1/embedding/upload \
    -H "Content-Type: application/json" \
    -d @upload.json
    ```

The API will return a job ID that can be used to track the status of the asynchronous workflow via the `/api/v1/job/status` endpoint.

## Development

### Developer Setup

Install the project in editable mode with development dependencies:
```bash
uv pip install -e ".[dev]"
```

It is recommended to use the pre-commit hooks to maintain code quality:
```bash
pre-commit install
```

### Running Tests

To execute the test suite, run:
```bash
make test
```

### Code Style

The project uses `ruff` for linting and formatting. These checks are enforced by the pre-commit hooks. To run them manually:
```bash
# Check for linting issues
uv run ruff check .

# Format code
uv run ruff format .
```

## Contributing

Contributions are welcome. Please open an issue to discuss your ideas or submit a pull request with your changes.

1.  Fork the repository.
2.  Create a new branch for your feature (`git checkout -b feature/my-new-feature`).
3.  Commit your changes (`git commit -am 'Add some feature'`).
4.  Push to the branch (`git push origin feature/my-new-feature`).
5.  Create a new Pull Request.

## License

This project is licensed under the MIT License.
