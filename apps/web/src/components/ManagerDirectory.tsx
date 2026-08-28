import { Button, Input, Select, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import type { FantasyCoachProfile } from "@fantappero/contracts";
import { formatFantasyPoints } from "@fantappero/contracts";
import {
  createNamedLeagueInvite,
  fetchCoachProfile,
  fetchManagerDirectory,
  type FantasyCoachDirectoryItem,
  type PaginatedFantasyCoachDirectory,
  type UserType,
} from "../api/managerInvites";
import { ApiError } from "../api/client";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

const DEMO_MANAGERS: FantasyCoachDirectoryItem[] = [
  {
    userId: "manager-lucia",
    displayName: "Lucia Bianchi",
    avatarUrl: null,
    userType: "human",
    availableForInvites: true,
    namedInviteStatus: null,
    memberSince: "03/2025",
    concludedLeagues: 3,
    bestPosition: 1,
    historySummary: "3 leghe concluse · miglior 1º",
  },
  {
    userId: "manager-paolo",
    displayName: "Paolo Verdi",
    avatarUrl: null,
    userType: "human",
    availableForInvites: false,
    namedInviteStatus: null,
    memberSince: "11/2025",
    concludedLeagues: 0,
    bestPosition: null,
    historySummary: "Nessuna lega conclusa",
  },
  {
    userId: "manager-ai",
    displayName: "Allenatore IA 01",
    avatarUrl: null,
    userType: "ai",
    availableForInvites: true,
    namedInviteStatus: "pending",
    memberSince: "01/2026",
    concludedLeagues: 1,
    bestPosition: 4,
    historySummary: "1 lega conclusa · miglior 4º",
  },
];

type ManagerDirectoryProps = {
  leagueId?: string | null;
  isDemoMode: boolean;
  search?: string;
  title?: string;
  compact?: boolean;
};

function inviteErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return "Non hai i permessi per invitare in questa lega.";
    if (error.code === "recipient_unavailable") return "Questo fantallenatore non accetta inviti.";
    if (error.code === "named_invite_already_pending") return "Hai già invitato questo fantallenatore.";
    if (error.code === "already_member") return "Il fantallenatore è già nella lega.";
    if (error.code === "league_full") return "La lega ha raggiunto la capienza massima.";
  }
  return getApiErrorMessage(error, "Impossibile inviare l'invito nominativo.");
}

function userTypeLabel(userType: UserType): string {
  return userType === "ai" ? "IA" : "Manuale";
}

