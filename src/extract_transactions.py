#!/usr/bin/env python3
import re
import logging
logging.getLogger("pdfminer").setLevel(logging.ERROR)

import pdfplumber
import pandas as pd

CASH_COL_X0 = 420 # any amount with x0 < this → Cash In
BALANCE_COL_X0 = 500 # any amount with x0 ≥ this → Balance

def parse_pdf_to_df(pdf_path: str) -> pd.DataFrame:
    records = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=1, y_tolerance=1)

            # group words into lines by 'top'
            lines = []
            for w in words:
                placed = False
                for line in lines:
                    if abs(w["top"] - line["top"]) < 2:
                        line["words"].append(w)
                        placed = True
                        break
                if not placed:
                    lines.append({"top": w["top"], "words": [w]})
            lines.sort(key=lambda L: L["top"])
            for L in lines:
                L["words"].sort(key=lambda w: w["x0"])

            # build records: start on date-line, end on year-line
            date_re = re.compile(r"^\d{1,2}\s+\w+\.?" )
            year_re = re.compile(r"^(\d{4})\b")
            current = None

            for L in lines:
                text_line = " ".join(w["text"] for w in L["words"])
                if date_re.match(text_line):
                    current = [L]
                    continue
                if current is not None:
                    current.append(L)
                    if year_re.match(text_line):
                        records.append(current)
                        current = None

    data = []
    for rec in records:
        last_text = " ".join(w["text"] for w in rec[-1]["words"])
        m_year = re.match(r"^(\d{4})", last_text)
        if not m_year:
            continue
        year = m_year.group(1)

        first_words = rec[0]["words"]
        first_text = " ".join(w["text"] for w in first_words)
        m_date = re.match(r"(\d{1,2}\s+\w+\.?)", first_text)
        if m_date:
            date = f"{m_date.group(1)} {year}"
            date_tokens = m_date.group(1).split()
            extra_desc = " ".join(w["text"] for w in first_words[len(date_tokens):]).strip()
        else:
            date = year
            extra_desc = ""

        stmt_line = None
        year_re = re.compile(r"^(\d{4})\b")
        for L in rec[1:]:
            txt = " ".join(w["text"] for w in L["words"])
            if "€" in txt and not year_re.match(txt):
                stmt_line = L
                break
        if not stmt_line:
            continue

        words_sl = stmt_line["words"]

        amt_list = []
        i = 0
        while i < len(words_sl):
            w = words_sl[i]
            t = w["text"]
            if re.match(r"^[\d\.,]+\s*€$", t):
                amt_list.append({"text": t.strip(), "x0": w["x0"]})
                i += 1
            elif re.match(r"^[\d\.,]+$", t) and i + 1 < len(words_sl) and words_sl[i+1]["text"].startswith("€"):
                amt_list.append({"text": f"{t} €", "x0": w["x0"]})
                i += 2
            else:
                i += 1
        if len(amt_list) < 2:
            continue

        cash_w = next((w for w in amt_list if w["x0"] < CASH_COL_X0), None)
        bal_w  = next((w for w in amt_list if w["x0"] >= BALANCE_COL_X0), None)
        if not cash_w or not bal_w:
            cash_w, bal_w = amt_list[-2], amt_list[-1]

        def to_float(s: str) -> float:
            clean = s.replace("€", "").replace(".", "").replace(",", ".").strip()
            try:
                return float(clean)
            except ValueError:
                return 0.0

        cash_val    = to_float(cash_w["text"])
        balance_val = to_float(bal_w["text"])

        tx_type = words_sl[0]["text"]
        desc_tokens = []
        for w in words_sl[1:]:
            if w["x0"] >= cash_w["x0"]:
                break
            desc_tokens.append(w["text"])
        description = " ".join(filter(None, [extra_desc, *desc_tokens])).strip()

        if cash_w["x0"] < CASH_COL_X0:
            cash_in, cash_out = cash_val, 0.0
        else:
            cash_in, cash_out = 0.0, cash_val

        data.append({
            "Date": date,
            "Type": tx_type,
            "Description": description,
            "Cash In": cash_in,
            "Cash Out": cash_out,
            "Total Balance": balance_val,
        })

    return pd.DataFrame(data)


def main():
    df = parse_pdf_to_df("data/statement.pdf")
    df.to_csv("data/raw_transactions.csv", index=False)
    print(f"Successfully read and extracted {len(df)} transactions")


if __name__ == "__main__":
    main()