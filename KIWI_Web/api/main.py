from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import batch_prep
from routers import exports, monitor, projects, queue, scan, settings

app = FastAPI(title="KIWI API Wrapper")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api")
app.include_router(scan.router, prefix="/api")
app.include_router(queue.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(exports.router, prefix="/api")
app.include_router(monitor.router, prefix="/api")
app.include_router(batch_prep.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

