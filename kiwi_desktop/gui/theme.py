"""Centralized application theme constants and base QSS."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


class KIWTheme:
    """Theme palette + global stylesheet for the desktop UI. Supports dark and light modes."""

    current_mode: str = "dark"

    DARK: dict = {
        "bg_window":      "#0f0f13",
        "bg_panel":       "#1a1a22",
        "bg_card":        "#22222e",
        "bg_card_header": "#2a2a38",
        "bg_input":       "#1a1a28",
        "border":         "#35354a",
        "border_subtle":  "#28283a",
        "text_primary":   "#e8e8f0",
        "text_secondary": "#8888a8",
        "text_muted":     "#55556a",
        "accent":         "#4a7fff",
        "accent_hover":   "#6090ff",
        "success":        "#3a9e6e",
        "warning":        "#c89a20",
        "danger":         "#b84040",
        "btn_primary_bg": "#4a7fff",
        "btn_primary_fg": "#ffffff",
        "btn_neutral_bg": "#2d2d3d",
        "btn_neutral_fg": "#c0c0d8",
        "btn_danger_bg":  "#7a2828",
        "btn_danger_fg":  "#ffffff",
        "step_card_bg":   "#1e1e2a",
        "step_header_bg": "#2a2a38",
        "step_header_fg": "#9090b8",
    }

    LIGHT: dict = {
        "bg_window":      "#f5f7fa",
        "bg_panel":       "#ffffff",
        "bg_card":        "#f0f0f5",
        "bg_card_header": "#e8e8f0",
        "bg_input":       "#ffffff",
        "border":         "#d0d5dd",
        "border_subtle":  "#e8e8f0",
        "text_primary":   "#1a1a2e",
        "text_secondary": "#5a6070",
        "text_muted":     "#9090a0",
        "accent":         "#2563eb",
        "accent_hover":   "#4070d8",
        "success":        "#16a34a",
        "warning":        "#d97706",
        "danger":         "#dc2626",
        "btn_primary_bg": "#2563eb",
        "btn_primary_fg": "#ffffff",
        "btn_neutral_bg": "#f0f2f5",
        "btn_neutral_fg": "#1a1a2e",
        "btn_danger_bg":  "#dc2626",
        "btn_danger_fg":  "#ffffff",
        "step_card_bg":   "#f8f8fc",
        "step_header_bg": "#eeeef8",
        "step_header_fg": "#5a6070",
    }

    # ── Legacy constants kept for backward compatibility ──────────────────
    BG_DARK = "#1e1e1e"
    BG_PANEL = "#2d2d2d"
    BG_INPUT = "#3c3c3c"
    BORDER = "#555555"
    TEXT_PRIMARY = "#e8e8e8"
    TEXT_SECONDARY = "#a0a0a0"
    TEXT_MUTED = "#666666"
    ACCENT_PRIMARY = "#4a9eff"
    ACCENT_SUCCESS = "#3d9970"
    ACCENT_WARNING = "#e6a817"
    ACCENT_DANGER = "#cc4444"
    ACCENT_MUTED = "#5a5a5a"
    FONT_FAMILY = "Segoe UI"
    FONT_SIZE_SM = 11
    FONT_SIZE_MD = 12
    FONT_SIZE_LG = 13

    @classmethod
    def colors(cls) -> dict:
        return cls.DARK if cls.current_mode == "dark" else cls.LIGHT

    @classmethod
    def toggle(cls) -> str:
        cls.current_mode = "light" if cls.current_mode == "dark" else "dark"
        return cls.current_mode

    @classmethod
    def apply_full_stylesheet(cls, app: QApplication, mode: str = "dark") -> None:
        """Build and apply the full QSS stylesheet for the given mode."""
        cls.current_mode = mode
        c = cls.colors()
        app.setFont(QFont(cls.FONT_FAMILY, cls.FONT_SIZE_MD))
        app.setStyleSheet(
            f"QWidget {{"
            f"  background-color: {c['bg_window']};"
            f"  color: {c['text_primary']};"
            f"  font-family: {cls.FONT_FAMILY};"
            f"  font-size: {cls.FONT_SIZE_MD}pt;"
            f"}}"
            f"QMainWindow {{"
            f"  background-color: {c['bg_window']};"
            f"}}"
            f"QLabel {{"
            f"  color: {c['text_primary']};"
            f"  background-color: transparent;"
            f"}}"
            f"QGroupBox {{"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"  border: 1px solid {c['border']};"
            f"  border-radius: 8px;"
            f"  margin-top: 0px;"
            f"  padding: 0px;"
            f"  background-color: {c['bg_panel']};"
            f"}}"
            f"QGroupBox::title {{"
            f"  subcontrol-origin: margin;"
            f"  subcontrol-position: top left;"
            f"  padding: 2px 8px;"
            f"  color: {c['accent']};"
            f"}}"
            f"QLineEdit, QComboBox, QAbstractSpinBox {{"
            f"  background-color: {c['bg_input']};"
            f"  color: {c['text_primary']};"
            f"  border: 1px solid {c['border']};"
            f"  border-radius: 4px;"
            f"  padding: 4px 8px;"
            f"  selection-background-color: {c['accent']};"
            f"  selection-color: #ffffff;"
            f"}}"
            f"QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{"
            f"  color: {c['text_muted']};"
            f"}}"
            f"QPushButton {{"
            f"  background-color: {c['btn_neutral_bg']};"
            f"  color: {c['btn_neutral_fg']};"
            f"  border: 1px solid {c['border']};"
            f"  border-radius: 5px;"
            f"  padding: 5px 10px;"
            f"  font-size: 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  border-color: {c['accent']};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: {c['bg_panel']};"
            f"}}"
            f"QPushButton:disabled {{"
            f"  color: {c['text_muted']};"
            f"  border-color: {c['border']};"
            f"  background-color: {c['bg_panel']};"
            f"}}"
            f"QPushButton[class='btn-primary'], QPushButton[kiwClass='btn-primary'] {{"
            f"  background-color: {c['btn_primary_bg']};"
            f"  color: {c['btn_primary_fg']};"
            f"  border: 1px solid {c['btn_primary_bg']};"
            f"}}"
            f"QPushButton[class='btn-danger'], QPushButton[kiwClass='btn-danger'] {{"
            f"  background-color: {c['btn_danger_bg']};"
            f"  color: {c['btn_danger_fg']};"
            f"  border: 1px solid {c['btn_danger_bg']};"
            f"}}"
            f"QTabWidget::pane {{"
            f"  border: none;"
            f"  background: {c['bg_window']};"
            f"}}"
            f"QTabBar {{"
            f"  background: {c['bg_panel']};"
            f"  border-bottom: 1px solid {c['border']};"
            f"}}"
            f"QTabBar::tab {{"
            f"  background: transparent;"
            f"  color: {c['text_muted']};"
            f"  padding: 9px 18px;"
            f"  font-size: 11px;"
            f"  font-weight: bold;"
            f"  letter-spacing: 0.06em;"
            f"  border: none;"
            f"  border-bottom: 2px solid transparent;"
            f"  margin-right: 2px;"
            f"}}"
            f"QTabBar::tab:selected {{"
            f"  color: {c['text_primary']};"
            f"  border-bottom: 2px solid {c['accent']};"
            f"  background: transparent;"
            f"}}"
            f"QTabBar::tab:hover:!selected {{"
            f"  color: {c['text_secondary']};"
            f"  background: {c['bg_card']};"
            f"}}"
            f"QTableWidget, QTableView {{"
            f"  background-color: {c['bg_panel']};"
            f"  alternate-background-color: {c['bg_card']};"
            f"  gridline-color: {c['border_subtle']};"
            f"  color: {c['text_primary']};"
            f"  border: 1px solid {c['border']};"
            f"  selection-background-color: {c['accent']};"
            f"  selection-color: #ffffff;"
            f"}}"
            f"QHeaderView::section {{"
            f"  background-color: {c['bg_card']};"
            f"  color: {c['text_secondary']};"
            f"  border: none;"
            f"  border-bottom: 1px solid {c['border']};"
            f"  border-right: 1px solid {c['border_subtle']};"
            f"  padding: 6px 8px;"
            f"  font-weight: bold;"
            f"  font-size: 10px;"
            f"}}"
            f"QScrollBar:vertical, QScrollBar:horizontal {{"
            f"  background: transparent;"
            f"  border: none;"
            f"  margin: 0px;"
            f"}}"
            f"QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{"
            f"  background: {c['border']};"
            f"  border-radius: 4px;"
            f"  min-height: 24px;"
            f"  min-width: 24px;"
            f"}}"
            f"QScrollBar::add-line, QScrollBar::sub-line,"
            f"QScrollBar::add-page, QScrollBar::sub-page {{"
            f"  background: transparent;"
            f"  border: none;"
            f"}}"
        )

    @classmethod
    def apply_base_stylesheet(cls, app: QApplication) -> None:
        """Apply the default (dark) stylesheet on launch."""
        cls.apply_full_stylesheet(app, mode="dark")
