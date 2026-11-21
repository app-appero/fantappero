"""Riparazione dei nomi del fornitore già salvati: calciatori e club (QA 20-21/11 e 21/11).

Quattro nomi del listone di dev erano arrivati dal fornitore come testo UTF-8 decodificato
una seconda volta ("L. JovanoviÄ\\x87" invece di "L. Jovanović") e la ricerca senza accenti
non li trovava. Altri arrivano con i riferimenti a caratteri dell'HTML ("D. O&apos;Shea"
invece di "D. O'Shea", QA 21/11), e così li mostravano listone, sito e app. Le
sincronizzazioni ora salvano i nomi riparati (`repair_provider_text`); queste funzioni
riparano subito quelli già salvati, senza aspettare la prossima sincronizzazione.

Idempotenti: toccano solo i nomi che `repair_provider_text` cambia, cioè le sequenze UTF-8
valide lette come Latin-1/Windows-1252, i riferimenti dell'HTML chiusi dal punto e virgola e i
controlli C1 rimasti da soli dopo una lettera già giusta ("D. Pejičić\\x87").
Un nome già giusto, anche con una "&" vera ("Brighton & Hove Albion"), resta com'è, quindi un
secondo passaggio non trova più niente.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.text_folding import repair_provider_text
from sports_data.catalog.models import Club
from sports_data.roster.models import Athlete

#: Campi del calciatore con un nome da riparare.
REPAIRABLE_NAME_FIELDS = ("canonical_name", "first_name", "last_name")
#: Campi del club con un nome da riparare.
REPAIRABLE_CLUB_FIELDS = ("name",)

# Una sequenza rovinata comincia sempre con un carattere tra "Â" (U+00C2) e "ô" (U+00F4), un
# riferimento dell'HTML con "&", e un controllo C1 rimasto da solo ("D. Pejičić\x87") è tra
# U+0080 e U+009F: il filtro in SQL evita di leggere tutto il catalogo, la decisione la prende
# Python. I caratteri sono elencati uno per uno: un intervallo nella regex può dipendere dalla
# collation.
_SUSPICIOUS_PATTERN = (
    "[" + "".join(chr(code) for code in (*range(0x80, 0xA0), *range(0xC2, 0xF5))) + "&]"
)


@dataclass(frozen=True)
class RepairedAthleteName:
    """Un nome di calciatore riparato (o da riparare, in prova)."""

    athlete_id: UUID
    provider_id: int
    field: str
    before: str
    after: str


@dataclass(frozen=True)
class RepairedClubName:
    """Un nome di club riparato (o da riparare, in prova)."""

    club_id: UUID
    provider_id: int
    field: str
    before: str
    after: str


@dataclass(frozen=True)
class _Repair:
    row: Any
    field: str
    before: str
    after: str


def _repair_names(
    session: Session,
    model: type[Athlete] | type[Club],
    fields: Sequence[str],
    *,
    dry_run: bool,
) -> list[_Repair]:
    columns = [getattr(model, field) for field in fields]
    rows = session.scalars(
        select(model)
        .where(or_(*(column.regexp_match(_SUSPICIOUS_PATTERN) for column in columns)))
        .order_by(model.provider_id.asc())
    ).all()
    repaired: list[_Repair] = []
    for row in rows:
        for field in fields:
            value = getattr(row, field)
            if not value:
                continue
            fixed = repair_provider_text(value)
            if fixed == value:
                continue
            repaired.append(_Repair(row=row, field=field, before=value, after=fixed))
            if not dry_run:
                setattr(row, field, fixed)
    if repaired and not dry_run:
        session.flush()
    return repaired


def repair_athlete_names(session: Session, *, dry_run: bool = False) -> list[RepairedAthleteName]:
    """Ripara i nomi dei calciatori salvati rovinati; con ``dry_run`` li elenca soltanto.

    Non fa commit: lo decide il chiamante.
    """
    return [
        RepairedAthleteName(
            athlete_id=item.row.id,
            provider_id=item.row.provider_id,
            field=item.field,
            before=item.before,
            after=item.after,
        )
        for item in _repair_names(session, Athlete, REPAIRABLE_NAME_FIELDS, dry_run=dry_run)
    ]


def repair_club_names(session: Session, *, dry_run: bool = False) -> list[RepairedClubName]:
    """Ripara i nomi dei club salvati rovinati; con ``dry_run`` li elenca soltanto.

    Non fa commit: lo decide il chiamante.
    """
    return [
        RepairedClubName(
            club_id=item.row.id,
            provider_id=item.row.provider_id,
            field=item.field,
            before=item.before,
            after=item.after,
        )
        for item in _repair_names(session, Club, REPAIRABLE_CLUB_FIELDS, dry_run=dry_run)
    ]
