"""Riparazione dei nomi del fornitore e confronto senza accenti (QA 20-21/11 e 21/11)."""

from __future__ import annotations

import pytest

from app.text_folding import repair_mojibake, repair_provider_text, strip_accents
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


# --- Riferimenti a caratteri dell'HTML (QA 21/11) ---------------------------------------------


@pytest.mark.parametrize(
    ("escaped", "expected"),
    [
        # Il nome visto dal tester nel listone (Ipswich) e le altre forme dello stesso apostrofo.
        ("D. O&apos;Shea", "D. O'Shea"),
        ("D. O&#39;Shea", "D. O'Shea"),
        ("D. O&#039;Shea", "D. O'Shea"),
        ("D. O&#x27;Shea", "D. O'Shea"),
        ("D. O&#X27;Shea", "D. O'Shea"),
        ("&quot;Kiko&quot; Casilla", '"Kiko" Casilla'),
        ("Brighton &amp; Hove Albion", "Brighton & Hove Albion"),
        ("Brighton &AMP; Hove Albion", "Brighton & Hove Albion"),
        ("N. Kant&eacute;", "N. Kanté"),
        ("Y. N&#8217;Dicka", "Y. N’Dicka"),
        # Escapati due e tre volte.
        ("D. O&amp;apos;Shea", "D. O'Shea"),
        ("D. O&amp;#039;Shea", "D. O'Shea"),
        ("D. O&amp;amp;apos;Shea", "D. O'Shea"),
        # Riferimenti e codifica rovinata nello stesso nome.
        ("D. O&apos;Shea JovanoviÄ‡", "D. O'Shea Jovanović"),
    ],
)
def test_repair_provider_text_decodes_html_character_references(
    escaped: str, expected: str
) -> None:
    assert repair_provider_text(escaped) == expected
    # Idempotente: ripararlo ancora non cambia niente.
    assert repair_provider_text(expected) == expected


@pytest.mark.parametrize(
    "text",
    [
        # Una "&" vera, senza riferimento.
        "Brighton & Hove Albion",
        "AT&T",
        "R&B",
        "Kiko &amp Casilla",
        # Nomi storici senza punto e virgola, o come prefisso: `html.unescape` li cambierebbe
        # ("¬te", "¬it;").
        "Bar &notte",
        "&notit;",
        "&copyright;",
        # Nomi che non sono riferimenti.
        "&foo;",
        "&A;",
        # Codici che non danno un carattere vero: nullo, controllo, invisibile, surrogato,
        # fuori da Unicode.
        "A&#0;B",
        "A&#10;B",
        "A&#x1;B",
        "A&shy;B",
        "A&#xD800;B",
        "A&#1114112;B",
        "",
    ],
)
def test_repair_provider_text_leaves_text_without_references_unchanged(text: str) -> None:
    assert repair_provider_text(text) == text


@pytest.mark.parametrize(
    "name",
    [
        "A. Dembélé",
        "A. Bayındır",
        "Š. Vrsaljko",
        "M. Ødegaard",
        "N’Dicka",
        "D. O'Shea",
        "François Ä",
    ],
)
def test_repair_provider_text_leaves_correct_names_unchanged(name: str) -> None:
    assert repair_provider_text(name) == name


@pytest.mark.parametrize(
    ("broken", "expected"),
    [
        ("L. JovanoviÄ\x87", "L. Jovanović"),
        ("L. JovanoviÄ‡", "L. Jovanović"),
        ("A. DembÃ©lÃ©", "A. Dembélé"),
        ("A. DembÃƒÂ©lÃƒÂ©", "A. Dembélé"),
        ("Y. Nâ€™Dicka", "Y. N’Dicka"),
    ],
)
def test_repair_provider_text_still_repairs_mojibake(broken: str, expected: str) -> None:
    assert repair_provider_text(broken) == expected == repair_mojibake(broken)


def test_repair_provider_text_leaves_text_escaped_too_many_times_as_it_is() -> None:
    # Escapato più volte delle passate: non si salva a metà, e resta idempotente.
    deep = "D. O&amp;amp;amp;amp;apos;Shea"
    assert repair_provider_text(deep) == deep
    assert repair_provider_text(repair_provider_text(deep)) == deep


def test_name_matching_finds_names_with_html_character_references() -> None:
    # Import rose: il nome salvato con il riferimento combacia con quello scritto nel file.
    assert normalize_athlete_name("D. O&apos;Shea") == normalize_athlete_name("D. O'Shea")
    assert normalize_athlete_name("D. O&amp;#039;Shea") == "d. o'shea"
    assert normalize_athlete_name("Brighton & Hove Albion") == "brighton & hove albion"
    # Probabili formazioni: stesso confronto.
    assert normalize_person("D. O&apos;Shea") == normalize_person("D. O'Shea") == "d oshea"


# --- Controlli C1 rimasti da soli (QA 21/11 su dev) ---------------------------------------------


@pytest.mark.parametrize(
    ("broken", "expected"),
    [
        # I due nomi trovati su dev: la lettera è già giusta, resta il controllo.
        ("D. Pejičić\x87", "D. Pejičić"),
        ("N. Kovač \x8d", "N. Kovač"),
        # Tolto il controllo non restano due spazi.
        ("N. Kovač \x8d Jr", "N. Kovač Jr"),
        ("\x87L. Modrić", "L. Modrić"),
        ("N. Kovač\x8d\x8d", "N. Kovač"),
        ("A\x80B", "AB"),
        ("A\x9fB", "AB"),
        # Con la codifica rovinata o un riferimento dell'HTML nello stesso nome.
        ("D. PejiÄ\x8diÄ\x87\x87", "D. Pejičić"),
        ("D. O&apos;Shea\x87", "D. O'Shea"),
    ],
)
def test_repair_provider_text_strips_stray_c1_controls(broken: str, expected: str) -> None:
    assert repair_provider_text(broken) == expected
    assert repair_provider_text(expected) == expected


@pytest.mark.parametrize(
    "text",
    [
        # Dopo il primo byte di una sequenza ("Â"-"ô") il controllo può essere ancora una
        # sequenza rovinata che non torna un carattere vero: resta com'è.
        "AÂ\x85B",
        "ÄÂ\x87",
        # Senza controlli, gli spazi doppi non si toccano.
        "A  B",
        " A ",
    ],
)
def test_repair_provider_text_keeps_c1_after_a_lead_byte_and_spaces_without_controls(
    text: str,
) -> None:
    assert repair_provider_text(text) == text


def test_athlete_name_str_repairs_names_in_responses() -> None:
    from pydantic import BaseModel

    from app.text_validation import AthleteNameStr

    class Row(BaseModel):
        name: AthleteNameStr
        other: AthleteNameStr | None = None

    assert Row(name="D. O&apos;Shea").name == "D. O'Shea"
    assert Row(name="L. JovanoviÄ\x87").name == "L. Jovanović"
    assert Row(name="D. Pejičić\x87").name == "D. Pejičić"
    assert Row(name="Brighton & Hove Albion").name == "Brighton & Hove Albion"
    assert Row(name="A. Dembélé", other=None).other is None
    assert Row(name="x", other="N. Kovač \x8d").other == "N. Kovač"
