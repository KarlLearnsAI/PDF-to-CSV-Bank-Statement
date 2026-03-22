import sys
import re
import pandas as pd
from common import to_float, MONTHS_PATTERN, MONTH_MAP, INCOME_KEYWORDS

def parse_transaction_text(text: str) -> dict:
    """
    Parses a single line of transaction text into a structured dictionary.
    Returns None if the line is not a valid transaction.
    """
    date_re = re.compile(rf"^\s*(\d{{1,2}}\s+{MONTHS_PATTERN}\.?\s+\d{{4}})")
    
    date_match = date_re.match(text)
    if not date_match:
        return None  # This is not a valid transaction line.
    
    date = date_match.group(1)

    # Find all monetary values in the text.
    amounts = re.findall(r'(-?[\d\.,]+\s*€)', text)
    if len(amounts) < 2:
        return None # Must have at least a cash value and a balance

    balance_val = to_float(amounts[-1])
    cash_val = to_float(amounts[-2])

    # The description is what's left after removing the date and amounts.
    description = text.replace(date, '')
    for amt in amounts:
        description = description.replace(amt.strip(), '')
    
    description = " ".join(description.split())
    
    # Exclude any footer text that might have been accidentally included.
    if "Trade Republic Bank GmbH" in description:
        description = description.split("Trade Republic Bank GmbH")[0]

    if not description.strip():
        return None

    cash_in = cash_val if any(kw in description for kw in INCOME_KEYWORDS) else 0.0
    cash_out = 0.0 if cash_in > 0 else cash_val
    
    return {
        "Date": date,
        "Type": description.split(' ')[0],
        "Description": description,
        "Cash In": cash_in,
        "Cash Out": cash_out,
        "Total Balance": balance_val,
    }

def main():
    output_csv = sys.argv[1] if len(sys.argv) > 1 else "data/output/processed_transactions.csv"
    csv_in = "data/temp/splitted_raw_transactions.csv"
    try:
        df = pd.read_csv(csv_in)
    except FileNotFoundError:
        print(f"Input file not found: {csv_in}. Cannot preprocess.")
        pd.DataFrame().to_csv(output_csv, index=False)
        return

    processed_data = []
    if not df.empty:
        for text in df['TransactionText']:
            parsed = parse_transaction_text(text)
            if parsed:
                processed_data.append(parsed)

    final_df = pd.DataFrame(processed_data)

    if not final_df.empty:
        # Convert German month abbreviations to English for date parsing
        for ger, eng in MONTH_MAP.items():
            final_df['Date'] = final_df['Date'].str.replace(ger, eng)

        # Use a flexible date format
        final_df["Date"] = pd.to_datetime(final_df["Date"].str.replace(r'\.', '', regex=True), format="%d %b %Y", errors='coerce')
        final_df.dropna(subset=["Date"], inplace=True)

    print(f"Successfully preprocessed and saved {len(final_df)} transactions")
    final_df.to_csv(output_csv, index=False)

if __name__ == "__main__":
    main()