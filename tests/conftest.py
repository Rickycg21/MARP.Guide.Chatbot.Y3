import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICES_DIR = REPO_ROOT / "services"

SERVICE_NAMES = [
    "ingestion",
    "extraction",
    "indexing",
    "retrieval",
    "chat",
    "monitoring",
]

# Make "services.*" importable from anywhere
sys.path.insert(0, str(REPO_ROOT))
print(f"[PYTEST] Added repo root to PYTHONPATH: {REPO_ROOT}")

for service in SERVICE_NAMES:
    service_root = SERVICES_DIR / service
    if service_root.exists():
        sys.path.insert(0, str(service_root))
        print(f"[PYTEST] Added to PYTHONPATH: {service_root}")
    else:
        print(f"[PYTEST] WARNING: service not found: {service_root}")
