"""Confronto dei nomi senza accenti, comune all'import delle rose e alle probabili formazioni."""

from __future__ import annotations

import unicodedata

# Lettere che la scomposizione Unicode (NFKD) non separa dall'accento: senza questa
# tabella "A. Bayındır" (ı turca senza punto) non combacia con "A. Bayindir"
# (QA 19-20/11). Sono le stesse che la ricerca nel listone ignora su web e mobile.
_NON_DECOMPOSING = str.maketrans(
    {
        "ı": "i",
        "ø": "o",
        "Ø": "O",
        "ł": "l",
        "Ł": "L",
        "đ": "d",
        "Đ": "D",
        "ð": "d",
        "Ð": "D",
        "æ": "ae",
        "Æ": "AE",
        "œ": "oe",
        "Œ": "OE",
        "þ": "th",
        "Þ": "TH",
        "ß": "ss",
    }
)


def strip_accents(value: str) -> str:
    """Il testo senza accenti né segni diacritici; maiuscole e spazi restano come sono.

    "Dembélé" diventa "Dembele", la İ turca diventa "I", la ı turca "i".
    """
    decomposed = unicodedata.normalize("NFKD", value)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return plain.translate(_NON_DECOMPOSING)
