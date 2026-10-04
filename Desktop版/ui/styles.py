# UI Modern Dark Theme Stylesheet (QSS)

DARK_THEME_QSS = """
QMainWindow {
    background-color: #0b0f19;
}

QWidget {
    color: #f8fafc;
    font-family: 'Segoe UI', 'Yu Gothic UI', 'Meiryo', sans-serif;
    font-size: 13px;
}

/* ===== TAB WIDGET ===== */
QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: #0f172a;
    border-radius: 14px;
    margin-top: 8px;
    padding: 12px;
}

QTabBar::tab {
    background: #1e293b;
    color: #94a3b8;
    padding: 10px 24px;
    margin-right: 6px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: 600;
    font-size: 13px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-bottom: none;
}

QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
    color: #ffffff;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background: #334155;
    color: #f1f5f9;
}

/* ===== GROUP BOX & CARDS ===== */
QGroupBox {
    border: 1px solid rgba(255, 255, 255, 0.08);
    background-color: rgba(30, 41, 59, 0.6);
    border-radius: 12px;
    margin-top: 24px;
    padding: 16px 14px 14px 14px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 6px;
    color: #a78bfa;
    background-color: transparent;
    padding: 0 4px;
    font-size: 14px;
    font-weight: bold;
}

/* ===== INPUTS & CONTROLS ===== */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background-color: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    selection-background-color: #8b5cf6;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #8b5cf6;
    background-color: #0f172a;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: none;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.2);
    selection-background-color: #8b5cf6;
    color: #f8fafc;
    padding: 4px;
}

/* ===== BUTTONS ===== */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8b5cf6, stop:1 #7c3aed);
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #a78bfa, stop:1 #8b5cf6);
}

QPushButton:pressed {
    background: #6d28d9;
}

QPushButton:disabled {
    background-color: #334155;
    color: #64748b;
}

QPushButton.secondary {
    background: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #e2e8f0;
}

QPushButton.secondary:hover {
    background: #334155;
    border-color: rgba(255, 255, 255, 0.3);
}

QPushButton.teal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #14b8a6, stop:1 #0d9488);
}

QPushButton.teal:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2dd4bf, stop:1 #14b8a6);
}

QPushButton.danger {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ef4444, stop:1 #dc2626);
}

QPushButton.danger:hover {
    background: #f87171;
}

/* ===== SLIDERS ===== */
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #334155;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #8b5cf6;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #f8fafc;
    border: 2px solid #8b5cf6;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #ffffff;
    border-color: #ec4899;
}

/* ===== SCROLLBARS ===== */
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #64748b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* ===== STATUS BAR ===== */
QStatusBar {
    background: #0b0f19;
    color: #94a3b8;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
}
"""
