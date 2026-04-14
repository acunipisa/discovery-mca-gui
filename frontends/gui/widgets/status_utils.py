from PyQt6.QtWidgets import QLabel


def set_status_badge(label: QLabel, text: str, kind: str):
    styles = {
        "green": "background-color: #d1fae5; color: #065f46; border: 1px solid #10b981;",
        "red": "background-color: #fee2e2; color: #991b1b; border: 1px solid #ef4444;",
        "yellow": "background-color: #fef3c7; color: #92400e; border: 1px solid #f59e0b;",
        "blue": "background-color: #dbeafe; color: #1e3a8a; border: 1px solid #3b82f6;",
        "gray": "background-color: #e5e7eb; color: #374151; border: 1px solid #9ca3af;",
    }

    base = "border-radius: 10px; " "padding: 3px 10px; " "font-weight: 600;"

    label.setText(text)
    label.setStyleSheet(base + styles.get(kind, styles["gray"]))
