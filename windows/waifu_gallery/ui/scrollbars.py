CAPSULE_SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        background: transparent;
        border: 0;
        width: 6px;
        margin: 4px 2px;
    }
    QScrollBar::handle:vertical {
        background: #747B91;
        border-radius: 3px;
        min-height: 28px;
        width: 6px;
    }
    QScrollBar::handle:vertical:hover { background: #929AB1; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        height: 0;
        width: 0;
    }
"""
