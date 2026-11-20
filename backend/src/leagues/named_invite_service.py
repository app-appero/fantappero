"""Fantasy-coach directory and transactional named invitations."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Literal, NoReturn
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from auth.models.user_profile import UserProfile
from auth.rate_limit import AuthRateLimiter
from authorization.context import LeagueAccess
from database.enums import (
    LeagueAuditAction,
    LeagueMemberRole,
    LeagueRole,
    NamedInviteStatus,
    NotificationCategory,
    PlatformRole,
    UserType,
)
from fantasy_teams.factory import ensure_team_for_membership
from leagues.coach_history import placements_page, seniority_label, summary_line
from leagues.coach_history_service import load_histories, load_history
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.named_league_invite import NamedLeagueInvite
from leagues.schemas import (
    CoachPlacementResponse,
    CreateNamedLeagueInviteRequest,
    FantasyCoachDirectoryItem,
    FantasyCoachDirectoryResponse,
    FantasyCoachProfileResponse,
    NamedLeagueInviteResponse,
    PendingInviteCountResponse,
    RespondNamedLeagueInviteResponse,
)
from leagues.validators import validate_configurable_league_state
from notifications.service import NotificationService
from observability.context import get_correlation_id
from observability.metrics import get_metrics


def invite_notification_dedup_key(invite_id: UUID) -> str:
    """Chiave della notifica «Nuovo invito»: una sola per invito, ritrovabile alla revoca."""
    return f"named_invite:{invite_id}"


def directory_invite_status(status: NamedInviteStatus | None) -> str | None:
    """Stato mostrato in directory.

    Un invito `accepted` non resta «Aggiunto»: chi è ancora in lega è marcato
    `inLeague`, chi è uscito può ricevere un nuovo invito.
    """
    if status is None or status == NamedInviteStatus.ACCEPTED:
        return None
    return status.value


# Inviti nominativi della lega che mostrano l'email del destinatario al suo admin: quello in
# corso (l'admin controlla di aver invitato la persona giusta e, se no, lo annulla) e quelli a
# cui il fantallenatore ha risposto, accettando o rifiutando. Revocati e scaduti no: senza
# risposta non c'è un legame con la lega, e un invito annullato per errore non deve lasciare
# in vista l'email di chi non c'entra.
EMAIL_INVITE_ANSWERED_STATUSES = (NamedInviteStatus.ACCEPTED, NamedInviteStatus.DECLINED)


def _coach_in_league(league_id: UUID):
    """EXISTS correlato a `User`: il fantallenatore è iscritto alla lega."""
    return (
        select(LeagueMembership.user_id)
        .where(
            LeagueMembership.league_id == league_id,
            LeagueMembership.user_id == User.id,
        )
        .correlate(User)
        .exists()
    )


def _coach_invited(league_id: UUID, now: datetime):
    """EXISTS correlato a `User`: invito nominativo della lega in corso o con risposta."""
    return (
        select(NamedLeagueInvite.id)
        .where(
            NamedLeagueInvite.league_id == league_id,
            NamedLeagueInvite.recipient_id == User.id,
            or_(
                NamedLeagueInvite.status.in_(EMAIL_INVITE_ANSWERED_STATUSES),
                and_(
                    NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                    NamedLeagueInvite.expires_at > now,
                ),
            ),
        )
        .correlate(User)
        .exists()
    )


def can_see_coach_email(
    league_access: LeagueAccess,
    *,
    coach_in_league: bool,
    coach_invited: bool,
) -> bool:
    """Chi vede l'email di un fantallenatore, in directory e nel profilo (decisione del 20/11).

    - L'operatore di piattaforma: sempre, anche quando nella lega è un
      partecipante qualunque o non ne fa parte.
    - L'admin della lega indicata nel percorso: solo per chi è già iscritto a
      quella lega (`coach_in_league`) o ha un suo invito nominativo in corso o
      con risposta (`coach_invited`, vedi `EMAIL_INVITE_ANSWERED_STATUSES`).
      Per tutti gli altri utenti della directory vede solo il nome.
    - Nessun altro: un partecipante normale non vede l'email altrui, e chi
      amministra un'altra lega non la vede passando da questa.

    Il controllo è qui, non solo sui permessi della rotta: la directory oggi
    richiede `league:admin`, ma se un giorno si aprisse ai membri l'email
    resterebbe comunque nascosta.
    """
    if league_access.operator_bypass or league_access.user.platform_role == PlatformRole.OPERATOR:
        return True
    if league_access.api_role != LeagueRole.LEAGUE_ADMIN:
        return False
    return coach_in_league or coach_invited


class NamedLeagueInviteService:
    def __init__(
        self,
        session: Session,
        rate_limiter: AuthRateLimiter | None = None,
    ) -> None:
        self._session = session
        self._rate_limiter = rate_limiter

    def directory(
        self,
        league_access: LeagueAccess,
        *,
        page: int,
        page_size: int,
        search: str | None,
        user_type: UserType | None,
        available: bool | None,
    ) -> FantasyCoachDirectoryResponse:
        self._check_rate_limit("coach_directory", league_access)
        now = datetime.now(UTC)
        self._expire_pending_for_league(league_access.league.id, now)

        def latest_invite(column):
            # Stesso ordinamento (con spareggio sull'id) per stato e id: i due
            # campi devono descrivere sempre lo stesso invito.
            return (
                select(column)
                .where(
                    NamedLeagueInvite.league_id == league_access.league.id,
                    NamedLeagueInvite.recipient_id == User.id,
                )
                .order_by(NamedLeagueInvite.created_at.desc(), NamedLeagueInvite.id.desc())
                .limit(1)
                .correlate(User)
                .scalar_subquery()
            )

        latest_status = latest_invite(NamedLeagueInvite.status)
        latest_id = latest_invite(NamedLeagueInvite.id)
        in_league = _coach_in_league(league_access.league.id)
        effective_available = or_(
            User.user_type == UserType.AI,
            UserProfile.available_for_invites.is_(True),
        )
        conditions = [User.deleted_at.is_(None)]
        if search:
            escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            if escaped:
                pattern = f"%{escaped}%"
                conditions.append(
                    or_(
                        UserProfile.display_name.ilike(pattern, escape="\\"),
                        UserProfile.nickname.ilike(pattern, escape="\\"),
                    )
                )
        if user_type is not None:
            conditions.append(User.user_type == user_type)
        if available is not None:
            conditions.append(effective_available if available else ~effective_available)

        base = (
            select(
                User,
                UserProfile,
                latest_status.label("invite_status"),
                latest_id.label("invite_id"),
                in_league.label("in_league"),
                _coach_invited(league_access.league.id, now).label("invited"),
            )
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(*conditions)
        )
        total = (
            self._session.scalar(select(func.count()).select_from(base.order_by(None).subquery()))
            or 0
        )
        rows = self._session.execute(
            base.order_by(func.coalesce(UserProfile.display_name, User.email).asc(), User.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        # Storico della sola pagina corrente, in una query: la card vieta
        # esplicitamente l'N+1 sulla preview.
        histories = load_histories(self._session, user_ids=[user.id for user, *_ in rows])
        items = [
            FantasyCoachDirectoryItem(
                userId=str(user.id),
                displayName=(
                    profile.display_name
                    if profile is not None and profile.display_name
                    else (user.email.split("@", 1)[0] or user.email)
                ),
                email=(
                    user.email
                    if can_see_coach_email(
                        league_access,
                        coach_in_league=bool(is_member),
                        coach_invited=bool(invited),
                    )
                    else None
                ),
                avatarUrl=profile.avatar_url if profile is not None else None,
                nickname=profile.nickname if profile is not None else None,
                userType=user.user_type.value,
                availableForInvites=(
                    user.user_type == UserType.AI
                    or (profile is not None and profile.available_for_invites)
                ),
                inLeague=bool(is_member),
                emailVerified=user.email_verified_at is not None,
                isSelf=user.id == league_access.user.id,
                namedInviteStatus=directory_invite_status(invite_status),
                # Serve alla UI per «Annulla invito»: segue lo stato mostrato,
                # quindi è nullo quando lo stato in directory è nullo.
                namedInviteId=(
                    str(invite_id) if directory_invite_status(invite_status) is not None else None
                ),
                memberSince=seniority_label(user.created_at, now=now),
                concludedLeagues=histories[user.id].concluded_leagues,
                bestPosition=histories[user.id].best_position,
                historySummary=summary_line(histories[user.id]),
            )
            for user, profile, invite_status, invite_id, is_member, invited in rows
        ]
        get_metrics().incr("coach_directory_viewed_total", labels={"result": "success"})
        return FantasyCoachDirectoryResponse(
            items=items,
            page=page,
            pageSize=page_size,
            total=total,
            totalPages=math.ceil(total / page_size) if total else 0,
        )

    def coach_profile(
        self,
        league_access: LeagueAccess,
        user_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> FantasyCoachProfileResponse:
        """Profilo storico limitato di un fantallenatore (EP13-P06).

        Reso accessibile a qualunque utente, incluso il chiamante stesso
        (candidati da invitare così come membri già in questa lega, es. dal
        click su un nome in Classifica — anche il proprio): l'endpoint è
        protetto da `Permission.LEAGUE_VIEW` sulla lega indicata (qualunque
        membro, non solo admin — prima era `LEAGUE_ADMIN`, impedendo a un
        membro normale di aprire il profilo di un altro fantallenatore della
        sua stessa lega). Lo storico restituisce solo fatti derivati da
        leghe concluse — mai budget, rose o nomi di lega; l'email la vedono
        solo l'operatore e l'admin di questa lega per chi ne fa parte o ne ha
        un invito nominativo (vedi `can_see_coach_email`, EP13-P06bis).

        Il chiamante NON viene escluso: la directory (`directory()`) lo
        elenca già con `isSelf=True`, e la Classifica può linkare anche la
        propria riga. Escluderlo qui rompeva il click sul proprio nome con
        "Fantallenatore non trovato" pur essendo un membro valido della lega
        (bug 8a).

        Né email verificata né `UserProfile` completo sono richiesti: la
        directory elenca anche utenti con email non verificata o senza
        profilo (es. un fantallenatore creato manualmente) — filtrare questa
        query più del necessario produceva lo stesso "Fantallenatore non
        trovato" per chiunque comparisse in quella lista senza soddisfare
        requisiti che la directory stessa non richiede. Nome visualizzato
        con lo stesso fallback sull'email di `directory()` quando il profilo
        manca o non ha un nome impostato.
        """
        self._check_rate_limit("coach_directory", league_access)
        now = datetime.now(UTC)

        latest_status = (
            select(NamedLeagueInvite.status)
            .where(
                NamedLeagueInvite.league_id == league_access.league.id,
                NamedLeagueInvite.recipient_id == User.id,
            )
            .order_by(NamedLeagueInvite.created_at.desc())
            .limit(1)
            .correlate(User)
            .scalar_subquery()
        )
        row = self._session.execute(
            select(
                User,
                UserProfile,
                latest_status.label("invite_status"),
                _coach_in_league(league_access.league.id).label("in_league"),
                _coach_invited(league_access.league.id, now).label("invited"),
            )
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(
                User.id == user_id,
                User.deleted_at.is_(None),
            )
        ).first()
        if row is None:
            self._fail("Fantallenatore non trovato.", "coach_not_found", "not_found")

        user, profile, invite_status, in_league, invited = row
        # Niente filtro su email verificata / nome visualizzato impostato:
        # la directory (`directory()`) elenca già utenti non verificati o
        # senza profilo completo (es. un fantallenatore MANUALE appena
        # creato), con lo stesso fallback sul nome qui sotto — escluderli
        # qui produceva "Fantallenatore non trovato" per chiunque comparisse
        # in quella lista senza soddisfare questi requisiti.
        display_name = (
            profile.display_name
            if profile is not None and profile.display_name
            else (user.email.split("@", 1)[0] or user.email)
        )
        history = load_history(self._session, user_id=user.id)
        page_items, total = placements_page(history.placements, page=page, page_size=page_size)

        get_metrics().incr("coach_profile_viewed_total", labels={"result": "success"})
        return FantasyCoachProfileResponse(
            userId=str(user.id),
            displayName=display_name,
            email=(
                user.email
                if can_see_coach_email(
                    league_access,
                    coach_in_league=bool(in_league),
                    coach_invited=bool(invited),
                )
                else None
            ),
            avatarUrl=profile.avatar_url if profile is not None else None,
            nickname=profile.nickname if profile is not None else None,
            userType=user.user_type.value,
            availableForInvites=(
                user.user_type == UserType.AI
                or (profile is not None and profile.available_for_invites)
            ),
            namedInviteStatus=invite_status.value if invite_status is not None else None,
            memberSince=seniority_label(user.created_at, now=now),
            concludedLeagues=history.concluded_leagues,
            bestPosition=history.best_position,
            historySummary=summary_line(history),
            placements=[
                CoachPlacementResponse(
                    seasonYear=item.season_year,
                    position=item.position,
                    participantCount=item.participant_count,
                    played=item.played,
                    points=item.points,
                    fantasyPoints=item.fantasy_points,
                )
                for item in page_items
            ],
            placementsPage=page,
            placementsPageSize=page_size,
            placementsTotal=total,
        )

    def create(
        self,
        league_access: LeagueAccess,
        payload: CreateNamedLeagueInviteRequest,
    ) -> NamedLeagueInviteResponse:
        self._check_rate_limit("named_invite_create", league_access)
        league = self._lock_league(league_access.league.id)
        validate_configurable_league_state(league.state, subject="gli inviti nominativi")
        recipient = self._session.scalar(
            select(User)
            .where(User.id == payload.recipient_user_id, User.deleted_at.is_(None))
            .options(selectinload(User.profile))
        )
        if recipient is None or recipient.email_verified_at is None:
            self._fail("Fantallenatore non trovato.", "recipient_not_found", "not_found")
        if recipient.id == league_access.user.id:
            self._fail("Non puoi invitare te stesso.", "cannot_invite_self", "self")
        if self._membership(league.id, recipient.id) is not None:
            self._fail("Il fantallenatore è già nella lega.", "already_member", "already_member")
        if not self._is_available_for_invites(recipient):
            self._fail(
                "Il fantallenatore non è disponibile agli inviti.",
                "recipient_unavailable",
                "unavailable",
            )

        now = datetime.now(UTC)
        self._expire_pending(league.id, recipient.id, now)
        pending = self._session.scalar(
            select(NamedLeagueInvite).where(
                NamedLeagueInvite.league_id == league.id,
                NamedLeagueInvite.recipient_id == recipient.id,
                NamedLeagueInvite.status == NamedInviteStatus.PENDING,
            )
        )
        if pending is not None:
            self._fail("Invito già inviato.", "named_invite_already_pending", "duplicate")

        self._require_capacity(league, include_pending=True)
        invite = NamedLeagueInvite(
            league_id=league.id,
            recipient_id=recipient.id,
            created_by_id=league_access.user.id,
            status=(
                NamedInviteStatus.ACCEPTED
                if recipient.user_type == UserType.AI
                else NamedInviteStatus.PENDING
            ),
            expires_at=now + timedelta(days=payload.expires_in_days),
            responded_at=now if recipient.user_type == UserType.AI else None,
        )
        self._session.add(invite)
        self._session.flush()
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.NAMED_INVITE_CREATED,
            invite,
        )
        if recipient.user_type == UserType.AI:
            ai_membership = LeagueMembership(
                league_id=league.id,
                user_id=recipient.id,
                role=LeagueMemberRole.MEMBER,
            )
            self._session.add(ai_membership)
            self._session.flush()
            # Ogni altro percorso di ingresso in lega (creazione owner,
            # accettazione invito aperto/nominativo umano) crea subito anche
            # la FantasyTeam — l'invito nominativo verso un fantallenatore IA
            # era l'unico a saltarlo, lasciando il membro senza squadra in
            # classifica e invisibile alla generazione formazioni IA.
            team, created = ensure_team_for_membership(
                self._session,
                ai_membership,
                name=recipient.display_name,
                actor_id=recipient.id,
            )
            if created:
                self._session.add(
                    LeagueAuditEvent(
                        league_id=league.id,
                        actor_id=recipient.id,
                        action=LeagueAuditAction.FANTASY_TEAM_CREATED,
                        correlation_id=get_correlation_id(),
                        details={
                            "fantasyTeamId": str(team.id),
                            "membershipId": str(ai_membership.id),
                        },
                    )
                )
            self._add_audit(
                league.id,
                recipient.id,
                LeagueAuditAction.NAMED_INVITE_ACCEPTED,
                invite,
            )
        else:
            # Notifica solo agli umani: un fantallenatore IA è già entrato e
            # non ha nulla da decidere (EP13-P07). `dedup_key` sull'id invito
            # rende l'operazione idempotente su retry e richieste concorrenti.
            NotificationService(self._session).create_notification(
                user_id=recipient.id,
                category=NotificationCategory.SISTEMA,
                template_key="sistema.invito_lega",
                template_version=1,
                params={
                    "league_name": league.name,
                    "inviter_name": league_access.user.display_name,
                },
                dedup_key=invite_notification_dedup_key(invite.id),
            )
        self._session.commit()
        get_metrics().incr(
            "named_invite_created_total",
            labels={"result": "auto_accepted" if recipient.user_type == UserType.AI else "success"},
        )
        return self._response(
            invite,
            league,
            recipient,
            auto_accepted=recipient.user_type == UserType.AI,
        )

    def pending_count(self, user: User) -> PendingInviteCountResponse:
        """Inviti realmente pendenti per il badge (EP13-P07).

        Distinto dal contatore della campanella, che conta le notifiche non
        lette: leggere la notifica non chiude l'invito. Gli scaduti vengono
        prima riconciliati, così il badge non conta ciò che non è più
        actionable.
        """
        now = datetime.now(UTC)
        result = self._session.execute(
            update(NamedLeagueInvite)
            .where(
                NamedLeagueInvite.recipient_id == user.id,
                NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                NamedLeagueInvite.expires_at <= now,
            )
            .values(status=NamedInviteStatus.EXPIRED)
        )
        if result.rowcount:
            self._session.commit()

        count = (
            self._session.scalar(
                select(func.count())
                .select_from(NamedLeagueInvite)
                .where(
                    NamedLeagueInvite.recipient_id == user.id,
                    NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                    NamedLeagueInvite.expires_at > now,
                )
            )
            or 0
        )
        return PendingInviteCountResponse(pendingInviteCount=count)

    def received(self, user: User) -> list[NamedLeagueInviteResponse]:
        now = datetime.now(UTC)
        result = self._session.execute(
            update(NamedLeagueInvite)
            .where(
                NamedLeagueInvite.recipient_id == user.id,
                NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                NamedLeagueInvite.expires_at <= now,
            )
            .values(status=NamedInviteStatus.EXPIRED)
        )
        if result.rowcount:
            self._session.commit()
        # Solo inviti ancora actionable: accettati/rifiutati/scaduti/revocati
        # non devono riapparire nella inbox dopo un refresh.
        invites = list(
            self._session.scalars(
                select(NamedLeagueInvite)
                .where(
                    NamedLeagueInvite.recipient_id == user.id,
                    NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                )
                .options(
                    selectinload(NamedLeagueInvite.league),
                    selectinload(NamedLeagueInvite.recipient).selectinload(User.profile),
                )
                .order_by(NamedLeagueInvite.created_at.desc())
            ).all()
        )
        return [self._response(row, row.league, row.recipient) for row in invites]

    def accept(self, user: User, invite_id: UUID) -> RespondNamedLeagueInviteResponse:
        return self._respond(user, invite_id, action="accept")

    def decline(self, user: User, invite_id: UUID) -> RespondNamedLeagueInviteResponse:
        return self._respond(user, invite_id, action="decline")

    def revoke(
        self,
        league_access: LeagueAccess,
        invite_id: UUID,
    ) -> NamedLeagueInviteResponse:
        league = self._lock_league(league_access.league.id)
        invite = self._load_invite(invite_id, for_update=True)
        if invite is None or invite.league_id != league.id:
            self._fail("Invito non trovato.", "named_invite_not_found", "not_found")
        if invite.status == NamedInviteStatus.REVOKED:
            # Idempotente: ripulisce anche la notifica di revoche fatte prima
            # che la revoca la togliesse.
            if self._withdraw_invite_notification(invite):
                self._session.commit()
            return self._response(invite, league, invite.recipient)
        if invite.status != NamedInviteStatus.PENDING:
            self._fail("L'invito non è più revocabile.", "named_invite_not_pending", "not_pending")
        now = datetime.now(UTC)
        invite.status = NamedInviteStatus.REVOKED
        invite.revoked_at = now
        self._add_audit(
            league.id,
            league_access.user.id,
            LeagueAuditAction.NAMED_INVITE_REVOKED,
            invite,
        )
        self._withdraw_invite_notification(invite)
        self._session.commit()
        get_metrics().incr("named_invite_revoked_total", labels={"result": "success"})
        return self._response(invite, league, invite.recipient)

    def _withdraw_invite_notification(self, invite: NamedLeagueInvite) -> bool:
        """Toglie al destinatario la notifica «Nuovo invito» di un invito revocato.

        Il suo link porta a «Inviti ricevuti», dove un invito revocato non
        compare più: lasciarla in campanella (letta o no) manderebbe a una
        pagina vuota. Resta nella transazione della revoca.
        """
        return (
            NotificationService(self._session).delete_notification_by_dedup_key(
                user_id=invite.recipient_id,
                dedup_key=invite_notification_dedup_key(invite.id),
            )
            > 0
        )

    def _respond(
        self,
        user: User,
        invite_id: UUID,
        *,
        action: Literal["accept", "decline"],
    ) -> RespondNamedLeagueInviteResponse:
        invite = self._load_invite(invite_id, for_update=False)
        if invite is None or invite.recipient_id != user.id:
            self._fail("Invito non trovato.", "named_invite_not_found", "not_found")
        desired = NamedInviteStatus.ACCEPTED if action == "accept" else NamedInviteStatus.DECLINED
        if invite.status == desired:
            return RespondNamedLeagueInviteResponse(
                **self._response(invite, invite.league, invite.recipient).model_dump(),
                alreadyProcessed=True,
            )
        if invite.status != NamedInviteStatus.PENDING:
            self._fail(
                "L'invito è già stato elaborato.",
                "named_invite_already_processed",
                "already_processed",
            )

        league = self._lock_league(invite.league_id)
        invite = self._load_invite(invite_id, for_update=True)
        if invite is None or invite.recipient_id != user.id:
            self._fail("Invito non trovato.", "named_invite_not_found", "not_found")
        if invite.status == desired:
            return RespondNamedLeagueInviteResponse(
                **self._response(invite, league, invite.recipient).model_dump(),
                alreadyProcessed=True,
            )
        if invite.status != NamedInviteStatus.PENDING:
            self._fail(
                "L'invito è già stato elaborato.",
                "named_invite_already_processed",
                "already_processed",
            )
        now = datetime.now(UTC)
        if invite.expires_at <= now:
            invite.status = NamedInviteStatus.EXPIRED
            self._session.commit()
            self._fail("L'invito è scaduto.", "named_invite_expired", "expired")
        validate_configurable_league_state(league.state, subject="gli ingressi nella lega")

        if action == "accept":
            recipient = invite.recipient
            if recipient.deleted_at is not None or recipient.email_verified_at is None:
                self._fail("Fantallenatore non trovato.", "recipient_not_found", "not_found")
            if not self._is_available_for_invites(recipient):
                self._fail(
                    "Il fantallenatore non è disponibile agli inviti.",
                    "recipient_unavailable",
                    "unavailable",
                )
            existing = self._membership(league.id, user.id)
            if existing is None:
                self._require_capacity(league, include_pending=False)
                membership = LeagueMembership(
                    league_id=league.id,
                    user_id=user.id,
                    role=LeagueMemberRole.MEMBER,
                )
                self._session.add(membership)
                self._session.flush()
                team, created = ensure_team_for_membership(
                    self._session,
                    membership,
                    name=user.display_name,
                    actor_id=user.id,
                )
                if created:
                    self._session.add(
                        LeagueAuditEvent(
                            league_id=league.id,
                            actor_id=user.id,
                            action=LeagueAuditAction.FANTASY_TEAM_CREATED,
                            correlation_id=get_correlation_id(),
                            details={
                                "fantasyTeamId": str(team.id),
                                "membershipId": str(membership.id),
                            },
                        )
                    )
            audit_action = LeagueAuditAction.NAMED_INVITE_ACCEPTED
        else:
            audit_action = LeagueAuditAction.NAMED_INVITE_DECLINED
        invite.status = desired
        invite.responded_at = now
        self._add_audit(league.id, user.id, audit_action, invite)
        coach_name = (
            user.profile.display_name
            if user.profile is not None and user.profile.display_name
            else "Il fantallenatore invitato"
        )
        NotificationService(self._session).create_notification(
            user_id=invite.created_by_id,
            category=NotificationCategory.SISTEMA,
            template_key="sistema.invito_lega_esito",
            template_version=1,
            params={
                "league_id": str(league.id),
                "league_name": league.name,
                "coach_name": coach_name,
                "outcome": "accepted" if action == "accept" else "declined",
            },
            dedup_key=f"named_invite_response:{invite.id}",
        )
        self._session.commit()
        get_metrics().incr(
            f"named_invite_{'accepted' if action == 'accept' else 'declined'}_total",
            labels={"result": "success"},
        )
        return RespondNamedLeagueInviteResponse(
            **self._response(invite, league, invite.recipient).model_dump(),
            alreadyProcessed=False,
        )

    def _require_capacity(self, league: League, *, include_pending: bool) -> None:
        if league.rules is None:
            self._fail(
                "Regolamento lega non configurato.",
                "league_rules_not_found",
                "rules_missing",
            )
        members = (
            self._session.scalar(
                select(func.count(LeagueMembership.id)).where(
                    LeagueMembership.league_id == league.id
                )
            )
            or 0
        )
        pending = 0
        if include_pending:
            pending = (
                self._session.scalar(
                    select(func.count(NamedLeagueInvite.id)).where(
                        NamedLeagueInvite.league_id == league.id,
                        NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                        NamedLeagueInvite.expires_at > datetime.now(UTC),
                    )
                )
                or 0
            )
        if members + pending >= league.rules.participant_count:
            self._fail("La lega non ha posti disponibili.", "league_full", "full")

    def _load_invite(
        self,
        invite_id: UUID,
        *,
        for_update: bool,
    ) -> NamedLeagueInvite | None:
        statement = (
            select(NamedLeagueInvite)
            .where(NamedLeagueInvite.id == invite_id)
            .options(
                selectinload(NamedLeagueInvite.league).selectinload(League.rules),
                selectinload(NamedLeagueInvite.recipient).selectinload(User.profile),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def _lock_league(self, league_id: UUID) -> League:
        league = self._session.scalar(
            select(League)
            .where(League.id == league_id)
            .options(selectinload(League.rules))
            .with_for_update()
        )
        if league is None:
            self._fail("Lega non trovata.", "league_not_found", "not_found")
        return league

    def _membership(self, league_id: UUID, user_id: UUID) -> LeagueMembership | None:
        return self._session.scalar(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league_id,
                LeagueMembership.user_id == user_id,
            )
        )

    def _expire_pending(self, league_id: UUID, recipient_id: UUID, now: datetime) -> None:
        rows = self._session.scalars(
            select(NamedLeagueInvite).where(
                NamedLeagueInvite.league_id == league_id,
                NamedLeagueInvite.recipient_id == recipient_id,
                NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                NamedLeagueInvite.expires_at <= now,
            )
        ).all()
        for row in rows:
            row.status = NamedInviteStatus.EXPIRED
        if rows:
            self._session.flush()

    def _expire_pending_for_league(self, league_id: UUID, now: datetime) -> None:
        result = self._session.execute(
            update(NamedLeagueInvite)
            .where(
                NamedLeagueInvite.league_id == league_id,
                NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                NamedLeagueInvite.expires_at <= now,
            )
            .values(status=NamedInviteStatus.EXPIRED)
        )
        if result.rowcount:
            self._session.flush()

    @staticmethod
    def _is_available_for_invites(user: User) -> bool:
        if user.user_type == UserType.AI:
            return True
        return user.profile is not None and user.profile.available_for_invites

    def _check_rate_limit(self, endpoint: str, access: LeagueAccess) -> None:
        if self._rate_limiter is not None:
            self._rate_limiter.check(
                endpoint=endpoint,
                key=f"{access.user.id}:{access.league.id}",
                limit=120 if endpoint == "coach_directory" else 30,
                window_seconds=60,
            )

    def _add_audit(
        self,
        league_id: UUID,
        actor_id: UUID,
        action: LeagueAuditAction,
        invite: NamedLeagueInvite,
    ) -> None:
        self._session.add(
            LeagueAuditEvent(
                league_id=league_id,
                actor_id=actor_id,
                action=action,
                correlation_id=get_correlation_id(),
                details={
                    "namedInviteId": str(invite.id),
                    "recipientUserId": str(invite.recipient_id),
                },
            )
        )

    @staticmethod
    def _response(
        invite: NamedLeagueInvite,
        league: League,
        recipient: User,
        *,
        auto_accepted: bool = False,
    ) -> NamedLeagueInviteResponse:
        display_name = (
            recipient.profile.display_name
            if recipient.profile is not None and recipient.profile.display_name
            else "Fantallenatore"
        )
        return NamedLeagueInviteResponse(
            id=str(invite.id),
            leagueId=str(invite.league_id),
            leagueName=league.name,
            recipientUserId=str(recipient.id),
            recipientDisplayName=display_name,
            recipientUserType=recipient.user_type.value,
            status=invite.status.value,
            expiresAt=invite.expires_at,
            respondedAt=invite.responded_at,
            createdAt=invite.created_at,
            autoAccepted=auto_accepted,
        )

    @staticmethod
    def _fail(message: str, code: str, result: str) -> NoReturn:
        get_metrics().incr("named_invite_operation_total", labels={"result": result})
        raise ValidationAuthError(message, code=code)
