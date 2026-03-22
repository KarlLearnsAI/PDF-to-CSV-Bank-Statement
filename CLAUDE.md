# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

```bash
python src/main.py [path-to-pdf]
```

Accepts an optional PDF path argument (default: `data/input/statement.pdf`). If just a filename is given (e.g. `statement.pdf`), it checks `data/input/`, `data/`, then the project root. Auto-detects the bank format from PDF content.

Output CSV is written to `data/output/<pdf-name>.csv`. Intermediate files go to `data/temp/`.

**Dependencies**: `pip install pdfplumber pandas`

No build, test, or lint configuration exists.

## Architecture

`src/main.py` auto-detects the bank from the PDF and routes to the appropriate pipeline.

`src/common.py` contains shared utilities: `to_float()`, `group_words_into_lines()`, month patterns, income keywords.

### Trade Republic pipeline (4 steps)
1. **extract_transactions.py** — Extracts transactions from PDF using pdfplumber's word-level coordinates (x0/top positions). Groups words into lines by Y-proximity, merges split date lines (day/month on separate Y-lines), detects ZAHLUNGSEINGANG/ZAHLUNGSAUSGANG column positions for Cash In/Out classification. Output: `data/temp/raw_transactions.csv`
2. **split_transactions.py** — Splits merged transaction rows using positive-lookahead regex on German date patterns. Output: `data/temp/splitted_raw_transactions.csv`
3. **preprocess_transactions.py** — Parses into structured fields, maps German month abbreviations to English, converts European currency format. Output: `data/output/<name>.csv`
4. **analyze_transactions.py** — Prints formatted transaction table and totals to terminal.

### Commerzbank pipeline (2 steps)
1. **extract_commerzbank.py** — Extracts transactions directly to processed format. Detects table boundaries per page ("Angaben zu den Umsätzen" → start, "Folgeseite"/"Neuer Kontostand" → end). Identifies transactions by Valuta date (DD.MM) in the Valuta column + amount in debit/credit columns. Trailing `-` on amounts indicates debit. Computes running balance from "Alter Kontostand". Output: `data/output/<name>.csv`
2. **analyze_transactions.py** — Same as Trade Republic.

## Key Design Details

- **Bank detection**: checks first page text for "COMMERZBANK" or "Kontoauszug" → Commerzbank; otherwise → Trade Republic
- **European currency**: `to_float()` treats dots as thousands separators and commas as decimal separators, handles trailing minus (`5,39-` → debit) and negative amounts
- **Trade Republic income detection**: column-position-based (ZAHLUNGSEINGANG vs ZAHLUNGSAUSGANG X positions from header), with keyword fallback (`INCOME_KEYWORDS` in `common.py`)
- **Commerzbank income detection**: column position (debit vs credit column) and trailing `-` on amounts
- **Path resolution**: `resolve_pdf_path()` checks exact path → `data/input/` → `data/` → project root
- **Privacy**: `.gitignore` excludes `*.pdf` and `*.csv` — never commit financial data
