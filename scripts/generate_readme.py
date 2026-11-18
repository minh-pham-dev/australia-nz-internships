"""Build the README tables from data/listings.yml.

Run from the repo root:
    python3 scripts/generate_readme.py          # rewrite README.md
    python3 scripts/generate_readme.py --check  # only validate the data
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "listings.yml"
README_FILE = ROOT / "README.md"
START_MARKER = "<!-- LISTINGS:START -->"
END_MARKER = "<!-- LISTINGS:END -->"

# Category key -> heading shown in the README (also sets the section order).
CATEGORIES = {
    "software": "💻 Software & IT",
    "data": "📊 Data & AI",
    "cyber": "🔐 Cyber Security",
    "quant": "📈 Quant & Trading",
    "finance": "🏦 Banking & Finance",
    "consulting": "🧾 Accounting & Consulting",
    "engineering": "🏗️ Engineering",
    "design": "🎨 Product & Design",
    "business": "💼 Business & Other",
}
FLAGS = {"AU": "🇦🇺 AU", "NZ": "🇳🇿 NZ"}  # text code too: the two flags look alike when small
ALLOWED = {
    "category": set(CATEGORIES),
    "international": {"yes", "no", "conditional", "unknown"},
    "sponsorship": {"yes", "no", "unknown"},
    "status": {"open", "upcoming", "closed"},
}
REQUIRED = ["company", "role", "category", "country", "locations", "intake", "international",
            "sponsorship", "eligibility", "link", "last_checked", "status"]
STATUS_ORDER = {"open": 0, "upcoming": 1, "closed": 2}

INTERNATIONAL_ICON = {"yes": "✅ Yes", "no": "❌ No", "conditional": "⚠️ Conditional", "unknown": "❓ Unknown"}
SPONSOR_ICON = {"yes": "🛂 Yes", "no": "No", "unknown": "❓"}
STATUS_ICON = {"open": "🟢 Open", "upcoming": "🟡 Soon", "closed": "🔒 Closed"}


@dataclass
class Listing:
    company: str
    role: str
    category: str
    country: list[str]
    locations: list[str]
    intake: str
    international: str
    sponsorship: str
    eligibility: str
    link: str
    last_checked: str
    status: str
    verified: bool = False
    opens: str = ""
    closes: str = ""
    notes: str = ""
    errors: list[str] = field(default_factory=list, repr=False)

    LIST_FIELDS = ("country", "locations")

    @classmethod
    def from_dict(cls, raw: dict, index: int) -> "Listing":
        name = f"#{index + 1} ({raw.get('company', '?')})"
        # "no" without quotes becomes False in YAML, so only None/""/[] count as missing.
        errors = [f"{name}: missing '{key}'" for key in REQUIRED if raw.get(key) in (None, "", [])]

        values = {}
        for key in cls.__dataclass_fields__:
            if key == "errors":
                continue
            value = raw.get(key)
            if value is None:
                continue  # use the default
            if key == "verified":
                values[key] = value is True
            elif key in cls.LIST_FIELDS:
                values[key] = value if isinstance(value, list) else [value]
            elif isinstance(value, bool):  # YAML turned yes/no into True/False
                values[key] = "yes" if value else "no"
            else:
                values[key] = str(value)  # YAML may have turned dates into date objects

        for key in REQUIRED:
            values.setdefault(key, [] if key in cls.LIST_FIELDS else "")
        listing = cls(**values)
        listing.errors = errors
        listing._validate(name, raw)
        return listing

    def _validate(self, name: str, raw: dict) -> None:
        for key, allowed in ALLOWED.items():
            value = getattr(self, key)
            if value and value not in allowed:
                self.errors.append(f"{name}: '{key}' is '{value}', expected one of {sorted(allowed)}")
        for key in self.LIST_FIELDS:
            if raw.get(key) is not None and not isinstance(raw.get(key), list):
                example = "[AU]" if key == "country" else "[Sydney]"
                self.errors.append(f"{name}: '{key}' must be a list, e.g. {example}")
        for code in self.country:
            if code not in FLAGS:
                self.errors.append(f"{name}: country '{code}' should be AU or NZ")
        if self.link and not self.link.startswith("https://"):
            self.errors.append(f"{name}: 'link' should start with https://")
        if "verified" in raw and not isinstance(raw["verified"], bool):
            self.errors.append(f"{name}: 'verified' must be true or false")
        try:
            date.fromisoformat(self.last_checked)
        except ValueError:
            self.errors.append(f"{name}: 'last_checked' must be YYYY-MM-DD")

    @property
    def effective_status(self) -> str:
        """Treat a role as closed once its exact closing date has passed."""
        try:
            if date.fromisoformat(self.closes) < date.today():
                return "closed"
        except ValueError:
            pass  # closes is empty or free text like "Feb 2027"
        return self.status

    def to_row(self) -> str:
        flags = " / ".join(FLAGS[code] for code in self.country)
        dates = " → ".join(part for part in (self.opens, self.closes) if part) or "—"
        quote = f"\"{self.eligibility}\"" if self.verified else f"{self.eligibility} <i>(unverified)</i>"
        detail = f"{quote}<br>{self.notes}" if self.notes else quote
        checked = self.last_checked if self.verified else f"{self.last_checked} ⏳"
        company = f"**{self.company}**"
        if self.effective_status == "closed":
            company = f"~~{self.company}~~"
        cells = [
            company,
            self.role,
            f"{flags}<br>{', '.join(self.locations)}",
            STATUS_ICON[self.effective_status],
            dates,
            f"<details><summary>{INTERNATIONAL_ICON[self.international]}</summary>{detail}</details>",
            SPONSOR_ICON[self.sponsorship],
            f"[Apply]({self.link})",
            checked,
        ]
        return "| " + " | ".join(str(cell).replace("|", "/") for cell in cells) + " |"


def load_listings() -> list[Listing]:
    raw = yaml.safe_load(DATA_FILE.read_text(encoding="utf-8")) or {}
    return [Listing.from_dict(item, i) for i, item in enumerate(raw.get("listings") or [])]


def anchor(heading: str) -> str:
    """GitHub-style anchor: lowercase, drop symbols/emoji, spaces become hyphens.

    The emoji is dropped but the space after it stays, so "💻 Software & IT"
    becomes "-software--it", which matches what GitHub generates.
    """
    text = "".join(ch for ch in heading.lower() if ch.isalnum() or ch in " -")
    return text.replace(" ", "-")


def build_section(listings: list[Listing]) -> str:
    header = (
        "| Company | Role | Location | Status | Opens → Closes | International students | Sponsors visa | Link | Checked |\n"
        "|---|---|---|---|---|---|---|---|---|"
    )
    counts = {s: sum(l.effective_status == s for l in listings) for s in STATUS_ORDER}
    lines = [
        f"**{len(listings)} roles** · 🟢 {counts['open']} open · 🟡 {counts['upcoming']} opening soon · "
        f"🔒 {counts['closed']} closed · "
        f"✅ {sum(l.international == 'yes' for l in listings)} confirmed open to international students",
        "",
        "| Category | Roles |",
        "|---|---|",
    ]
    present = [key for key in CATEGORIES if any(l.category == key for l in listings)]
    for key in present:
        n = sum(l.category == key for l in listings)
        lines.append(f"| [{CATEGORIES[key]}](#{anchor(CATEGORIES[key])}) | {n} |")
    lines.append("")
    for key in present:
        rows = sorted(
            (l for l in listings if l.category == key),
            key=lambda l: (STATUS_ORDER[l.effective_status], l.company.lower()),
        )
        lines += [f"### {CATEGORIES[key]}", "", header, *(l.to_row() for l in rows), ""]
    return "\n".join(lines).strip()


def main() -> int:
    listings = load_listings()
    errors = [error for listing in listings for error in listing.errors]
    if errors:
        print("Data errors:\n  " + "\n  ".join(errors))
        return 1
    if "--check" in sys.argv:
        print(f"OK: {len(listings)} listings are valid.")
        return 0

    readme = README_FILE.read_text(encoding="utf-8")
    before, rest = readme.split(START_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)
    README_FILE.write_text(f"{before}{START_MARKER}\n{build_section(listings)}\n{END_MARKER}{after}", encoding="utf-8")
    print(f"README updated with {len(listings)} listings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
