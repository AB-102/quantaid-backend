# Quantaid Backend

FastAPI backend for Quantaid, an AI-driven quantum computing education platform built at Rice University. It serves lesson content, quizzes, progress tracking and AI explanations to the [Quantaid frontend](https://github.com/AB-102/quantaid-frontend).

## Deployed Site

[https://quantaid.org](https://quantaid.org)

## Development

Requires [uv](https://docs.astral.sh/uv/) and Docker. Python and every dependency are installed by `uv sync`.

```bash
git clone https://github.com/AB-102/quantaid-backend.git
cd quantaid-backend
uv sync
docker run -d --name quantaid-mongo -p 127.0.0.1:27017:27017 mongo:7  # Local MongoDB; later: docker start quantaid-mongo
cp .env.example .env              # Fill in the keys
uv run uvicorn main:app --reload  # http://localhost:8000
```

Local development never uses a shared database: `.env.example` points `MONGODB_URI` and `MONGODB_URI_TEST` at the local container. An empty database is seeded with the default lessons on startup. The frontend's `VITE_BACKEND_URL` should be `http://localhost:8000`.

**API reference:** with the server running, open `http://localhost:8000/docs` for the interactive docs.

## Testing and Checks

Tests run against the database in `MONGODB_URI_TEST`, never `MONGODB_URI`, so they can't touch the data you develop with. Both point at the local container, in separate databases (`quantaid-test` and `quantaid-dev`):

```bash
uv run pytest           # Tests
uv run ruff check .     # Lint
uv run ruff format .    # Format
uv run ty check .       # Type-check
```

CI runs all four on pushes and pull requests to `main`.

## Project Structure

```
main.py          App setup: logging, CORS, startup seeding, routers, /health
config.py        Settings read from .env
routers/         Route handlers: auth, users and progress (/api/me), ai, content, feedback, admin_users, files
schemas/         Pydantic request models, one module per router
services/        Business logic as plain functions (Google sign-in, progress, profile)
dependencies/    Auth dependencies: CurrentUser, OptionalUser, AdminUser
core/            JWT and file-URL helpers
database/        Async MongoDB client and startup seeding
data/            Default lessons and dashboard config
tests/           pytest suite
```

## License

MIT License

## Citation

If you use Quantaid in an academic work, please cite:

> Kevin Hernandez, Tirthak Patel.  
> *Enhancing Early Quantum Computing Education with QuantumAiEd: Bridging the Educational Gap.*  
> SIGCSETS 2025: Proceedings of the 56th ACM Technical Symposium on Computer Science Education V. 2, p. 1755.  
> [https://doi.org/10.1145/3641555.3705028](https://doi.org/10.1145/3641555.3705028)  
> Published: February 18, 2025. ACM.
