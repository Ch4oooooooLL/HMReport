"""Qt QSS Style Sheet for CAE Report Desktop application."""

CAE_DESKTOP_QSS = """
/* Global Window Style */
QMainWindow {
    background-color: #F8FAFC;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    color: #0F172A;
}

/* ToolBar Styling */
QToolBar {
    background-color: #0F172A;
    border-bottom: 2px solid #0284C7;
    padding: 6px 10px;
    spacing: 8px;
}

QToolBar QToolButton {
    color: #F8FAFC;
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 500;
}

QToolBar QToolButton:hover {
    background-color: #0284C7;
    border-color: #38BDF8;
    color: white;
}

QToolBar QToolButton:pressed {
    background-color: #0369A1;
}

/* Left Sidebar Project List */
QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 6px;
    outline: none;
}

QListWidget::item {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 10px;
    margin-bottom: 6px;
    color: #1E293B;
}

QListWidget::item:hover {
    background-color: #F0F9FF;
    border-color: #38BDF8;
}

QListWidget::item:selected {
    background-color: #E0F2FE;
    border: 1px solid #0284C7;
    color: #0369A1;
    font-weight: bold;
}

/* Header & Detail Panel */
QLabel#ProjectTitle {
    font-size: 22px;
    font-weight: bold;
    color: #0F172A;
    padding-bottom: 4px;
}

/* Action Control Buttons */
QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
    color: #1E293B;
}

QPushButton:hover {
    background-color: #F1F5F9;
    border-color: #94A3B8;
}

QPushButton[primary="true"] {
    background-color: #0284C7;
    border-color: #0284C7;
    color: #FFFFFF;
    font-weight: bold;
}

QPushButton[primary="true"]:hover {
    background-color: #0369A1;
    border-color: #0369A1;
}

QPushButton[danger="true"] {
    background-color: #FEF2F2;
    border-color: #FCA5A5;
    color: #DC2626;
}

QPushButton[danger="true"]:hover {
    background-color: #EF4444;
    color: #FFFFFF;
}

/* Overall Progress Bar */
QProgressBar {
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    text-align: center;
    background-color: #F1F5F9;
    color: #0F172A;
    font-weight: bold;
    font-size: 12px;
    height: 22px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8);
    border-radius: 5px;
}

/* Tasks Table */
QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    gridline-color: #F1F5F9;
    outline: none;
    font-size: 13px;
}

QTableWidget::item {
    padding: 6px 8px;
}

QHeaderView::section {
    background-color: #F1F5F9;
    color: #475569;
    padding: 8px;
    font-weight: bold;
    font-size: 12px;
    border: none;
    border-bottom: 2px solid #E2E8F0;
}

/* Console Log Box */
QTextEdit#ConsoleLog {
    background-color: #0F172A;
    color: #38BDF8;
    border: 1px solid #1E293B;
    border-radius: 6px;
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
    padding: 8px;
}

/* Status Bar */
QStatusBar {
    background-color: #0F172A;
    color: #94A3B8;
    border-top: 1px solid #1E293B;
}

QStatusBar QLabel {
    color: #CBD5E1;
    padding: 0 10px;
    font-family: Consolas, monospace;
    font-size: 12px;
}
"""
