"""Validazioni di testo comuni agli schemi di input e di risposta."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator

from app.text_folding import repair_provider_text

_INVALID_TEXT = "Il testo contiene caratteri non validi."


def has_lone_surrogate(value: str) -> bool:
    """Un surrogato UTF-16 isolato (es. JSON "\\ud83d") non è codificabile in UTF-8."""
    return any("\ud800" <= char <= "\udfff" for char in value)


def reject_surrogates(value: str) -> str:
    """Senza questo controllo l'encode in UTF-8 (o Postgres) fallisce con un 500."""
    if has_lone_surrogate(value):
        raise ValueError(_INVALID_TEXT)
    return value


def reject_nul(value: str) -> str:
    """Il byte NUL non è testo valido e Postgres lo rifiuta con un 500: meglio un 422.

    Rifiuta anche i surrogati UTF-16 isolati, per lo stesso motivo (QA 18/11).
    """
    if "\x00" in value:
        raise ValueError(_INVALID_TEXT)
    return reject_surrogates(value)


NoNulStr = Annotated[str, AfterValidator(reject_nul)]
# Per i campi in cui il NUL è già gestito più avanti (es. le righe del CSV).
NoSurrogateStr = Annotated[str, AfterValidator(reject_surrogates)]

# Nome di un calciatore (o di un club) come lo manda il fornitore, riparato quando esce
# dall'API: codifica rovinata ("L. JovanoviÄ\x87"), riferimenti dell'HTML ("D. O&apos;Shea")
# e controlli C1 rimasti da soli (QA 20-21/11 e 21/11). Così listone, rosa, formazione e le
# altre risposte mostrano il nome giusto anche se la riga salvata è ancora rovinata, senza
# aspettare la sincronizzazione o la riparazione dei nomi salvati. Un nome già giusto non cambia.
AthleteNameStr = Annotated[str, AfterValidator(repair_provider_text)]
