from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.endpoints import router
from app.database import init_db
import uvicorn
import os

app = FastAPI(
    title="Claude Task Automation Server",
    description="HTTP-based system for automating tasks with Claude AI",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")

# Mount static files
# Get project root (parent of app directory)
app_dir = os.path.dirname(__file__)
project_root = os.path.dirname(app_dir)
static_dir = os.path.join(project_root, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/")
async def root():
    """Serve web UI."""
    # Get project root (parent of app directory)
    app_dir = os.path.dirname(__file__)
    project_root = os.path.dirname(app_dir)
    index_file = os.path.join(project_root, "static", "index.html")

    if os.path.exists(index_file):
        return FileResponse(index_file)

    # Fallback to JSON response if UI not available
    return {
        "message": "Claude Task Automation Server",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    uvicorn.run(app, host=host, port=port)
