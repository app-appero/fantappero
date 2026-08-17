"""Errori di dominio per il voto statistico (EP07-01)."""

from __future__ import annotations


class FantasyRatingError(Exception):
    """Errore di dominio sul calcolo o la lettura dei voti."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
