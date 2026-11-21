"""The layout explorer page, built from the catalog document's examples and the compiler's renderers.

`./fw deck-compile --explorer` writes the page and prints its address. Each layout's
example comes from `deck-svg/reference/layout-catalog.md` and is rendered by the same
function `deck-compile` calls, once per variant, so the page shows exactly what a
storyboard row compiles to. A hand-written copy of every layout used to live in the
page and showed variants the compiler did not implement.

The same examples feed the test that every declared variant renders differently.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

try:
    from _deck import FRAMEWORK, SKILLS
    from _deck_catalog import CATALOG, SlideContext, parse_slot_payload
except ImportError:          # imported as scripts._deck_explorer (tests)
    from ._deck import FRAMEWORK, SKILLS
    from ._deck_catalog import CATALOG, SlideContext, parse_slot_payload

CATALOG_DOC = SKILLS / "deck-svg" / "reference" / "layout-catalog.md"
TEMPLATE = FRAMEWORK / "docs" / "layout-explorer.html"
STYLESHEETS = {
    "../.agents/skills/house-style/assets/css/tokens.css": SKILLS / "house-style" / "assets" / "css" / "tokens.css",
    "../.agents/skills/deck-svg/template/asset/deck.css": SKILLS / "deck-svg" / "template" / "asset" / "deck.css",
}
FAMILIES = {
    "Declarative": "宣告與定性類",
    "Parallel": "平行展開與收束類",
    "Relational": "關係、分類與對抗類",
    "Progression": "歷時演進與因果推進類",
    "Critique": "學術批判、文本與實證類",
}
EXAMPLE = re.compile(r"^### \d+\. `(L-[A-Z0-9-]+)`.*?```text\n\s*(.*?)\n\s*```", re.S | re.M)


def catalog_examples() -> dict[str, str]:
    """Each layout's 畫面內容 example from the catalog document, by layout code."""
    return {m.group(1): m.group(2).strip() for m in EXAMPLE.finditer(CATALOG_DOC.read_text(encoding="utf-8"))}


def render_example(layout_id: str, variant: str, example: str, accent: str = "var(--c1)") -> str:
    """One layout's example as the slide `deck-compile` would write for it in that variant."""
    layout = CATALOG[layout_id]
    slots = parse_slot_payload(example)
    title = slots.get("title") or slots.get("heading") or layout.name
    ctx = SlideContext(slide_num=1, total_slides=1, accent=accent, eyebrow=layout.name,
                       data_label=title, variant=variant)
    return layout.render_func(slots, variant, ctx)


def explorer_data() -> list[dict]:
    examples = catalog_examples()
    data = []
    for number, (layout_id, layout) in enumerate(CATALOG.items()):
        example = examples[layout_id]
        slides = {v: render_example(layout_id, v, example).replace('<section class="slide', '<section data-deck-active class="slide', 1)
                  for v in layout.allowed_variants}
        data.append({
            "id": layout_id, "name": layout.name, "family": FAMILIES.get(layout.family, layout.family),
            "variants": layout.allowed_variants, "html": slides,
            "snippet": f"| {number} | — | — | {layout_id} | — | — | {example} | — | — |",
        })
    return data


def build_explorer(out: Path | None = None) -> Path:
    """Write the explorer page and return its path.

    The page goes to the temporary directory by default, because the framework is a
    read-only submodule inside a course and a generated file there would dirty it.
    """
    page = TEMPLATE.read_text(encoding="utf-8")
    for href, path in STYLESHEETS.items():
        page = page.replace(f'href="{href}"', f'href="{path.resolve().as_uri()}"')
    # `</` would end the inline script early inside a JSON string
    payload = json.dumps(explorer_data(), ensure_ascii=False).replace("</", "<\\/")
    if "/*CATALOG_DATA*/[]" not in page:
        raise SystemExit(f"{TEMPLATE} has no /*CATALOG_DATA*/[] placeholder")
    page = page.replace("/*CATALOG_DATA*/[]", payload)
    out = out or Path(tempfile.gettempdir()) / "thesisbug2-layout-explorer.html"
    out.write_text(page, encoding="utf-8")
    return out
