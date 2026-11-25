"""Seed the database with roles, users, settings, territories and synthetic demo data.

Usage (inside backend/):
    python -m scripts.seed            # incremental, idempotent
    python -m scripts.seed --regenerate
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.db.bootstrap import bootstrap, ensure_synthetic_artifacts  # noqa: E402
from app.services.synthetic import write_artifacts  # noqa: E402

logger = logging.getLogger("nutririsk.seed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed NutriRisk AI")
    parser.add_argument("--regenerate", action="store_true", help="Regenerar los datos sintéticos antes de sembrar")
    parser.add_argument("--skip-demo-data", action="store_true", help="Sembrar solo roles, usuarios y configuración")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )
    settings.ensure_directories()

    if args.regenerate:
        manifest = write_artifacts(settings.synthetic_dir)
        logger.info("Datos sintéticos regenerados: %s", manifest["run_id"])
    else:
        ensure_synthetic_artifacts()

    if args.skip_demo_data:
        from app.db.session import SessionLocal
        from app.db.bootstrap import create_schema_if_needed, seed_roles, seed_settings, seed_users

        create_schema_if_needed()
        with SessionLocal() as db:
            roles = seed_roles(db)
            seed_users(db, roles)
            seed_settings(db)
        result = {"status": "roles-users-settings"}
    else:
        result = bootstrap()

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
