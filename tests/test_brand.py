from pathlib import Path

from autoclip.brand import load_brand

REPO_BRANDKIT = Path(__file__).resolve().parents[1] / "brandkit"


def test_repo_brandkit_loads_and_resolves_assets():
    brand = load_brand(REPO_BRANDKIT)
    assert brand["colors"]["canvas_bg"].startswith("#")
    assert brand["font"]["family"]
    for key in ("light", "dark"):
        assert Path(brand["logo"][key]).is_file(), f"missing logo asset: {key}"
    assert brand["subtitles"]["font_size"] > 0
