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
UPDATED_START = "<!-- UPDATED:START -->"
UPDATED_END = "<!-- UPDATED:END -->"

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
    "sponsorship": {"yes", "no", "unknown"},  # optional field
}
REQUIRED = ["company", "role", "category", "country", "locations", "careers_page", "study_year",
            "duration", "status", "expected_open", "last_round", "international", "summary",
            "eligibility", "source", "source_note", "last_checked"]
SUMMARY_MAX = 120  # one or two short sentences shown when the cell is clicked
URL_FIELDS = ("careers_page", "source", "apply_link")
LIST_FIELDS = ("country", "locations")
STATUS_ORDER = {"open": 0, "not_open": 1, "closed": 2}

INTERNATIONAL_ICON = {"yes": "✅ Yes", "no": "❌ No", "conditional": "⚠️ Depends", "unknown": "❓ Not stated"}


@dataclass
class Listing:
    company: str
    role: str
    category: str
    country: list[str]
    locations: list[str]
    careers_page: str
    study_year: str
    duration: str
    status: str
    expected_open: str
    last_round: str
    international: str
    summary: str
    eligibility: str
    source: str
    source_note: str
    last_checked: str
    sponsorship: str = "unknown"  # kept in the data, not shown: students already here don't need it for internships
    apply_link: str = ""
    closes: str = ""
    posted: str = ""  # "YYYY-MM-DD" the live ad went up; shown as its age
    last_round_dates: str = ""
    last_opened: str = ""
    study_year_detail: str = ""
    other_requirements: str = ""  # shown on click, e.g. "Credit average of 65 WAM"
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
        if len(self.other_requirements) > SUMMARY_MAX:
            self.errors.append(f"{name}: 'other_requirements' is too long; keep it under {SUMMARY_MAX}")
        if len(self.summary) > SUMMARY_MAX:
            self.errors.append(f"{name}: 'summary' is {len(self.summary)} characters; keep it under {SUMMARY_MAX}")
        if self.status == "open" and not self.apply_link:
            self.errors.append(f"{name}: status is 'open' but there is no 'apply_link' to the live ad")
        if self.status == "open" and not self.posted:
            self.errors.append(f"{name}: status is 'open' but there is no 'posted' date for the live ad")
        for key in ("last_checked", "closes", "posted"):
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

    def age(self) -> str:
        """How long the live ad has been up, like Simplify's Age column. Only right if the README is rebuilt daily."""
        days = (date.today() - date.fromisoformat(self.posted)).days
        return "posted today" if days <= 0 else f"{days}d old"

    def round_cell(self) -> str:
        if self.effective_status == "open":
            closes = f"<br>Closes {self.closes}" if self.closes else ""
            return f"📝 **Open** · {self.age()}<br>[Apply]({self.apply_link}){closes}"
        if self.effective_status == "closed":
            return "🔒 Closed"
        visible = f"⏳ Not open yet<br>Expected: {self.expected_open}"
        if not self.last_opened:
            return visible  # nothing more to say, so no click needed
        return f"<details><summary>{visible}</summary><br>Last round: {self.last_opened}</details>"

    def eligibility_cell(self) -> str:
        # Visible: the icon. Click: a plain-English summary and the source link.
        # The exact quote (eligibility) stays in the data file as proof for each summary,
        # along with last_round_dates, notes and source_note, but readers don't see them.
        origin = f"<sub>{self.last_round} round · <a href=\"{self.source}\">Source</a></sub>"
        # Bold label so it stands apart from the explanation that opens under it.
        label = f"<b>{INTERNATIONAL_ICON[self.international]}</b>"
        also = f"<br><b>Also needs:</b> {self.other_requirements}" if self.other_requirements else ""
        return f"<details><summary>{label}</summary><br>{self.summary}{also}<br>{origin}</details>"

    def to_row(self) -> str:
        flags = " / ".join(FLAGS[code] for code in self.country)
        company = f"~~{self.company}~~" if self.effective_status == "closed" else f"**{self.company}**"
        # study_year_detail (last round's exact dates) stays in the data but isn't shown:
        # it describes last year's cohort and would confuse people applying this year.
        cells = [
            company,
            f"{self.role}<br><sub>🎓 {self.study_year}</sub>",
            f"{flags}<br>{', '.join(self.locations)}",
            self.duration,
            self.round_cell(),
            self.eligibility_cell(),
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
        "| Company | Role | Location | Duration | Applications (2027/28) | International students? | Links | Checked |\n"
        "|---|---|---|---|---|---|---|---|"
    )
    count = lambda status: sum(l.effective_status == status for l in listings)
    lines = [
        f"**{len(listings)} program{'' if len(listings) == 1 else 's'}** · 📝 {count('open')} open now · ⏳ {count('not_open')} not open yet · "
        f"✅ {sum(l.international == 'yes' for l in listings)} open to international students (2026/27)",
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


def replace_between(text: str, start: str, end: str, content: str) -> str:
    """Swap whatever sits between two marker comments for new content."""
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    return f"{before}{start}\n{content}\n{end}{after}"


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
    readme = replace_between(readme, START_MARKER, END_MARKER, build_section(listings))
    today = date.today()
    stamp = f"🔄 **Last updated: {today.day} {today:%B %Y}** · New programs are added as their ads open"
    readme = replace_between(readme, UPDATED_START, UPDATED_END, stamp)
    README_FILE.write_text(readme, encoding="utf-8")
    print(f"README updated with {len(listings)} listings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
