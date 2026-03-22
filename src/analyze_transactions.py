import sys
import pandas as pd


def truncate(s, width):
    """Truncate string to width, adding '..' if truncated."""
    s = str(s)
    if len(s) <= width:
        return s
    return s[:width - 2] + ".."


def print_transactions(df):
    """Print all transactions in a formatted table."""
    col_widths = {"Date": 10, "Type": 15, "Description": 30, "Cash In": 10, "Cash Out": 10, "Total Balance": 12}
    header = "  ".join(col.ljust(col_widths[col]) for col in col_widths)
    separator = "  ".join("-" * col_widths[col] for col in col_widths)

    print(f"\n{header}")
    print(separator)
    for _, row in df.iterrows():
        date_str = row["Date"].strftime("%d.%m.%Y") if hasattr(row["Date"], "strftime") else str(row["Date"])[:10]
        cash_in = f'{row["Cash In"]:.2f}' if row["Cash In"] > 0 else ""
        cash_out = f'{row["Cash Out"]:.2f}' if row["Cash Out"] > 0 else ""
        balance = f'{row["Total Balance"]:.2f}'
        line = "  ".join([
            truncate(date_str, col_widths["Date"]).ljust(col_widths["Date"]),
            truncate(row["Type"], col_widths["Type"]).ljust(col_widths["Type"]),
            truncate(row["Description"], col_widths["Description"]).ljust(col_widths["Description"]),
            cash_in.rjust(col_widths["Cash In"]),
            cash_out.rjust(col_widths["Cash Out"]),
            balance.rjust(col_widths["Total Balance"]),
        ])
        print(line)
    print(separator)
    print(f"Total Cash In:  {df['Cash In'].sum():.2f}")
    print(f"Total Cash Out: {df['Cash Out'].sum():.2f}")
    print(f"Net:            {df['Cash In'].sum() - df['Cash Out'].sum():.2f}")


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/output/processed_transactions.csv"
    df = pd.read_csv(csv_path, parse_dates=["Date"])

    if df.empty:
        print("No transactions found.")
        return

    print_transactions(df)

if __name__ == "__main__":
    main()
