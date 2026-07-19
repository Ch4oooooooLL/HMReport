"""Qt QSS Style Sheet for CAE Report Desktop application (Windows 10/11 Fluent Style)."""

CAE_DESKTOP_QSS = """
/* Global Window Style - Custom Frameless Container */
#FramelessContainer {
    background-color: #F3F3F3;
    border: 1px solid #D0D0D0;
    border-radius: 8px;
}

QMainWindow {
    background-color: transparent;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    color: #1A1A1A;
}

/* Custom Title Bar */
#CustomTitleBar {
    background-color: #FFFFFF;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    border-bottom: 1px solid #E5E5E5;
}

#TitleBarIcon {
    background-color: #0067C0;
    color: #FFFFFF;
    border-radius: 4px;
    font-weight: bold;
    font-size: 11px;
}

#TitleBarTitle {
    font-size: 12px;
    font-weight: 600;
    color: #333333;
}

/* Title Bar Control Buttons */
#TitleMinBtn, #TitleMaxBtn {
    background-color: transparent;
    border: none;
    border-radius: 0px;
    color: #555555;
    font-size: 13px;
}

#TitleMinBtn:hover, #TitleMaxBtn:hover {
    background-color: #E5E5E5;
    color: #000000;
}

#TitleCloseBtn {
    background-color: transparent;
    border: none;
    border-top-right-radius: 7px;
    color: #555555;
    font-size: 13px;
}

#TitleCloseBtn:hover {
    background-color: #E81123;
    color: #FFFFFF;
}

/* ToolBar Styling */
QToolBar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E5E5E5;
    padding: 4px 8px;
    spacing: 6px;
}

QToolBar QToolButton {
    color: #1F1F1F;
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 400;
}

QToolBar QToolButton:hover {
    background-color: #F5F5F5;
    border-color: #CCCCCC;
    color: #000000;
}

QToolBar QToolButton:pressed {
    background-color: #E9E9E9;
}

/* Left Sidebar Project List */
QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}

QListWidget::item {
    background-color: #FFFFFF;
    border: 1px solid #F0F0F0;
    border-radius: 4px;
    padding: 8px 10px;
    margin-bottom: 4px;
    color: #1F1F1F;
    font-size: 13px;
}

QListWidget::item:hover {
    background-color: #F5F5F5;
    border-color: #D0D0D0;
}

QListWidget::item:selected {
    background-color: #E5F3FF;
    border: 1px solid #0067C0;
    color: #003E78;
    font-weight: 600;
}

/* Header & Title Labels */
QLabel#ProjectTitle {
    font-size: 20px;
    font-weight: 600;
    color: #1A1A1A;
}

/* Form Layout Labels */
QFormLayout QLabel {
    font-size: 12px;
    color: #424242;
}

/* Standard Control Buttons - Win11 Design */
QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #D1D1D1;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
    color: #1F1F1F;
}

QPushButton:hover {
    background-color: #F8F8F8;
    border-color: #C7C7C7;
}

QPushButton:pressed {
    background-color: #F0F0F0;
}

QPushButton[primary="true"] {
    background-color: #0067C0;
    border-color: #0067C0;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton[primary="true"]:hover {
    background-color: #005A9E;
    border-color: #005A9E;
}

QPushButton[danger="true"] {
    background-color: #FFFFFF;
    border-color: #D13438;
    color: #D13438;
}

QPushButton[danger="true"]:hover {
    background-color: #FDF2F2;
    border-color: #A80000;
    color: #A80000;
}

/* Overall Progress Bar */
QProgressBar {
    border: 1px solid #D1D1D1;
    border-radius: 4px;
    text-align: center;
    background-color: #FFFFFF;
    color: #1F1F1F;
    font-size: 12px;
    height: 20px;
}

QProgressBar::chunk {
    background-color: #0067C0;
    border-radius: 3px;
}

/* Tasks Table */
QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    gridline-color: #F0F0F0;
    outline: none;
    font-size: 12px;
}

QTableWidget::item {
    padding: 5px 8px;
}

QHeaderView::section {
    background-color: #F9F9F9;
    color: #424242;
    padding: 6px 8px;
    font-weight: 600;
    font-size: 12px;
    border: none;
    border-bottom: 1px solid #E0E0E0;
}

/* Console Log Box */
QTextEdit#ConsoleLog {
    background-color: #FAFAFA;
    color: #262626;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    font-family: Consolas, "Segoe UI Mono", monospace;
    font-size: 12px;
    padding: 6px;
}

/* Status Bar */
QStatusBar {
    background-color: #F8F8F8;
    color: #616161;
    border-top: 1px solid #E5E5E5;
    border-bottom-left-radius: 7px;
    border-bottom-right-radius: 7px;
}

QStatusBar QLabel {
    color: #424242;
    padding: 0 8px;
    font-size: 12px;
}
"""


