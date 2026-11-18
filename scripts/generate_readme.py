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
    "status": {"not_open", "open", "closed"},
    "international": {"yes", "no", "conditional", "unknown"},
    "sponsorship": {"yes", "no", "unknown"},
}
REQUIRED = ["company", "role", "category", "country", "locations", "careers_page",
            "status", "expected_open", "last_round", "international", "sponsorship",
            "eligibility", "source", "source_note", "last_checked"]
URL_FIELDS = ("careers_page", "source", "apply_link")
LIST_FIELDS = ("country", "locations")
STATUS_ORDER = {"open": 0, "not_open": 1, "closed": 2}

INTERNATIONAL_ICON = {"yes": "✅ Yes", "no": "❌ No", "conditional": "⚠️ Conditional", "unknown": "❓ Unknown"}
SPONSOR_ICON = {"yes": "🛂 Yes", "no": "No", "unknown": "❓"}


@dataclass
class Listing:
    company: str
    role: str
    category: str
    country: list[str]
    locations: list[str]
    careers_page: str
    status: str
    expected_open: str
    last_round: str
    international: str
    sponsorship: str
    eligibility: str
    source: str
    source_note: str
    last_checked: str
    apply_link: str = ""
    closes: str = ""
    last_round_dates: str = ""
    notes: str = ""
    errors: list[str] = field(default_factory=list, repr=False)

    @classmethod
    def from_dict(cls, raw: dict, index: int) -> "Listing":
        name = f"#{index + 1} ({raw.get('company', '?')})"
        # "no" without quotes becomes False in YAML, so only None/""/[] count as missing.
        errors = [f"{name}: missing '{key}'" for key in REQUIRED if raw.get(key) in (None, "", [])]
        unknown = set(raw) - set(cls.__dataclass_fields__)
        errors += [f"{name}: unknown field '{key}' (typo?)" for key in sorted(unknown)]

        values = {}
        for key in cls.__dataclass_fields__:
            if key == "errors" or raw.get(key) is None:
                continue
            value = raw[key]
            if key in LIST_FIELDS:
                values[key] = value if isinstance(value, list) else [value]
            elif isinstance(value, bool):  # YAML turned yes/no into True/False
                values[key] = "yes" if value else "no"
            else:
                values[key] = str(value)  # YAML may have turned dates into date objects
        for key in REQUIRED:
            values.setdefault(key, [] if key in LIST_FIELDS else "")

        listing = cls(**values)
        listing.errors = errors
        listing._validate(name, raw)
        return listing

    def _validate(self, name: str, raw: dict) -> None:
        for key, allowed in ALLOWED.items():
            value = getattr(self, key)
            if value and value not in allowed:
                self.errors.append(f"{name}: '{key}' is '{value}', expected one of {sorted(allowed)}")
        for key in LIST_FIELDS:
            if raw.get(key) is not None and not isinstance(raw.get(key), list):
                example = "[AU]" if key == "country" else "[Sydney]"
                self.errors.append(f"{name}: '{key}' must be a list, e.g. {example}")
        for code in self.country:
            if code not in FLAGS:
                self.errors.append(f"{name}: country '{code}' should be AU or NZ")
        for key in URL_FIELDS:
            value = getattr(self, key)
            if value and not value.startswith("https://"):
                self.errors.append(f"{name}: '{key}' should start with https://")
        if self.status == "open" and not self.apply_link:
            self.errors.append(f"{name}: status is 'open' but there is no 'apply_link' to the live ad")
        for key in ("last_checked", "closes"):
            value = getattr(self, key)
            if value:
                try:
                    date.fromisoformat(value)
                except ValueError:
                    self.errors.append(f"{name}: '{key}' must be YYYY-MM-DD")

    @property
    def effective_status(self) -> str:
        """An open round counts as closed once its closing date has passed."""
        if self.status == "open" and self.closes and date.fromisoformat(self.closes) < date.today():
            return "closed"
        return self.status

    def round_cell(self) -> str:
        if self.effective_status == "open":
            closes = f"<br>Closes {self.closes}" if self.closes else ""
            return f"🟢 **Open**<br>[Apply]({self.apply_link}){closes}"
        if self.effective_status == "closed":
            return "🔒 Closed"
        return f"🔜 Not open yet<br>Expected: {self.expected_open}"

    def eligibility_cell(self) -> str:
        parts = [
            f"<b>{self.last_round} round (expired):</b>",
            f"\"{self.eligibility}\"",
            f"Source: <a href=\"{self.source}\">{self.source_note}</a>",
        ]
        if self.last_round_dates:
            parts.append(self.last_round_dates)
        if self.notes:
            parts.append(self.notes)
        return f"<details><summary>{INTERNATIONAL_ICON[self.international]}</summary>{'<br>'.join(parts)}</details>"

    def to_row(self) -> str:
        flags = " / ".join(FLAGS[code] for code in self.country)
        company = f"~~{self.company}~~" if self.effective_status == "closed" else f"**{self.company}**"
        cells = [
            company,
            self.role,
            f"{flags}<br>{', '.join(self.locations)}",
            self.round_cell(),
            self.eligibility_cell(),
            SPONSOR_ICON[self.sponsorship],
            f"[Careers page]({self.careers_page})",
            self.last_checked,
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
        "| Company | Role | Location | 2027/28 round | International students (last round) | Sponsors visa | Links | Checked |\n"
        "|---|---|---|---|---|---|---|---|"
    )
    count = lambda status: sum(l.effective_status == status for l in listings)
    lines = [
        f"**{len(listings)} program{'' if len(listings) == 1 else 's'}** · 🟢 {count('open')} open now · 🔜 {count('not_open')} not open yet · "
        f"✅ {sum(l.international == 'yes' for l in listings)} accepted international students last round",
        "",
        "| Category | Programs |",
        "|---|---|",
    ]
    present = [key for key in CATEGORIES if any(l.category == key for l in listings)]
    for key in present:
        lines.append(f"| [{CATEGORIES[key]}](#{anchor(CATEGORIES[key])}) | {sum(l.category == key for l in listings)} |")
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
