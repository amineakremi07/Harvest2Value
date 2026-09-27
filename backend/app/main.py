"""Harvest2Value FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import optimize, scenario, explain, chat


app = FastAPI(title="Harvest2Value API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(optimize.router)
app.include_router(scenario.router)
app.include_router(explain.router)
app.include_router(chat.router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Harvest2Value"}
