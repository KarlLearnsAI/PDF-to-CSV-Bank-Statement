#!/usr/bin/env python3
import re
import logging
from typing import List, Dict, Any
import pdfplumber
import pandas as pd

# Suppress verbose logs from the PDF library
logging.getLogger("pdfminer").setLevel(logging.ERROR)

def to_float(s: str) -> float:
    """Converts a European-formatted currency string to a clean float."""
    if not isinstance(s, str): return 0.0
    clean = s.replace("€", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(clean)
    except (ValueError, TypeError):
        return 0.0

def parse_pdf_to_df(pdf_path: str) -> pd.DataFrame:
    """Extracts transaction data from a PDF bank statement."""
    all_records = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            lines: List[Dict[str, Any]] = []
            for w in page.extract_words(x_tolerance=1, y_tolerance=3):
                placed = False
                for line in lines:
                    if abs(w["top"] - line["top"]) < 4:
                        line["words"].append(w)
                        placed = True
                        break
                if not placed:
                    lines.append({"top": w["top"], "words": [w]})
            
            lines.sort(key=lambda L: L["top"])
            for L in lines:
                L["words"].sort(key=lambda w: w["x0"])
                L["text"] = " ".join(w["text"] for w in L["words"])

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
        m_date = re.match(r"^\s*(\d{1,2}\s+\w+\.?)", first_line_text)
        if not m_date:
            continue
        
        date_str = m_date.group(1)
        extra_desc = first_line_text[m_date.end():].strip()
        date = f"{date_str} {year}"

        stmt_line = next((L for L in rec if "€" in L["text"]), None)
        if not stmt_line:
            continue

        words_sl = stmt_line["words"]
        amt_list = []
        i = 0
        while i < len(words_sl):
            w = words_sl[i]; t = w["text"]
            if re.match(r"^[\d\.,]+\s*€$", t):
                amt_list.append({"text": t.strip(), "x0": w["x0"]})
                i += 1
            elif re.match(r"^[\d\.,]+$", t) and i + 1 < len(words_sl) and words_sl[i+1]["text"].startswith("€"):
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
        
        tx_type = description.split(' ')[0] if description else 'N/A'
        
        cash_in = cash_val if any(kw in description for kw in ["Incoming", "Zinszahlung", "Gutschrift"]) else 0.0
        cash_out = 0.0 if cash_in > 0 else cash_val

        data.append({
            "Date": date, "Type": tx_type, "Description": description,
            "Cash In": cash_in, "Cash Out": cash_out, "Total Balance": balance_val,
        })

    df = pd.DataFrame(data)
    df.drop_duplicates(subset=['Date', 'Total Balance'], inplace=True, keep='first')
    return df

def main():
    df = parse_pdf_to_df("data/statement.pdf")
    print(f"\nSuccessfully read and extracted {len(df)} unique transactions")
    if df.empty:
        pd.DataFrame(columns=["Date", "Type", "Description", "Cash In", "Cash Out", "Total Balance"]).to_csv("data/raw_transactions.csv", index=False)
    else:
        df.to_csv("data/raw_transactions.csv", index=False)

if __name__ == "__main__":
    main()