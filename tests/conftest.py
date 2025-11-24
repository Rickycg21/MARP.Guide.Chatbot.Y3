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

"""
Configures pytest so each microservice's `app/` and `common/` folders can be
imported correctly by adding their service roots to PYTHONPATH during tests.
"""

for service in SERVICE_NAMES:
    service_root = SERVICES_DIR / service
    if service_root.exists():
        sys.path.insert(0, str(service_root))
        print(f"[PYTEST] Added to PYTHONPATH: {service_root}")
    else:
        print(f"[PYTEST] WARNING: service not found: {service_root}")
