#!/usr/bin/env python3
import re
import sys
import logging
import pdfplumber
import pandas as pd
from common import to_float, group_words_into_lines, MONTHS_PATTERN, INCOME_KEYWORDS

logging.getLogger("pdfminer").setLevel(logging.ERROR)

MONTHS_RE = re.compile(rf"^({MONTHS_PATTERN})\.?\s")


def merge_date_lines(lines):
    """Merge bare day-number lines with the following month line.

    Trade Republic PDFs sometimes place the day (e.g. '01') on its own
    Y-line, with the month ('Sept.') on the next.  This pass combines
    them so that downstream date detection works correctly.
    """
    merged = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if (re.match(r'^\s*\d{1,2}\s*$', line['text'])
                and i + 1 < len(lines)
                and MONTHS_RE.match(lines[i + 1]['text'])):
            nxt = lines[i + 1]
            merged.append({
                'top': line['top'],
                'words': sorted(line['words'] + nxt['words'], key=lambda w: w['x0']),
                'text': line['text'].strip() + ' ' + nxt['text'],
            })
            i += 2
        else:
            merged.append(line)
            i += 1
    return merged


def parse_pdf_to_df(pdf_path: str) -> pd.DataFrame:
    """Extracts transaction data from a PDF bank statement."""
    all_records = []
    # X positions of amount columns (detected from header)
    eingang_x = None  # ZAHLUNGSEINGANG column
    ausgang_x = None  # ZAHLUNGSAUSGANG column

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1, y_tolerance=3)
            lines = group_words_into_lines(words)

            # Detect column positions from header (use rightmost occurrence
            # to get the transaction table headers, not the overview headers)
            for L in lines:
                for w in L["words"]:
                    if w["text"] == "ZAHLUNGSEINGANG":
                        eingang_x = w["x0"]
                    elif w["text"] == "ZAHLUNGSAUSGANG":
                        ausgang_x = w["x0"]

            # Merge bare day numbers with following month lines
            lines = merge_date_lines(lines)

            page_records = []
            current_record = None
            date_re = re.compile(r"^\s*(\d{1,2}\s+\w+\.?)")

            for line in lines:
                if date_re.match(line["text"]):
                    if current_record:
                        page_records.append(current_record)
                    current_record = [line]
                elif current_record:
                    current_record.append(line)

            if current_record:
                page_records.append(current_record)

            all_records.extend(page_records)
            print(f"Page {page_num}: {len(page_records)} transactions extracted")

    # Midpoint between the two amount columns for classification
    col_midpoint = None
    if eingang_x is not None and ausgang_x is not None:
        col_midpoint = (eingang_x + ausgang_x) / 2

    data = []
    last_known_year = None
    year_re = re.compile(r'\b(20\d{2})\b')

    for rec in all_records:
        year = last_known_year
        full_rec_text = " ".join(line['text'] for line in rec)
        year_match = year_re.search(full_rec_text)
        if year_match:
            year = year_match.group(1)
            last_known_year = year
        if not year:
            continue

        first_line_text = rec[0]["text"]

        # Extract day number from the start of the first line
        day_match = re.match(r"^\s*(\d{1,2})\s+", first_line_text)
        if not day_match:
            continue
        day = day_match.group(1)

        # Try to find month right after the day on the first line
        rest_after_day = first_line_text[day_match.end():]
        month_match = re.match(rf"({MONTHS_PATTERN})\.?\s*", rest_after_day)

        if month_match:
            month = month_match.group(1)
            extra_desc = rest_after_day[month_match.end():].strip()
        else:
            # Month is on a subsequent line (day was on same Y as description)
            month = None
            for line in rec[1:]:
                m = re.match(rf"\s*({MONTHS_PATTERN})\.?\s*(.*)", line["text"])
                if m:
                    month = m.group(1)
                    break
            if not month:
                continue
            extra_desc = rest_after_day.strip()

        date = f"{day} {month}. {year}"

        stmt_line = next((L for L in rec if "€" in L["text"]), None)
        if not stmt_line:
            continue

        words_sl = stmt_line["words"]
        amt_list = []
        i = 0
        while i < len(words_sl):
            w = words_sl[i]; t = w["text"]
            if re.match(r"^-?[\d\.,]+\s*€$", t):
                amt_list.append({"text": t.strip(), "x0": w["x0"]})
                i += 1
            elif re.match(r"^-?[\d\.,]+$", t) and i + 1 < len(words_sl) and words_sl[i+1]["text"].startswith("€"):
                amt_list.append({"text": f"{t} €", "x0": w["x0"]})
                i += 2
            else:
                i += 1

        if len(amt_list) < 1: continue

        bal_w = max(amt_list, key=lambda w: w['x0'])
        cash_w_list = [w for w in amt_list if w != bal_w]

        if not cash_w_list: continue
        cash_w = cash_w_list[0]

        cash_val = to_float(cash_w["text"])
        balance_val = to_float(bal_w["text"])

        desc_parts = [extra_desc]
        for line in rec[1:]:
            desc_words = [w['text'] for w in line['words'] if w['x0'] < cash_w['x0']]
            desc_parts.append(" ".join(desc_words))

        description = " ".join(filter(None, desc_parts)).strip()
        description = " ".join(description.split())

        # Filter out footer text
        if "Trade Republic Bank GmbH" in description:
            description = description.split("Trade Republic Bank GmbH")[0].strip()

        tx_type = description.split(' ')[0] if description else 'N/A'

        # Use column position to determine Cash In vs Cash Out
        if col_midpoint is not None:
            is_income = cash_w["x0"] < col_midpoint
        else:
            is_income = any(kw in description for kw in INCOME_KEYWORDS)
        cash_in = abs(cash_val) if is_income else 0.0
        cash_out = 0.0 if is_income else abs(cash_val)

        data.append({
            "Date": date, "Type": tx_type, "Description": description,
            "Cash In": cash_in, "Cash Out": cash_out, "Total Balance": balance_val,
        })

    df = pd.DataFrame(data)
    df.drop_duplicates(subset=['Date', 'Total Balance'], inplace=True, keep='first')
    return df

def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "data/input/statement.pdf"
    output_csv = "data/temp/raw_transactions.csv"
    df = parse_pdf_to_df(pdf_path)
    print(f"\nSuccessfully read and extracted {len(df)} unique transactions")
    if df.empty:
        pd.DataFrame(columns=["Date", "Type", "Description", "Cash In", "Cash Out", "Total Balance"]).to_csv(output_csv, index=False)
    else:
        df.to_csv(output_csv, index=False)

if __name__ == "__main__":
    main()