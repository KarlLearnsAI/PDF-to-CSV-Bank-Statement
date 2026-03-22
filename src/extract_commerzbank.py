#!/usr/bin/env python3
"""Commerzbank PDF statement extractor."""
import re
import sys
import logging
from datetime import datetime
import pdfplumber
import pandas as pd
from common import to_float, group_words_into_lines

logging.getLogger("pdfminer").setLevel(logging.ERROR)


def parse_commerzbank_pdf(pdf_path: str) -> pd.DataFrame:
    """Extract transactions from a Commerzbank PDF statement."""
    opening_balance = None
    booking_date = None
    transactions = []
    current_tx = None
    valuta_x = None

    valuta_re = re.compile(r'^\d{2}\.\d{2}$')
    amount_re = re.compile(r'^[\d.]+,\d{2}-?$')
    buchung_re = re.compile(r'Buchungsdatum:\s*(\d{2}\.\d{2}\.\d{4})')

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1, y_tolerance=3)
            lines = group_words_into_lines(words)

            # Find table Y boundaries for this page
            table_start_y = None
            table_end_y = page.height

            for line in lines:
                text = line["text"]
                if "Alter Kontostand" in text or "Angaben zu den Umsätzen" in text:
                    if table_start_y is None:
                        table_start_y = line["top"]
                if ("Folgeseite" in text or "Neuer Kontostand" in text
                        or "Guthaben sind als" in text):
                    table_end_y = min(table_end_y, line["top"])
                # Detect Valuta column X position from header
                if valuta_x is None:
                    for w in line["words"]:
                        if w["text"] == "Valuta":
                            valuta_x = w["x0"]

            if table_start_y is None:
                continue

            # Process lines within table area
            for line in lines:
                if line["top"] < table_start_y or line["top"] >= table_end_y:
                    continue

                text = line["text"]

                # Handle Alter Kontostand (opening balance)
                if "Alter Kontostand" in text:
                    for w in reversed(line["words"]):
                        if amount_re.match(w["text"]):
                            opening_balance = to_float(w["text"])
                            break
                    continue

                # Skip column headers
                if any(s in text for s in [
                    "Angaben zu den Umsätzen", "Kontowährung",
                    "zu Ihren",
                ]):
                    continue

                # Handle Buchungsdatum
                m = buchung_re.search(text)
                if m:
                    booking_date = m.group(1)
                    continue

                if valuta_x is None:
                    continue

                # Parse line: look for Valuta date and amount
                line_valuta = None
                line_amount_str = None
                line_is_debit = False
                desc_words = []

                for w in line["words"]:
                    # Valuta date (DD.MM) near the Valuta column
                    if abs(w["x0"] - valuta_x) < 30 and valuta_re.match(w["text"]):
                        line_valuta = w["text"]
                    # Amount in debit/credit columns (right of Valuta)
                    elif w["x0"] > valuta_x + 30 and amount_re.match(w["text"]):
                        line_amount_str = w["text"]
                        line_is_debit = w["text"].endswith('-')
                    # Description word (left of Valuta column)
                    elif w["x0"] < valuta_x - 10:
                        desc_words.append(w["text"])

                desc_text = " ".join(desc_words).strip()

                if line_valuta and line_amount_str:
                    # New transaction starts
                    if current_tx:
                        transactions.append(current_tx)
                    current_tx = {
                        "booking_date": booking_date,
                        "valuta_date": line_valuta,
                        "amount_str": line_amount_str,
                        "is_debit": line_is_debit,
                        "desc_parts": [desc_text] if desc_text else [],
                    }
                elif current_tx and desc_text:
                    # Continuation of previous transaction's description
                    current_tx["desc_parts"].append(desc_text)

            print(f"Page {page_num}: processed")

    # Don't forget the last transaction
    if current_tx:
        transactions.append(current_tx)

    # Build output DataFrame with running balance
    if opening_balance is None:
        opening_balance = 0.0

    running_balance = opening_balance
    data = []

    for tx in transactions:
        description = " ".join(tx["desc_parts"]).strip()
        description = " ".join(description.split())

        tx_type = description.split()[0] if description else "Sonstige"

        try:
            date = datetime.strptime(tx["booking_date"], "%d.%m.%Y")
        except (ValueError, TypeError):
            continue

        amount = abs(to_float(tx["amount_str"]))

        cash_in = 0.0
        cash_out = 0.0
        if tx["is_debit"]:
            cash_out = amount
            running_balance -= amount
        else:
            cash_in = amount
            running_balance += amount

        data.append({
            "Date": date,
            "Type": tx_type,
            "Description": description,
            "Cash In": cash_in,
            "Cash Out": cash_out,
            "Total Balance": round(running_balance, 2),
        })

    df = pd.DataFrame(data)
    return df


def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "data/input/statement.pdf"
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "data/output/processed_transactions.csv"
    df = parse_commerzbank_pdf(pdf_path)
    print(f"\nExtracted {len(df)} transactions")
    if df.empty:
        pd.DataFrame(columns=["Date", "Type", "Description", "Cash In", "Cash Out", "Total Balance"]).to_csv(
            output_csv, index=False)
    else:
        df.to_csv(output_csv, index=False)


if __name__ == "__main__":
    main()
