"""Brand kit loader. All render styling flows through here."""

from pathlib import Path

import yaml

from autoclip.config import settings


def load_brand(brandkit_dir: Path | None = None) -> dict:
    root = brandkit_dir or settings.brandkit_dir
    brand = yaml.safe_load((root / "brand.yaml").read_text(encoding="utf-8"))

    # Resolve asset paths relative to the brand kit directory.
    for key in ("light", "dark"):
        rel = brand.get("logo", {}).get(key)
        if rel:
            brand["logo"][key] = str(root / rel)
    return brand
