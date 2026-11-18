"""Build the README table from data/listings.yml.

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

ALLOWED = {
    "type": {"internship", "graduate"},
    "international": {"yes", "no", "conditional", "unknown"},
    "sponsorship": {"yes", "no", "unknown"},
    "status": {"open", "upcoming", "closed"},
}
REQUIRED = ["company", "role", "type", "locations", "intake", "international",
            "sponsorship", "eligibility", "link", "last_checked", "status"]

INTERNATIONAL_ICON = {"yes": "✅ Yes", "no": "❌ No", "conditional": "⚠️ Conditional", "unknown": "❓ Unknown"}
SPONSOR_ICON = {"yes": "🛂 Yes", "no": "No", "unknown": "❓"}


@dataclass
class Listing:
    company: str
    role: str
    type: str
    locations: list[str]
    intake: str
    international: str
    sponsorship: str
    eligibility: str
    link: str
    last_checked: str
    status: str
    opens: str = ""
    closes: str = ""
    notes: str = ""
    errors: list[str] = field(default_factory=list, repr=False)

    @classmethod
    def from_dict(cls, raw: dict, index: int) -> "Listing":
        # "no" without quotes becomes False in YAML, so only None/"" count as missing.
        missing = [key for key in REQUIRED if raw.get(key) in (None, "", [])]
        values = {key: raw.get(key, "") for key in cls.__dataclass_fields__ if key != "errors"}
        # YAML turns dates into date objects and yes/no into booleans; keep everything as text.
        for key, value in values.items():
            if isinstance(value, bool):
                values[key] = "yes" if value else "no"
            elif key != "locations" and value is not None:
                values[key] = str(value)
        listing = cls(**values)
        name = f"#{index + 1} ({raw.get('company', '?')})"
        listing.errors = [f"{name}: missing '{key}'" for key in missing]
        listing._validate(name)
        return listing

    def _validate(self, name: str) -> None:
        for key, allowed in ALLOWED.items():
            value = getattr(self, key)
            if value and value not in allowed:
                self.errors.append(f"{name}: '{key}' is '{value}', expected one of {sorted(allowed)}")
        if not isinstance(self.locations, list):
            self.errors.append(f"{name}: 'locations' must be a list, e.g. [Sydney]")
        if self.link and not self.link.startswith("https://"):
            self.errors.append(f"{name}: 'link' should start with https://")
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
        dates = " → ".join(part for part in (self.opens, self.closes) if part) or "—"
        cells = [
            f"**{self.company}**",
            f"[{self.role}]({self.link})",
            ", ".join(self.locations),
            self.intake,
            dates,
            INTERNATIONAL_ICON[self.international],
            SPONSOR_ICON[self.sponsorship],
            f"<details><summary>Quote</summary>\"{self.eligibility}\"<br>{self.notes}</details>",
            self.last_checked,
        ]
        return "| " + " | ".join(cell.replace("|", "/") for cell in cells) + " |"


def load_listings() -> list[Listing]:
    raw = yaml.safe_load(DATA_FILE.read_text(encoding="utf-8")) or {}
    return [Listing.from_dict(item, i) for i, item in enumerate(raw.get("listings", []))]


def build_tables(listings: list[Listing]) -> str:
    header = (
        "| Company | Role | Location | Intake | Opens → Closes | International students | Visa sponsorship | Eligibility | Checked |\n"
        "|---|---|---|---|---|---|---|---|---|"
    )
    sections = [("🟢 Open now", "open"), ("🟡 Opening soon", "upcoming"), ("🔒 Closed", "closed")]
    parts = []
    for title, status in sections:
        rows = sorted((l for l in listings if l.effective_status == status), key=lambda l: l.company.lower())
        parts.append(f"### {title} ({len(rows)})\n")
        parts.append("\n".join([header, *(l.to_row() for l in rows)]) if rows else "_Nothing here yet._")
        parts.append("")
    return "\n".join(parts).strip()


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
    README_FILE.write_text(f"{before}{START_MARKER}\n{build_tables(listings)}\n{END_MARKER}{after}", encoding="utf-8")
    print(f"README updated with {len(listings)} listings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
