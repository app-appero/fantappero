"""Schemi HTTP condivisi: media stagionale, valore di mercato e storico del calciatore (1.3)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from auth.schemas import ApiModel


class AthleteSeasonAverageResponse(ApiModel):
    """Media stagionale nelle liste del mercato.

    ``isCurrent``: media dei nostri voti della stagione in corso (verde). Altrimenti è la media
    della stagione scorsa, ``seasonLabel`` tipo «25/26» (rossa).
    """

    value: float
    season_year: int = Field(alias="seasonYear")
    season_label: str = Field(alias="seasonLabel")
    is_current: bool = Field(alias="isCurrent")


class AthleteCareerRowResponse(ApiModel):
    """Una riga dello storico nella scheda calciatore (stagione + club + competizione)."""

    season_year: int = Field(alias="seasonYear")
    season_label: str = Field(alias="seasonLabel")
    is_current: bool = Field(alias="isCurrent")
    #: ``provider``: statistiche di stagione del fornitore; ``fantappero``: i nostri dati.
    source: Literal["provider", "fantappero"]
    club_id: str | None = Field(default=None, alias="clubId")
    club_name: str | None = Field(default=None, alias="clubName")
    competition_id: str | None = Field(default=None, alias="competitionId")
    competition_name: str | None = Field(default=None, alias="competitionName")
    appearances: int | None = None
    minutes: int | None = None
    #: Media voto: del fornitore per le stagioni passate, dei nostri voti per quella in corso.
    average_rating: float | None = Field(default=None, alias="averageRating")
    #: Partite con voto FantApperò (``null`` per le righe del fornitore).
    votes: int | None = None
    fantasy_average: float | None = Field(default=None, alias="fantasyAverage")
    goals: int | None = None
    assists: int | None = None
    goals_conceded: int | None = Field(default=None, alias="goalsConceded")
    saves: int | None = None
    penalties_saved: int | None = Field(default=None, alias="penaltiesSaved")
    yellow_cards: int | None = Field(default=None, alias="yellowCards")
    red_cards: int | None = Field(default=None, alias="redCards")
    #: Porte inviolate: solo portieri e solo dalla stagione in corso (``null`` altrimenti).
    clean_sheets: int | None = Field(default=None, alias="cleanSheets")
