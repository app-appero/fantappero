"""Normalizzazione nomi per collegare FotMob ai club e ai calciatori interni.

Gli id FotMob non sono gli id del provider calcistico già in uso: il
collegamento passa solo da questi confronti, e un pareggio ambiguo non
viene risolto a forza.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

_NOISE = re.compile(
    r"\b(fc|cf|afc|sc|ssc|ac|us|as|calcio|club|de|the|04|1899|1846)\b",
)

# Dopo la pulizia dei suffissi societari. Chiavi e valori sono già normalizzati.
_CLUB_ALIASES = {
    "man united": "manchester united",
    "man utd": "manchester united",
    "manchester utd": "manchester united",
    "man city": "manchester city",
    "internazionale": "inter",
    "inter milan": "inter",
    "bayern munich": "bayern munchen",
    "psg": "paris saint germain",
    "paris sg": "paris saint germain",
    "wolves": "wolverhampton",
    "wolverhampton wanderers": "wolverhampton",
    "spurs": "tottenham hotspur",
    "tottenham": "tottenham hotspur",
    "newcastle": "newcastle united",
    "nottm forest": "nottingham forest",
    "nottingham": "nottingham forest",
    "atletico madrid": "atletico madrid",
    "atl madrid": "atletico madrid",
    "sporting cp": "sporting",
    "sporting lisbon": "sporting",
    "leverkusen": "bayer leverkusen",
}


def normalize_person(value: str | None) -> str:
    """Minuscolo, senza accenti né punteggiatura."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("'", "").replace("`", "")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_club(value: str | None) -> str:
    text = normalize_person(value)
    text = _NOISE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _CLUB_ALIASES.get(text, text)


def clubs_match(left: str | None, right: str | None) -> bool:
    """True se i due nomi di club indicano la stessa squadra."""
    normalized_left = normalize_club(left)
    normalized_right = normalize_club(right)
    if not normalized_left or not normalized_right:
        return False
    if normalized_left == normalized_right:
        return True
    if len(normalized_left) >= 5 and (
        normalized_left in normalized_right or normalized_right in normalized_left
    ):
        return True
    left_tokens = {token for token in normalized_left.split() if len(token) >= 4}
    right_tokens = {token for token in normalized_right.split() if len(token) >= 4}
    if not left_tokens or not right_tokens:
        return False
    shorter, longer = (
        (left_tokens, right_tokens)
        if len(left_tokens) <= len(right_tokens)
        else (right_tokens, left_tokens)
    )
    return shorter <= longer


@dataclass(frozen=True)
class SquadPlayer:
    athlete_id: UUID
    canonical_name: str
    first_name: str | None = None
    last_name: str | None = None


def match_squad_player(name: str | None, squad: Sequence[SquadPlayer]) -> UUID | None:
    """Collega un nome FotMob a un solo calciatore della rosa. Se non è univoco, None."""
    target = normalize_person(name)
    if not target or not squad:
        return None

    exact = [player for player in squad if normalize_person(player.canonical_name) == target]
    if len(exact) == 1:
        return exact[0].athlete_id
    if len(exact) > 1:
        return None

    composed = [
        player
        for player in squad
        if normalize_person(f"{player.first_name or ''} {player.last_name or ''}") == target
    ]
    if len(composed) == 1:
        return composed[0].athlete_id
    if len(composed) > 1:
        return None

    tokens = target.split()
    if len(tokens) >= 2 and len(tokens[0]) <= 2:
        initial = tokens[0][0]
        last = " ".join(tokens[1:])
        # Un calciatore in rosa senza nome proprio noto (es. anagrafica
        # incompleta: `canonical_name` è solo il cognome) non va scartato per
        # questo: non possiamo confermare l'iniziale, ma nemmeno escluderla.
        # Altrimenti un cognome univoco smette di abbinarsi solo perché la
        # rosa non ha il nome proprio, mentre un compagno con anagrafica
        # completa continua ad abbinarsi — esattamente il tipo di asimmetria
        # che fa sembrare "rotto" un singolo giocatore.
        hits = [
            player
            for player in squad
            if _last_name(player) == last
            and (_first_initial(player) == initial or _first_initial(player) == "")
        ]
        if len(hits) == 1:
            return hits[0].athlete_id

    last_token = tokens[-1] if tokens else ""
    if len(last_token) < 4:
        return None
    hits = [player for player in squad if _last_name(player) == last_token]
    if len(tokens) > 1:
        first = tokens[0]
        refined: list[SquadPlayer] = []
        for player in hits:
            given = _given_name(player)
            if not given:
                # Nome proprio sconosciuto in rosa: il cognome resta l'unico
                # segnale disponibile, non lo invalidiamo.
                refined.append(player)
            elif given.startswith(first) or (len(first) == 1 and given.startswith(first)):
                refined.append(player)
        hits = refined
    if len(hits) == 1:
        return hits[0].athlete_id
    return None


def _last_name(player: SquadPlayer) -> str:
    explicit = normalize_person(player.last_name)
    if explicit:
        return explicit
    parts = normalize_person(player.canonical_name).split()
    return parts[-1] if parts else ""


def _given_name(player: SquadPlayer) -> str:
    explicit = normalize_person(player.first_name)
    if explicit:
        return explicit
    parts = normalize_person(player.canonical_name).split()
    return parts[0] if len(parts) > 1 else ""


def _first_initial(player: SquadPlayer) -> str:
    given = _given_name(player)
    return given[:1]
