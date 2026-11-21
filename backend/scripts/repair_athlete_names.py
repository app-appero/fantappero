"""Ripara i nomi di calciatori e club salvati rovinati dal fornitore (QA 20-21/11 e 21/11).

Due difetti: testo UTF-8 letto come Latin-1/Windows-1252 ("L. JovanoviÄ\\x87" diventa
"L. Jovanović") e riferimenti a caratteri dell'HTML ("D. O&apos;Shea", "D. O&#039;Shea" e
"D. O&amp;apos;Shea" diventano "D. O'Shea"). Tocca solo i nomi che tornano puliti; i nomi
giusti restano come sono, anche con una "&" vera ("Brighton & Hove Albion"), quindi si può
rilanciare quante volte si vuole (la seconda volta non trova niente).

Esempi (dalla cartella ``backend``, con ``DATABASE_URL`` dell'ambiente):

  # Solo elenco «prima -> dopo», nessuna modifica
  python scripts/repair_athlete_names.py --dry-run

  # Riparazione
  python scripts/repair_athlete_names.py

  # Docker Compose, dalla radice del monorepo
  docker compose --env-file infra/local/.env.example run --rm api \\
    python scripts/repair_athlete_names.py --dry-run
"""

from __future__ import annotations

import argparse
import sys

import database.models  # noqa: F401 — register ORM mappers
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from sports_data.roster.name_repair import repair_athlete_names, repair_club_names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ripara i nomi di calciatori e club con la codifica rovinata o con i riferimenti "
            "dell'HTML (&apos;, &amp;, &#39;)."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Elenca i nomi da riparare (prima -> dopo) senza modificarli.",
    )
    args = parser.parse_args(argv)

    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            athletes = repair_athlete_names(session, dry_run=args.dry_run)
            clubs = repair_club_names(session, dry_run=args.dry_run)
            if args.dry_run:
                session.rollback()
    finally:
        engine.dispose()

    for item in athletes:
        print(f"calciatore {item.provider_id} {item.field}: {item.before!r} -> {item.after!r}")
    for club in clubs:
        print(f"club {club.provider_id} {club.field}: {club.before!r} -> {club.after!r}")
    action = "da riparare" if args.dry_run else "riparati"
    print(f"nomi {action}: {len(athletes)} di calciatori, {len(clubs)} di club")
    return 0


if __name__ == "__main__":
    sys.exit(main())
