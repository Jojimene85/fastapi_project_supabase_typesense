from fastapi import APIRouter
import subprocess
import re

router = APIRouter(prefix="/test", tags=["test"])

@router.get("/")
def run_tests():
    """
    Ejecuta todos los tests de pytest y devuelve un resumen por test.
    """
    try:
        result = subprocess.run(
            ["pytest", "tests", "--maxfail=1", "--disable-warnings", "--tb=short", "-v"],
            capture_output=True, text=True
        )
        # Parsear el output para mostrar por test
        lines = result.stdout.splitlines()
        summary = []
        for line in lines:
            # Ejemplo de línea: tests/test_api.py::test_read_main PASSED
            m = re.match(r"(tests/.*?\.py)::(\w+) (\w+)", line)
            if m:
                file, test, status = m.groups()
                if status == "PASSED":
                    summary.append(f"{test} en {file}: OK ✅")
                elif status == "FAILED":
                    summary.append(f"{test} en {file}: ERROR ❌")
                else:
                    summary.append(f"{test} en {file}: {status}")
        return {
            "returncode": result.returncode,
            "summary": summary,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except Exception as e:
        return {"error": str(e)}