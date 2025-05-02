# Simple PDF Bank Statement Reader

## How to use this application?
1) Simply put your bank statement into the ./data/statement.pdf folder and name it accordingly "statement.pdf"
2) Run "python src/main.py"

![Example Application Usage](data/example_usage.png)

### Note: Optimized for Trade Republic
- Otherwise you might want to adjust the parameters CASH_COL_X0 and BALANCE_COL_X0 to fit your bank's format
    - CASH_COL_X0: Distance to the right before which the Income is displayed (after that the Outcome should be displayed)
    - BALANCE_COL_X0: Distance to the right after the total balance is displayed
- Current Transaction Format (Trade Republic): Date, Transaction Type, Description, Income, Outcome, Total Balance