from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import settings
from database import init_db
from engine.graphiti_engine import create_graphiti
from routers import sessions
from routers import memory
from routers import messages
from routers import users
from routers import graph
from routers import facts


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.graphiti = create_graphiti(settings)
    await app.state.graphiti.build_indices_and_constraints()
    await init_db()
    yield
    # Shutdown
    await app.state.graphiti.driver.close()


app = FastAPI(
    title="OpenZep",
    description="Self-hosted Zep API-compatible memory service powered by Graphiti",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(sessions.router)
app.include_router(memory.router)
app.include_router(messages.router)
app.include_router(users.router)
app.include_router(graph.router)
app.include_router(facts.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
