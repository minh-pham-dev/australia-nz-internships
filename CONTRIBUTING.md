# Contributing

Thanks for helping other students! Accuracy is the whole point of this list, so every program needs a source anyone can open.

## Option 1: Open an issue (easiest)

Use the **"New role"** issue template and paste the link to the ad. A maintainer will check it and add it.

## Option 2: Edit the data yourself

1. Add an entry to [`data/listings.yml`](data/listings.yml). The fields are explained at the top of that file.
2. Copy the eligibility sentence **word for word** into `eligibility`, then write a plain-English `summary` of it.
   The summary is what readers see, so it must say the same thing as the quote and nothing more.
3. Put the link where that sentence can be read **right now** into `source`, and say what it is in `source_note`.
   If the company took the ad down, an exact copy on a job board is fine. Say so in `source_note`.
4. When the new round's ad goes live, set `status: open` and add `apply_link` and `posted` (the date the ad went up).
5. Set `last_checked` to today's date.
6. Optional: check your entry locally before opening a pull request:

   ```bash
   pip install pyyaml
   python3 scripts/generate_readme.py --check
   ```

7. Open a pull request. A GitHub Action checks your data automatically, and rebuilds the README after it's merged, so you don't need to edit `README.md` yourself.

## Rules

- **Quote, don't guess.** If the ad doesn't mention work rights, use `unknown`.
- **Before you submit, open your `source` link and find the quote on that page.**
- Australia and New Zealand programs only.
- Don't add personal details of recruiters or staff.
