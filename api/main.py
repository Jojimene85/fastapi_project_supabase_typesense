"""
Punto de entrada de FastAPI: registra routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import seed, raw, gold, search, test


app = FastAPI(title="PWC Entrevista API")

# CORS: relajado para dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "service": "Lakehouse API (pandas)"}

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(raw.router)
app.include_router(gold.router)
app.include_router(search.router)
app.include_router(seed.router)
app.include_router(test.router)