#!/usr/bin/env python3
import os
import sys
import subprocess
import pdfplumber


def detect_bank(pdf_path: str) -> str:
    """Detect bank type from first page of PDF."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if pdf.pages:
                text = pdf.pages[0].extract_text() or ""
                if "COMMERZBANK" in text.upper() or "Kontoauszug" in text:
                    return "commerzbank"
    except Exception:
        pass
    return "trade_republic"


def run_step(script_path: str, args: list = None):
    cmd = [sys.executable, script_path] + (args or [])
    print(f"\n-> Running {script_path} ...")
    res = subprocess.run(cmd, check=False)
    if res.returncode != 0:
        print(f"{script_path} failed with exit code {res.returncode}")
        sys.exit(res.returncode)


def resolve_pdf_path(path: str) -> str:
    """Resolve PDF path, checking data/input/, data/, and root as fallbacks."""
    if os.path.isfile(path):
        return path
    basename = os.path.basename(path)
    for folder in ["data/input", "data", "."]:
        candidate = os.path.join(folder, basename)
        if os.path.isfile(candidate):
            return candidate
    return path  # return original so the error message is clear


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "data/input/statement.pdf"
    pdf_path = resolve_pdf_path(arg)

    # Derive output CSV path from input PDF name
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_csv = f"data/output/{pdf_name}.csv"

    os.makedirs("data/output", exist_ok=True)
    os.makedirs("data/temp", exist_ok=True)

    bank = detect_bank(pdf_path)
    print(f"Detected bank: {bank}")

    if bank == "commerzbank":
        run_step("src/extract_commerzbank.py", [pdf_path, output_csv])
        run_step("src/analyze_transactions.py", [output_csv])
    else:
        run_step("src/extract_transactions.py", [pdf_path])
        run_step("src/split_transactions.py")
        run_step("src/preprocess_transactions.py", [output_csv])
        run_step("src/analyze_transactions.py", [output_csv])

    print(f"\nAll steps completed successfully!")
    print(f"Output CSV: {output_csv}")


if __name__ == "__main__":
    main()
