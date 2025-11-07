"""
Dialog utilities for consistent dialog styling and behavior.

This module provides centralized functions for common dialog operations
with consistent styling and theme integration.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QMessageBox, QWidget


def show_info(parent: Optional[QWidget], title: str, message: str) -> None:
    """
    Show an information dialog.
    
    Args:
        parent: Parent widget for the dialog
        title: Dialog title
        message: Message to display
    """
    QMessageBox.information(parent, title, message)


def show_warning(parent: Optional[QWidget], title: str, message: str) -> None:
    """
    Show a warning dialog.
    
    Args:
        parent: Parent widget for the dialog
        title: Dialog title
        message: Message to display
    """
    QMessageBox.warning(parent, title, message)


def show_error(parent: Optional[QWidget], title: str, message: str) -> None:
    """
    Show an error dialog.
    
    Args:
        parent: Parent widget for the dialog
        title: Dialog title
        message: Message to display
    """
    QMessageBox.critical(parent, title, message)


def show_question(
    parent: Optional[QWidget],
    title: str,
    message: str,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes
) -> QMessageBox.StandardButton:
    """
    Show a question dialog.
    
    Args:
        parent: Parent widget for the dialog
        title: Dialog title
        message: Message to display
        buttons: Button flags (default: Yes | No)
        default_button: Default button (default: Yes)
        
    Returns:
        The button that was clicked
    """
    reply = QMessageBox.question(parent, title, message, buttons, default_button)
    return reply


def show_confirmation(parent: Optional[QWidget], title: str, message: str) -> bool:
    """
    Show a confirmation dialog.
    
    Args:
        parent: Parent widget for the dialog
        title: Dialog title
        message: Message to display
        
    Returns:
        True if user clicked Yes, False otherwise
    """
    reply = show_question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes
    )
    return reply == QMessageBox.StandardButton.Yes


__all__ = [
    'show_info',
    'show_warning',
    'show_error',
    'show_question',
    'show_confirmation',
]

