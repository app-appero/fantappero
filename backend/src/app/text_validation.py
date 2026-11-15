"""Validazioni di testo comuni agli schemi di input."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator


def reject_nul(value: str) -> str:
    """Il byte NUL non è testo valido e Postgres lo rifiuta con un 500: meglio un 422."""
    if "\x00" in value:
        msg = "Il testo contiene caratteri non validi."
        raise ValueError(msg)
    return value


NoNulStr = Annotated[str, AfterValidator(reject_nul)]
