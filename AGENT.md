# DocETL Codebase Guide

## Commands
- **Test**: `poetry run pytest` (all tests), `poetry run pytest tests/basic` (basic tests), `poetry run pytest -k "test_name"` (single test)
- **Lint**: `poetry run ruff check docetl/* --fix`
- **Type check**: `poetry run mypy`
- **Install**: `poetry install --all-extras`
- **UI dev**: `make run-ui-dev` (starts backend + frontend)
- **Docker**: `make docker` (full playground setup)

## Architecture
- **Core**: `docetl/` - Pipeline execution (`runner.py`), operations (`operations/`), optimization (`optimizer.py`)
- **Reasoning Optimizer**: `docetl/reasoning_optimizer/` - LLM-based pipeline optimization with directives
- **Server**: `server/app/` - FastAPI backend for web UI with REST endpoints
- **Website**: `website/` - Next.js frontend (DocWrangler playground)
- **Operations**: Plugin-based system with BaseOperation abstract class, registered via Poetry plugins

## Code Style
- **Imports**: `from typing import Dict, List, Optional` (prefer explicit over Any)
- **Classes**: Pydantic models with Field descriptors, inherit from BaseOperation for operations
- **Types**: Use type hints extensively, Pydantic schemas for validation
- **Formatting**: Black + isort (profile=black), Ruff linting
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Error handling**: Use exceptions, validate inputs with Pydantic
