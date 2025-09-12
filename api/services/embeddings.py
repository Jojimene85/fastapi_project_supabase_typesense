# api/services/embeddings.py
import os
import httpx

SUPABASE_EMBED_URL = os.getenv("SUPABASE_EMBED_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

async def embed_query(text: str) -> list[float]:
    if not SUPABASE_EMBED_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Embeddings no configurados en .env")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            SUPABASE_EMBED_URL,
            headers={"Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"},
            json={"input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["embedding"]
