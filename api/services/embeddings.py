# api/services/embeddings.py
import os
import httpx

SUPABASE_EMBED_URL = os.getenv("SUPABASE_EMBED_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
VERIFY_TLS = os.getenv("HTTPX_VERIFY", "1") != "0"

async def embed_query(text: str) -> list[float]:
    if not SUPABASE_EMBED_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Embeddings no configurados en .env")
    
    async with httpx.AsyncClient(timeout=30.0, verify=VERIFY_TLS) as client:
        # Prueba ambos formatos de payload
        try:
            resp = await client.post(
                SUPABASE_EMBED_URL,
                headers={"Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"},
                json={"inputs": [text]},
            )
            resp.raise_for_status()
            data = resp.json()
            # Si la respuesta tiene "embeddings", devuelve el primero
            if isinstance(data, dict) and "embeddings" in data:
                return data["embeddings"][0]
            # Si la respuesta tiene "embedding", úsalo
            if isinstance(data, dict) and "embedding" in data:
                return data["embedding"]
            # Si la respuesta es una lista, devuelve el primero
            if isinstance(data, list):
                return data[0]
            raise RuntimeError(f"Respuesta inesperada de embed: {data}")
        except Exception as e:
            raise RuntimeError(f"Error llamando a embed: {e}")
