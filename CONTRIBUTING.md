# Contributing

Thanks for helping other students! Accuracy is the whole point of this list, so every entry needs evidence.

## Option 1: Open an issue (easiest)

Use the **"New role"** issue template and paste the link to the official ad. A maintainer will add it.

## Option 2: Edit the data yourself

1. Add an entry to [`data/listings.yml`](data/listings.yml). The fields are explained at the top of that file.
2. Pick a `category`: software, data, cyber, quant, finance, consulting, engineering, design or business.
3. Copy the eligibility sentence **word for word** from the official ad into `eligibility` and set `verified: true`.
   If you only saw it on a secondary site, set `verified: false`.
4. Set `last_checked` to today's date.
5. Run the checks and rebuild the tables:

   ```bash
   pip install pyyaml
   python3 scripts/generate_readme.py --check
   python3 scripts/generate_readme.py
   ```

6. Open a pull request.

## Rules

- **Official sources first:** the company's careers page or its ad on a job board.
- **Quote, don't guess.** If the ad doesn't mention work rights, use `unknown`.
- Australia and New Zealand roles only.
- Don't add personal details of recruiters or staff.
