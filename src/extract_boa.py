#!/usr/bin/env python3
"""Bank of America PDF statement extractor (bank + credit card)."""
import re
import sys
import logging
import pdfplumber
import pandas as pd
from common import group_words_into_lines

logging.getLogger("pdfminer").setLevel(logging.ERROR)

DATE_RE = re.compile(r'^\d{2}/\d{2}/\d{2}$')
CC_DATE_RE = re.compile(r'^\d{2}/\d{2}$')
AMOUNT_RE = re.compile(r'^-?\$?[\d,]+\.\d{2}$')


def to_float_us(s: str) -> float:
    """Convert US-formatted currency string to float."""
    if not isinstance(s, str):
        return 0.0
    clean = s.strip().replace("$", "").replace(",", "")
    try:
        return float(clean)
    except (ValueError, TypeError):
        return 0.0


def _detect_credit_card(pdf) -> bool:
    """Check first page for credit card indicators."""
    text = pdf.pages[0].extract_text() or ""
    return "purchases and adjustments" in text.lower()


def _extract_statement_year(pdf) -> str:
    """Extract year from statement header like 'February 22 - March 21, 2026'."""
    text = pdf.pages[0].extract_text() or ""
    m = re.search(r'(\w+\s+\d{1,2}\s*[-–]\s*\w+\s+\d{1,2},?\s*(\d{4}))', text)
    if m:
        return m.group(2)
    # Fallback: find any 4-digit year on first page
    m = re.search(r'\b(20\d{2})\b', text)
    return m.group(1) if m else "2026"


def _match_section(lower, is_cc):
    """Return new section name if line is a section header, else None."""
    if "total" in lower:
        return None  # total lines are not section headers

    if is_cc:
        if "payments and other credits" in lower:
            return "credits"
        if "purchases and adjustments" in lower:
            return "purchases"
        if "interest charged" in lower:
            return "interest"
        if "fees charged" in lower:
            return "fees"
    else:
        if "deposits and other additions" in lower:
            return "deposits"
        if "atm and debit card subtractions" in lower:
            return "subtractions"
        if "other subtractions" in lower:
            return "subtractions"
        if "service fees" in lower:
            return "subtractions"

    return None


def _is_section_total(lower):
    """Check if line is a section total line."""
    if "total" not in lower:
        return False
    keywords = ("deposits", "subtractions", "fees", "payments",
                "credits", "purchases", "adjustments", "interest")
    return any(kw in lower for kw in keywords)


def parse_boa_pdf(pdf_path: str) -> pd.DataFrame:
    """Extract transactions from a Bank of America PDF statement."""
    beginning_balance = None
    section = None
    transactions = []
    current_tx = None

    with pdfplumber.open(pdf_path) as pdf:
        is_cc = _detect_credit_card(pdf)
        stmt_year = _extract_statement_year(pdf) if is_cc else None
        date_re = CC_DATE_RE if is_cc else DATE_RE

        for page_num, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1, y_tolerance=3)
            lines = group_words_into_lines(words)

            for line in lines:
                text = line["text"]
                lower = text.lower()

                # Detect beginning/previous balance (always skip these lines)
                if "beginning balance" in lower or "previous balance" in lower:
                    if beginning_balance is None:
                        m = re.search(r'\$?([\d,]+\.\d{2})', text)
                        if m:
                            beginning_balance = to_float_us(m.group(0))
                    continue

                # Detect section headers (only for non-date lines)
                first_word = line["words"][0]["text"] if line["words"] else ""
                if not date_re.match(first_word):
                    new_section = _match_section(lower, is_cc)
                    if new_section is not None:
                        if current_tx:
                            transactions.append(current_tx)
                            current_tx = None
                        section = new_section
                        continue

                # Skip non-transaction lines
                if section is None:
                    continue
                if _is_section_total(lower):
                    if current_tx:
                        transactions.append(current_tx)
                        current_tx = None
                    section = None
                    continue
                if "continued" in lower:
                    continue
                if lower.startswith("date") and ("description" in lower or "amount" in lower):
                    continue
                if "transaction" in lower and "posting" in lower and "reference" in lower:
                    continue
                if lower.startswith("page") and "of" in lower:
                    continue
                if "withdrawals and other" in lower:
                    continue

                # Check if line starts with a date
                if date_re.match(first_word):
                    # Save previous transaction
                    if current_tx:
                        transactions.append(current_tx)

                    # Find the amount (rightmost word matching amount pattern)
                    amount_str = None
                    for w in reversed(line["words"]):
                        if AMOUNT_RE.match(w["text"]):
                            amount_str = w["text"]
                            break

                    # Description: skip date(s), stop before amount
                    # Credit card has two dates (transaction + posting)
                    start_idx = 1
                    if is_cc and len(line["words"]) > 1 and CC_DATE_RE.match(line["words"][1]["text"]):
                        start_idx = 2

                    desc_words = []
                    for w in line["words"][start_idx:]:
                        if w["text"] == amount_str:
                            break
                        desc_words.append(w["text"])

                    current_tx = {
                        "date": first_word,
                        "amount_str": amount_str,
                        "section": section,
                        "desc_parts": [" ".join(desc_words)] if desc_words else [],
                    }
                elif current_tx:
                    # Continuation of previous transaction description
                    desc_text = " ".join(w["text"] for w in line["words"])
                    current_tx["desc_parts"].append(desc_text)

            print(f"Page {page_num}: processed")

    if current_tx:
        transactions.append(current_tx)

    # Build DataFrame with running balance
    if beginning_balance is None:
        beginning_balance = 0.0

    running_balance = beginning_balance
    data = []

    for tx in transactions:
        if not tx["amount_str"]:
            continue

        amount = to_float_us(tx["amount_str"])
        description = " ".join(tx["desc_parts"]).strip()
        description = " ".join(description.split())

        if not description:
            continue

        tx_type = description.split()[0] if description else "Other"

        if is_cc:
            # Credit card: credits section = payments to card, rest = charges
            if tx["section"] == "credits":
                cash_in = abs(amount)
                cash_out = 0.0
            else:
                cash_in = 0.0
                cash_out = abs(amount)
            # Balance = amount owed: decreases with payments, increases with charges
            running_balance += cash_out - cash_in
        else:
            if tx["section"] == "deposits":
                cash_in = abs(amount)
                cash_out = 0.0
            else:
                cash_in = 0.0
                cash_out = abs(amount)
            running_balance += cash_in - cash_out

        # Parse date
        parts = tx["date"].split("/")
        if len(parts) == 3:
            # MM/DD/YY -> YYYY-MM-DD
            month, day, year = parts
            date_str = f"20{year}-{month}-{day}"
        elif len(parts) == 2 and stmt_year:
            # MM/DD -> YYYY-MM-DD (credit card)
            month, day = parts
            date_str = f"{stmt_year}-{month}-{day}"
        else:
            continue

        data.append({
            "Date": date_str,
            "Type": tx_type,
            "Description": description,
            "Cash In": cash_in,
            "Cash Out": cash_out,
            "Total Balance": round(running_balance, 2),
        })

    return pd.DataFrame(data)


def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "data/input/statement.pdf"
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "data/output/processed_transactions.csv"
    df = parse_boa_pdf(pdf_path)
    print(f"\nExtracted {len(df)} transactions")
    if df.empty:
        pd.DataFrame(columns=["Date", "Type", "Description", "Cash In", "Cash Out", "Total Balance"]).to_csv(
            output_csv, index=False)
    else:
        df.to_csv(output_csv, index=False)


if __name__ == "__main__":
    main()
