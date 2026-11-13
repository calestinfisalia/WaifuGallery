CAPSULE_SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        background: transparent;
        border: 0;
        width: 8px;
        margin: 4px 1px;
    }
    QScrollBar::handle:vertical {
        background: #626A80;
        border-radius: 3px;
        min-height: 32px;
        width: 6px;
    }
    QScrollBar::handle:vertical:hover { background: #929AB1; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
        border: 0;
        height: 0;
        width: 0;
        min-height: 0;
        min-width: 0;
    }
"""
