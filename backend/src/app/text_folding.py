"""Confronto dei nomi senza accenti, comune all'import delle rose e alle probabili formazioni."""

from __future__ import annotations

import re
import unicodedata

# Testo UTF-8 decodificato una seconda volta come Latin-1 o Windows-1252 (mojibake): ogni
# lettera accentata diventa due o tre caratteri, "ć" (C4 87) diventa "Ä\x87" o "Ä‡", "é"
# (C3 A9) diventa "Ã©". Così erano arrivati dal fornitore quattro nomi del listone, che la
# ricerca senza accenti non trovava (QA 20-21/11). Windows-1252 mette tra 0x80 e 0x9F
# caratteri tipografici al posto dei controlli C1: servono i loro byte originali.
_CP1252_BYTES: dict[str, int] = {
    char: byte
    for byte in range(0x80, 0xA0)
    if (char := bytes([byte]).decode("cp1252", errors="ignore"))
}

# Un carattere che sta per un byte di continuazione UTF-8 (0x80-0xBF).
_CONTINUATION = "[\u0080-¿" + "".join(re.escape(char) for char in _CP1252_BYTES) + "]"
# Una sequenza UTF-8 completa letta byte per byte: primo byte da 2 (C2-DF, "Â"-"ß"), da 3
# (E0-EF, "à"-"ï") o da 4 (F0-F4, "ð"-"ô"), poi le continuazioni.
_MOJIBAKE_SEQUENCE = re.compile(
    f"[Â-ß]{_CONTINUATION}|[à-ï]{_CONTINUATION}{{2}}|[ð-ô]{_CONTINUATION}{{3}}"
)
# Testo codificato due volte: al massimo tre passate, poi si lascia com'è.
_MAX_REPAIR_PASSES = 3


def _mojibake_byte(char: str) -> int:
    code = ord(char)
    return code if code <= 0xFF else _CP1252_BYTES[char]


def _repair_sequence(match: re.Match[str]) -> str:
    original = match.group(0)
    try:
        decoded = bytes(_mojibake_byte(char) for char in original).decode("utf-8")
    except (KeyError, UnicodeDecodeError):
        return original
    # Solo se torna un carattere vero: niente controlli, surrogati o punti non assegnati.
    if unicodedata.category(decoded).startswith("C"):
        return original
    return decoded


def repair_mojibake(value: str) -> str:
    """Ripara il testo UTF-8 letto per sbaglio come Latin-1 o Windows-1252.

    Prudente: tocca solo le sequenze che sono UTF-8 valido byte per byte e tornano un
    carattere vero, il resto del testo resta com'è. "L. JovanoviÄ\\x87" e "L. JovanoviÄ‡"
    diventano "L. Jovanović"; un nome già giusto ("A. Dembélé", "Š. Vrsaljko",
    "A. Bayındır") non cambia, e ripararlo due volte dà lo stesso risultato.
    """
    repaired = value
    for _ in range(_MAX_REPAIR_PASSES):
        candidate = _MOJIBAKE_SEQUENCE.sub(_repair_sequence, repaired)
        if candidate == repaired:
            break
        repaired = candidate
    return repaired


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
