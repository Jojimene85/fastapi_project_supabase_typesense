# api/routes/raw.py
"""
RAW: listado y subida de archivos CSV a Bronze.
- GET  /raw/list    : lista archivos en lake/bronze
- POST /raw         : sube uno o varios CSV (multipart/form-data, campo 'files')
"""

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from api.auth import basic_auth
from pathlib import Path
from datetime import datetime, timezone
import os, tempfile

router = APIRouter(prefix="/raw", tags=["raw"])

BRONZE_DIR = Path(os.getenv("BRONZE_DIR", "lake/bronze")).resolve()
BRONZE_DIR.mkdir(parents=True, exist_ok=True)

# Límite por archivo (MB). Cambiable vía env BRONZE_MAX_UPLOAD_MB
MAX_MB = int(os.getenv("BRONZE_MAX_UPLOAD_MB", "100"))
MAX_BYTES = MAX_MB * 1024 * 1024
CHUNK = 1 * 1024 * 1024  # 1 MB

def _secure_csv_name(name: str) -> str:
    base = Path(name or "").name  # evita path traversal
    if not base:
        raise HTTPException(422, detail="Nombre de archivo inválido.")
    if not base.lower().endswith(".csv"):
        raise HTTPException(422, detail=f"Solo se aceptan archivos .csv (recibido: {base}).")
    return base

@router.get("/list", dependencies=[Depends(basic_auth)])
def list_raw_files():
    """Lista archivos existentes en lake/bronze (recursivo)."""
    files = []
    for p in BRONZE_DIR.rglob("*"):
        if p.is_file():
            st = p.stat()
            files.append({
                "path": str(p.relative_to(BRONZE_DIR)),
                "bytes": st.st_size,
                "modified_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            })
    files.sort(key=lambda x: x["path"])
    return {"count": len(files), "max_upload_mb": MAX_MB, "files": files}

@router.post("", dependencies=[Depends(basic_auth)])
async def upload_raw_csv(
    files: list[UploadFile] = File(..., description="Uno o varios CSV (campo 'files')")
):
    """
    Sube **uno o varios** CSV a Bronze.
    - Límite por archivo: MAX_MB (por env BRONZE_MAX_UPLOAD_MB, default 100MB).
    - Escritura atómica: tmp → replace.
    - Se sobrescribe si ya existe.
    """
    results: list[dict] = []

    for file in files:
        tmp_path = None
        try:
            target = _secure_csv_name(file.filename)
            dest = (BRONZE_DIR / target).resolve()
            if dest.parent != BRONZE_DIR:
                raise HTTPException(400, detail="Ruta destino inválida.")

            total = 0
            with tempfile.NamedTemporaryFile("wb", dir=BRONZE_DIR, delete=False) as tmp:
                while True:
                    chunk = await file.read(CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise HTTPException(413, detail=f"{target}: supera {MAX_MB} MB.")
                    tmp.write(chunk)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = Path(tmp.name)

            os.replace(tmp_path, dest)
            results.append({"file": target, "bytes": total, "ok": True, "message": "Guardado"})
        except HTTPException as he:
            if tmp_path:
                try: tmp_path.unlink(missing_ok=True)
                except: pass
            results.append({"file": file.filename, "ok": False, "error": he.detail})
        except Exception as e:
            if tmp_path:
                try: tmp_path.unlink(missing_ok=True)
                except: pass
            results.append({"file": file.filename, "ok": False, "error": str(e)})
        finally:
            await file.close()

    return {"ok": all(r.get("ok") for r in results), "max_upload_mb": MAX_MB, "results": results}
