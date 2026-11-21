"""Confronto dei nomi senza accenti, comune all'import delle rose e alle probabili formazioni."""

from __future__ import annotations

import re
import unicodedata
from html import unescape
from html.entities import html5 as _HTML5_REFERENCES

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


# Riferimenti a caratteri dell'HTML ("&apos;", "&amp;", "&#39;", "&#039;", "&#x27;"): il
# fornitore manda a volte i nomi così («D. O&apos;Shea», QA 21/11). Solo quelli chiusi dal
# punto e virgola, e per nome solo quelli della tabella HTML5 scritti per intero:
# `html.unescape` da solo decodifica anche i nomi storici senza punto e virgola o come
# prefisso ("&notte" diventerebbe "¬te", "&notit;" "¬it;"). Una "&" vera ("Brighton & Hove
# Albion", "AT&T") resta com'è.
_CHARACTER_REFERENCE = re.compile(
    r"&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});"
)
# Testo riparato a passate ("&amp;apos;" è "&apos;" escapato una seconda volta): se dopo
# queste non si è fermato, si lascia com'è, così ripararlo di nuovo non cambia niente.
_MAX_PROVIDER_TEXT_PASSES = 4


def _decode_reference(match: re.Match[str]) -> str:
    original = match.group(0)
    if original[1] == "#":
        decoded = unescape(original)
    else:
        decoded = _HTML5_REFERENCES.get(original[1:], original)
    # Solo caratteri veri: niente controlli ("&#10;"), caratteri invisibili ("&shy;") o il
    # carattere sostitutivo che `html.unescape` mette al posto di un codice non valido.
    if not decoded or any(
        char == "\ufffd" or unicodedata.category(char).startswith("C") for char in decoded
    ):
        return original
    return decoded


# Un controllo C1 (U+0080-U+009F) rimasto da solo dopo una lettera già giusta: «D. Pejičić\x87»,
# «N. Kovač \x8d» (QA 21/11 su dev). Non è testo e `repair_mojibake` non lo toglie, perché non
# fa parte di una sequenza UTF-8 completa. Si toglie solo se non segue un primo byte di una
# sequenza ("Â"-"ô"): lì può essere ancora una sequenza rovinata, e la si lascia com'è.
_STRAY_C1_CONTROL = re.compile(r"(?<![Â-ô])[\u0080-\u009f]")
_REPEATED_SPACES = re.compile(" {2,}")


def _strip_stray_c1_controls(value: str) -> str:
    stripped = _STRAY_C1_CONTROL.sub("", value)
    if stripped == value:
        return value
    # Tolto il controllo restano a volte due spazi o uno in fondo ("N. Kovač ").
    return _REPEATED_SPACES.sub(" ", stripped).strip()


def _repair_provider_pass(value: str) -> str:
    decoded = _CHARACTER_REFERENCE.sub(_decode_reference, repair_mojibake(value))
    return _strip_stray_c1_controls(decoded)


def repair_provider_text(value: str) -> str:
    """Ripara un testo del fornitore: codifica rovinata e riferimenti a caratteri dell'HTML.

    Fa quello che fa `repair_mojibake` e in più decodifica i riferimenti dell'HTML chiusi dal
    punto e virgola, anche escapati due o tre volte: "D. O&apos;Shea", "D. O&#039;Shea" e
    "D. O&amp;apos;Shea" diventano "D. O'Shea". Toglie anche i controlli C1 rimasti da soli
    dopo una lettera già giusta ("D. Pejičić\\x87" diventa "D. Pejičić"). Una "&" che non apre
    un riferimento ("Brighton & Hove Albion") resta com'è, come un nome già giusto.
    Idempotente: il risultato, riparato di nuovo, non cambia.
    """
    repaired = value
    for _ in range(_MAX_PROVIDER_TEXT_PASSES):
        candidate = _repair_provider_pass(repaired)
        if candidate == repaired:
            return repaired
        repaired = candidate
    # Ancora non stabile (testo escapato più volte delle passate): meglio non toccarlo che
    # salvarlo a metà, e una seconda riparazione darebbe un altro risultato.
    return value


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
