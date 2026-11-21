"""Riparazione della codifica rovinata dei nomi e confronto senza accenti (QA 20-21/11)."""

from __future__ import annotations

import pytest

from app.text_folding import repair_mojibake, strip_accents
from fantasy_teams.csv_import import normalize_athlete_name
from sports_data.predicted.names import normalize_person


@pytest.mark.parametrize(
    ("broken", "expected"),
    [
        # I quattro nomi del listone di dev: UTF-8 letto come Latin-1 (controlli C1).
        ("L. JovanoviÄ\x87", "L. Jovanović"),
        ("R. ObriÄ\x87", "R. Obrić"),
        ("D. PejiÄ\x8diÄ\x87", "D. Pejičić"),
        ("N. KovaÄ\x8d", "N. Kovač"),
        # Lo stesso letto come Windows-1252.
        ("L. JovanoviÄ‡", "L. Jovanović"),
        ("A. DembÃ©lÃ©", "A. Dembélé"),
        ("H. BellerÃ\xadn", "H. Bellerín"),
        ("M. Ã˜degaard", "M. Ødegaard"),
        ("A. BayÄ±ndÄ±r", "A. Bayındır"),
        # Codificato due volte.
        ("A. DembÃƒÂ©lÃƒÂ©", "A. Dembélé"),
        # Tre byte: l'apostrofo tipografico.
        ("Y. Nâ€™Dicka", "Y. N’Dicka"),
    ],
)
def test_repair_mojibake_fixes_utf8_read_as_latin1_or_cp1252(broken: str, expected: str) -> None:
    assert repair_mojibake(broken) == expected
    # Idempotente: ripararlo ancora non cambia niente.
    assert repair_mojibake(expected) == expected


@pytest.mark.parametrize(
    "name",
    [
        "A. Dembélé",
        "H. Bellerín",
        "K. Lomónaco",
        "A. Bayındır",
        "E. İlkhan",
        "Š. Vrsaljko",
        "Ž. Ivanušec",
        "L. Modrić",
        "D. Vlahović",
        "Đ. Petrović",
        "Ł. Skorupski",
        "M. Ødegaard",
        "P. Højbjerg",
        "V. Gyökeres",
        "N. Füllkrug",
        "Ç. Söyüncü",
        "H. Çalhanoğlu",
        "M. Vojvoda Mërgim",
        "João Mário",
        "Iñaki Williams",
        "Gonçalo Ramos",
        "Ángel Di María",
        "Óscar Mingueza",
        "Þ. Þórisson",
        "N’Dicka",
        "D’Ambrosio",
        "Nicolò Barella",
        "Mattéo Guendouzi",
        "Ümit Œzil",
        "François Ä",
        "",
    ],
)
def test_repair_mojibake_leaves_correct_names_unchanged(name: str) -> None:
    assert repair_mojibake(name) == name


def test_repair_mojibake_keeps_sequences_that_do_not_round_trip() -> None:
    # "Ã" seguito da un carattere che non è un byte di continuazione: non è mojibake.
    assert repair_mojibake("Ã Test") == "Ã Test"
    # Sequenza troncata: il primo byte da 3 vuole due continuazioni.
    assert repair_mojibake("Ä\x87 â€") == "ć â€"
    # Decodifica a un carattere di controllo (U+0085): si lascia com'è.
    assert repair_mojibake("AÂ\u0085B") == "AÂ\u0085B"


def test_accent_insensitive_matching_finds_broken_names() -> None:
    assert normalize_athlete_name("L. JovanoviÄ\x87") == normalize_athlete_name("l. jovanovic")
    assert normalize_athlete_name("N. KovaÄ\x8d") == "n. kovac"
    assert normalize_person("R. ObriÄ\x87") == normalize_person("R. Obric")
    # I nomi giusti si confrontano come prima.
    assert normalize_athlete_name("A. Dembélé") == "a. dembele"
    assert strip_accents("A. Bayındır") == "A. Bayindir"
