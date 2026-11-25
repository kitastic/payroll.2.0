"""Tiny event hub so tabs can refresh each other without importing each other."""
from __future__ import annotations

from typing import Callable

from controllers.app_controller import AppController


class ViewState:
    def __init__(self, ctrl: AppController):
        self.ctrl = ctrl
        self._listeners: dict[str, list[Callable]] = {}

    def on(self, event: str, fn: Callable) -> None:
        self._listeners.setdefault(event, []).append(fn)

    def emit(self, event: str, *args) -> None:
        for fn in self._listeners.get(event, []):
            fn(*args)

    # events used: 'salons_changed', 'sales_changed', 'employees_changed'