/** Profilo storico limitato: solo fatti da leghe concluse (EP13-P06). */
export function CoachProfilePanel({
  profile,
  onClose,
}: {
  profile: FantasyCoachProfile;
  onClose: () => void;
}) {
  return (
    <section
      className="fa-coach-profile"
      aria-labelledby="coach-profile-title"
      data-testid="coach-profile"
    >
      <h3 id="coach-profile-title">{profile.displayName}</h3>
      <p>
        {userTypeLabel(profile.userType)} ·{" "}
        {profile.availableForInvites ? "Disponibile" : "Non disponibile"}
        {profile.memberSince ? ` · iscritto da ${profile.memberSince}` : ""}
      </p>
      <p data-testid="coach-profile-summary">{profile.historySummary}</p>

      {profile.placements.length === 0 ? (
        <p data-testid="coach-profile-empty">
          Nessuna lega conclusa: questo fantallenatore non ha ancora uno storico.
        </p>
      ) : (
        <table data-testid="coach-profile-placements">
          <caption className="fa-sr-only">Piazzamenti in leghe concluse</caption>
          <thead>
            <tr>
              <th scope="col">Stagione</th>
              <th scope="col">Posizione</th>
              <th scope="col">Partite</th>
              <th scope="col">Punti</th>
              <th scope="col">Fantapunti</th>
            </tr>
          </thead>
          <tbody>
            {profile.placements.map((item) => (
              <tr key={`${item.seasonYear}-${item.position}-${item.participantCount}`}>
                <td>{item.seasonYear}</td>
                <td>
                  {item.position}º su {item.participantCount}
                </td>
                <td>{item.played}</td>
                <td>{item.points}</td>
                <td>{formatFantasyPoints(item.fantasyPoints)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="fa-manager-directory__hint">
        Lo storico mostra solo leghe concluse. I nomi delle leghe non sono visibili.
      </p>
      <Button type="button" variant="secondary" onClick={onClose} data-testid="coach-profile-close">
        Chiudi
      </Button>
    </section>
  );
}

export function ManagerDirectory({
  leagueId = null,
  isDemoMode,
  search = "",
  title = "Directory fantallenatori",
  compact = false,
}: ManagerDirectoryProps) {
  const demoState = new URLSearchParams(search).get("directory");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [userType, setUserType] = useState<"" | UserType>("");
  const [availableFilter, setAvailableFilter] = useState<"" | "true" | "false">("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<PaginatedFantasyCoachDirectory | null>(() =>
    isDemoMode && demoState !== "error" && demoState !== "forbidden"
      ? {
          items: demoState === "empty" ? [] : DEMO_MANAGERS,
          page: 1,
          pageSize: 12,
          total: demoState === "empty" ? 0 : DEMO_MANAGERS.length,
          totalPages: 1,
        }
      : null,
  );
  const [loading, setLoading] = useState(!isDemoMode);
  const [error, setError] = useState<string | null>(() => {
    if (!isDemoMode) return null;
    if (demoState === "error") return "Impossibile caricare la directory (demo).";
    if (demoState === "forbidden") return "Non hai i permessi per consultare la directory.";
    return null;
  });
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [profile, setProfile] = useState<FantasyCoachProfile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [capacityReached, setCapacityReached] = useState(isDemoMode && demoState === "capacity");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setDebouncedQuery(query.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  const load = useCallback(async () => {
    setSuccess(null);
    if (isDemoMode) {
      setLoading(demoState === "loading");
      setCapacityReached(demoState === "capacity");
      if (demoState === "error") {
        setError("Impossibile caricare la directory (demo).");
        setResult(null);
        return;
      }
      if (demoState === "forbidden") {
        setError("Non hai i permessi per consultare la directory.");
        setResult(null);
        return;
      }
      const filtered =
        demoState === "empty"
          ? []
          : DEMO_MANAGERS.filter(
              (manager) =>
                (!debouncedQuery ||
                  manager.displayName.toLowerCase().includes(debouncedQuery.toLowerCase())) &&
                (!userType || manager.userType === userType) &&
                (availableFilter === "" ||
                  manager.availableForInvites === (availableFilter === "true")),
            );
      setResult({ items: filtered, page: 1, pageSize: 12, total: filtered.length, totalPages: 1 });
      setError(null);
      return;
    }

    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      setLoading(false);
      return;
    }
    if (!leagueId) {
      setError("Seleziona una lega amministrata per consultare la directory.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setResult(
        await fetchManagerDirectory(session.accessToken, leagueId, {
          query: debouncedQuery || undefined,
          userType: userType || undefined,
          available:
            availableFilter === "" ? undefined : availableFilter === "true",
          page,
        }),
      );
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 403) {
        setError("Non hai i permessi per consultare la directory.");
      } else {
        setError(getApiErrorMessage(loadError, "Impossibile caricare la directory."));
      }
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [availableFilter, debouncedQuery, demoState, isDemoMode, leagueId, page, userType]);

  useEffect(() => {
    void load();
  }, [load]);

  async function openProfile(manager: FantasyCoachDirectoryItem) {
    setProfileError(null);
    if (isDemoMode || !leagueId) {
      // In demo il profilo si costruisce dalla riga: nessuna chiamata API.
      setProfile({
        userId: manager.userId,
        displayName: manager.displayName,
        avatarUrl: manager.avatarUrl,
        userType: manager.userType,
        availableForInvites: manager.availableForInvites,
        namedInviteStatus: manager.namedInviteStatus,
        memberSince: manager.memberSince,
        concludedLeagues: manager.concludedLeagues,
        bestPosition: manager.bestPosition,
        historySummary: manager.historySummary,
        placements: [],
        placementsPage: 1,
        placementsPageSize: 20,
        placementsTotal: 0,
      });
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setProfileError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    try {
      setProfile(await fetchCoachProfile(stored.accessToken, leagueId, manager.userId));
    } catch (error) {
      setProfile(null);
      setProfileError(getApiErrorMessage(error, "Impossibile caricare il profilo."));
    }
  }

  async function onInvite(manager: FantasyCoachDirectoryItem) {
    setError(null);
    setSuccess(null);
    if (!manager.availableForInvites) {
      setError("Questo fantallenatore non accetta inviti.");
      return;
    }
    if (manager.namedInviteStatus === "pending") {
      setError("Hai già invitato questo fantallenatore.");
      return;
    }
    if (capacityReached) {
      setError("La lega ha raggiunto la capienza massima.");
      return;
    }
    if (!leagueId) {
      setError("Seleziona una lega prima di inviare un invito.");
      return;
    }
    if (isDemoMode) {
      setSuccess(`Invito inviato a ${manager.displayName} (demo).`);
      setResult((current) =>
        current
          ? {
              ...current,
              items: current.items.map((row) =>
                row.userId === manager.userId ? { ...row, namedInviteStatus: "pending" } : row,
              ),
            }
          : current,
      );
      return;
    }
    const session = loadStoredSession();
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setWorkingId(manager.userId);
    try {
      const created = await createNamedLeagueInvite(session.accessToken, leagueId, manager.userId);
      setCapacityReached(false);
      setSuccess(
        created.autoAccepted
          ? `${manager.displayName} è entrato automaticamente nella lega.`
          : `Invito inviato a ${manager.displayName}.`,
      );
      setResult((current) =>
        current
          ? {
              ...current,
              items: current.items.map((row) =>
                row.userId === manager.userId
                  ? { ...row, namedInviteStatus: created.status }
                  : row,
              ),
            }
          : current,
      );
    } catch (inviteError) {
      if (inviteError instanceof ApiError && inviteError.code === "league_full") {
        setCapacityReached(true);
      }
      setError(inviteErrorMessage(inviteError));
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <section
      className={compact ? "fa-manager-directory fa-manager-directory--compact" : "fa-manager-directory"}
      aria-labelledby="manager-directory-title"
    >
      <h2 id="manager-directory-title">{title}</h2>
      <p>Consulta i fantallenatori e invitali nominativamente nella lega.</p>

      <div className="fa-manager-directory__filters">
        <Input
          label="Cerca per nome"
          name="manager-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Select
          label="Tipologia"
          name="manager-type"
          value={userType}
          onChange={(event) => {
            setPage(1);
            setUserType(event.target.value as "" | UserType);
          }}
          options={[
            { value: "", label: "Tutte" },
            { value: "human", label: "Manuale" },
            { value: "ai", label: "IA" },
          ]}
        />
        <Select
          label="Disponibilità"
          name="manager-available"
          value={availableFilter}
          onChange={(event) => {
            setPage(1);
            setAvailableFilter(event.target.value as "" | "true" | "false");
          }}
          options={[
            { value: "", label: "Tutte" },
            { value: "true", label: "Disponibile" },
            { value: "false", label: "Non disponibile" },
          ]}
        />
      </div>

      {success ? (
        <UiStatePanel
          state="success"
          title="Invito inviato"
          message={success}
          testId="manager-directory-success"
        />
      ) : null}
      {capacityReached ? (
        <UiStatePanel
          state="error"
          title="Lega al completo"
          message="Non puoi inviare altri inviti: è stata raggiunta la capienza massima."
          testId="manager-directory-capacity"
        />
      ) : null}
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento directory"
          message="Ricerca fantallenatori in corso…"
          testId="manager-directory-loading"
        />
      ) : null}
      {!loading && error ? (
        <div>
          <UiStatePanel
            state={error.includes("permessi") ? "forbidden" : "error"}
            title="Directory non disponibile"
            message={error}
            testId="manager-directory-error"
          />
          <Button type="button" variant="ghost" onClick={() => void load()}>
            Riprova
          </Button>
        </div>
      ) : null}
      {!loading && !error && result?.items.length === 0 ? (
        <UiStatePanel
          state="empty"
          title="Nessun fantallenatore trovato"
          message="Modifica la ricerca o riprova più tardi."
          testId="manager-directory-empty"
        />
      ) : null}
      {profileError ? (
        <p role="alert" data-testid="coach-profile-error">
          {profileError}
        </p>
      ) : null}
      {profile ? (
        <CoachProfilePanel profile={profile} onClose={() => setProfile(null)} />
      ) : null}
      {!loading && !error && result && result.items.length > 0 ? (
        <>
          <ul className="fa-manager-directory__list" data-testid="manager-directory-list">
            {result.items.map((manager) => {
              const unavailable = !manager.availableForInvites;
              const alreadyInvited = manager.namedInviteStatus === "pending";
              const accepted = manager.namedInviteStatus === "accepted";
              return (
                <li key={manager.userId} className="fa-manager-directory__item">
                  <span className="fa-manager-directory__avatar" aria-hidden>
                    {manager.displayName.charAt(0)}
                  </span>
                  <button
                    type="button"
                    className="fa-manager-directory__identity fa-manager-directory__open"
                    onClick={() => void openProfile(manager)}
                    aria-label={`Apri il profilo di ${manager.displayName}`}
                    data-testid={`manager-open-${manager.userId}`}
                  >
                    <strong>{manager.displayName}</strong>
                    <small>
                      {userTypeLabel(manager.userType)} ·{" "}
                      {unavailable ? "Non disponibile" : "Disponibile"}
                      {manager.memberSince ? ` · dal ${manager.memberSince}` : ""}
                    </small>
                    <small data-testid={`manager-history-${manager.userId}`}>
                      {manager.historySummary}
                    </small>
                  </button>
                  {leagueId ? (
                    <Button
                      type="button"
                      size="sm"
                      variant={unavailable || alreadyInvited || accepted ? "secondary" : "primary"}
                      disabled={unavailable || alreadyInvited || accepted || capacityReached}
                      loading={workingId === manager.userId}
                      onClick={() => void onInvite(manager)}
                      data-testid={`manager-invite-${manager.userId}`}
                    >
                      {unavailable
                        ? "Indisponibile"
                        : accepted
                          ? "Aggiunto"
                          : alreadyInvited
                            ? "Già invitato"
                            : "Invita"}
                    </Button>
                  ) : (
                    <span className="fa-manager-directory__status">
                      {unavailable ? "Non disponibile" : "Disponibile"}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
          {result.totalPages > 1 ? (
            <div className="fa-manager-directory__pagination">
              <Button
                type="button"
                variant="ghost"
                disabled={page <= 1}
                onClick={() => setPage((value) => value - 1)}
              >
                Precedente
              </Button>
              <span>
                Pagina {result.page} di {result.totalPages}
              </span>
              <Button
                type="button"
                variant="ghost"
                disabled={page >= result.totalPages}
                onClick={() => setPage((value) => value + 1)}
              >
                Successiva
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
