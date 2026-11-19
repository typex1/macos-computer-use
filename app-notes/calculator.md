# Calculator (macOS)

Fully accessible. Keys are `Button` elements titled by their label: digits
'0'..'9', 'Add', 'Subtract', 'Multiply', 'Divide', 'Equals', 'All Clear',
'Delete', 'Percent', 'Open Parenthesis', scientific keys like 'X Squared'.
Use `--exact`: without it "1" matches "10 to the X" and "2" matches
"X Squared". Result lives in `ScrollArea 'Edit field'` > `StaticText`; the
expression in `ScrollArea 'Last Expression'`. Text contains U+200E marks.

    ax.py --app Calculator click "All Clear" --role Button --exact
    ax.py --app Calculator click "1" --role Button --exact   # ... 3, Multiply, 2, 4, Equals
    ax.py --app Calculator tree | grep -A1 "Edit field"
