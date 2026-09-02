import { Badge, Button, Input, Select, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import type { CoachPlacement, FantasyCoachProfile } from "@fantappero/contracts";
import { formatFantasyPoints } from "@fantappero/contracts";
import {
  createNamedLeagueInvite,
  fetchManagerDirectory,
  type FantasyCoachDirectoryItem,
  type PaginatedFantasyCoachDirectory,
  type UserType,
} from "../api/managerInvites";
import { ApiError } from "../api/client";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { Link } from "../router/simpleRouter";
import { resolveAvatarUrl } from "../utils/avatar";

/** Foto fittizie (pravatar.cc) solo per popolare la demo — nessun dato reale. */
function demoAvatar(seed: string): string {
  return `https://i.pravatar.cc/150?u=${seed}`;
}

export const DEMO_MANAGERS: FantasyCoachDirectoryItem[] = [
  {
    userId: "manager-lucia",
    displayName: "Lucia Bianchi",
    avatarUrl: demoAvatar("manager-lucia"),
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
    avatarUrl: demoAvatar("manager-ai"),
    userType: "ai",
    availableForInvites: true,
    namedInviteStatus: "pending",
    memberSince: "01/2026",
    concludedLeagues: 1,
    bestPosition: 4,
    historySummary: "1 lega conclusa · miglior 4º",
  },
  {
    userId: "manager-ai-02",
    displayName: "Allenatore IA 02",
    avatarUrl: demoAvatar("manager-ai-02"),
    userType: "ai",
    availableForInvites: true,
    namedInviteStatus: null,
    memberSince: "02/2026",
    concludedLeagues: 2,
    bestPosition: 2,
    historySummary: "2 leghe concluse · miglior 2º",
  },
  {
    userId: "manager-ai-03",
    displayName: "Allenatore IA 03",
    avatarUrl: demoAvatar("manager-ai-03"),
    userType: "ai",
    availableForInvites: false,
    namedInviteStatus: null,
    memberSince: "02/2026",
    concludedLeagues: 0,
    bestPosition: null,
    historySummary: "Nessuna lega conclusa",
  },
  {
    userId: "manager-ai-04",
    displayName: "Allenatore IA 04",
    avatarUrl: null,
    userType: "ai",
    availableForInvites: true,
    namedInviteStatus: null,
    memberSince: "08/2026",
    concludedLeagues: 0,
    bestPosition: null,
    historySummary: "Nessuna lega conclusa",
  },
  {
    userId: "manager-ai-05",
    displayName: "Allenatore IA 05",
    avatarUrl: demoAvatar("manager-ai-05"),
    userType: "ai",
    availableForInvites: true,
    namedInviteStatus: null,
    memberSince: "08/2026",
    concludedLeagues: 0,
    bestPosition: null,
    historySummary: "Nessuna lega conclusa",
  },
  {
    userId: "manager-ai-06",
    displayName: "Allenatore IA 06",
    avatarUrl: demoAvatar("manager-ai-06"),
    userType: "ai",
    availableForInvites: true,
    namedInviteStatus: "pending",
    memberSince: "08/2026",
    concludedLeagues: 0,
    bestPosition: null,
    historySummary: "Nessuna lega conclusa",
  },
  {
    userId: "manager-ai-07",
    displayName: "Allenatore IA 07",
    avatarUrl: demoAvatar("manager-ai-07"),
    userType: "ai",
    availableForInvites: true,
    namedInviteStatus: null,
    memberSince: "01/2026",
    concludedLeagues: 4,
    bestPosition: 1,
    historySummary: "4 leghe concluse · miglior 1º",
  },
  {
    userId: "manager-ai-08",
    displayName: "Allenatore IA 08",
    avatarUrl: demoAvatar("manager-ai-08"),
    userType: "ai",
    availableForInvites: true,
    namedInviteStatus: null,
    memberSince: "08/2026",
    concludedLeagues: 0,
    bestPosition: null,
    historySummary: "Nessuna lega conclusa",
  },
  {
    userId: "manager-ai-09",
    displayName: "Allenatore IA 09",
    avatarUrl: demoAvatar("manager-ai-09"),
    userType: "ai",
    availableForInvites: false,
    namedInviteStatus: "accepted",
    memberSince: "07/2026",
    concludedLeagues: 1,
    bestPosition: 3,
    historySummary: "1 lega conclusa · miglior 3º",
  },
];

/** Piazzamenti fittizi per userId, usati solo dalla vista profilo in modalità demo. */
export const DEMO_PLACEMENTS: Record<string, CoachPlacement[]> = {
  "manager-lucia": [
    { seasonYear: 2026, position: 1, participantCount: 8, played: 14, points: 30, fantasyPoints: 812.5 },
    { seasonYear: 2025, position: 3, participantCount: 8, played: 14, points: 24, fantasyPoints: 745 },
    { seasonYear: 2024, position: 5, participantCount: 6, played: 10, points: 15, fantasyPoints: 610 },
  ],
  "manager-ai": [
    { seasonYear: 2026, position: 4, participantCount: 8, played: 14, points: 18, fantasyPoints: 690 },
  ],
  "manager-ai-02": [
    { seasonYear: 2026, position: 2, participantCount: 6, played: 10, points: 21, fantasyPoints: 720 },
    { seasonYear: 2025, position: 6, participantCount: 8, played: 14, points: 12, fantasyPoints: 580 },
  ],
  "manager-ai-07": [
    { seasonYear: 2026, position: 1, participantCount: 10, played: 18, points: 34, fantasyPoints: 905 },
    { seasonYear: 2025, position: 2, participantCount: 10, played: 18, points: 30, fantasyPoints: 870 },
    { seasonYear: 2024, position: 5, participantCount: 8, played: 14, points: 16, fantasyPoints: 650 },
    { seasonYear: 2023, position: 3, participantCount: 6, played: 10, points: 19, fantasyPoints: 605 },
  ],
  "manager-ai-09": [
    { seasonYear: 2026, position: 3, participantCount: 8, played: 14, points: 19, fantasyPoints: 700 },
  ],
};

function CoachAvatar({
  name,
  avatarUrl,
  className,
}: {
  name: string;
  avatarUrl: string | null;
  className: string;
}) {
  const src = resolveAvatarUrl(avatarUrl);
  if (src) {
    return <img src={src} alt="" className={className} />;
  }
  return (
    <span className={className} aria-hidden>
      {name.charAt(0)}
    </span>
  );
}

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
  closeLabel = "Chiudi",
}: {
  profile: FantasyCoachProfile;
  onClose: () => void;
  closeLabel?: string;
}) {
  return (
    <section
      className="fa-coach-profile"
      aria-labelledby="coach-profile-title"
      data-testid="coach-profile"
    >
      <header className="fa-coach-profile__header">
        <CoachAvatar
          name={profile.displayName}
          avatarUrl={profile.avatarUrl}
          className="fa-coach-profile__avatar"
        />
        <div>
          <h3 id="coach-profile-title" className="fa-coach-profile__title">
            {profile.displayName}
          </h3>
          <div className="fa-coach-profile__meta">
            <Badge variant={profile.userType === "ai" ? "accent" : "neutral"}>
              {userTypeLabel(profile.userType)}
            </Badge>
            <Badge variant={profile.availableForInvites ? "success" : "neutral"}>
              {profile.availableForInvites ? "Disponibile" : "Non disponibile"}
            </Badge>
            {profile.memberSince ? <span>iscritto da {profile.memberSince}</span> : null}
          </div>
        </div>
      </header>

      <p className="fa-coach-profile__summary" data-testid="coach-profile-summary">
        {profile.historySummary}
      </p>

      {profile.placements.length === 0 ? (
        <p className="fa-coach-profile__empty" data-testid="coach-profile-empty">
          Nessuna lega conclusa: questo fantallenatore non ha ancora uno storico.
        </p>
      ) : (
        <div className="fa-table-wrap">
          <table className="fa-table" data-testid="coach-profile-placements">
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
        </div>
      )}

      <p className="fa-coach-profile__hint">
        Lo storico mostra solo leghe concluse. I nomi delle leghe non sono visibili.
      </p>
      <Button type="button" variant="secondary" onClick={onClose} data-testid="coach-profile-close">
        {closeLabel}
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

  function profileHref(manager: FantasyCoachDirectoryItem): string {
    const params = new URLSearchParams(search);
    if (leagueId) params.set("league", leagueId);
    const qs = params.toString();
    return `/fantallenatori/${manager.userId}${qs ? `?${qs}` : ""}`;
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
      {!loading && !error && result && result.items.length > 0 ? (
        <>
          <ul className="fa-manager-directory__list" data-testid="manager-directory-list">
            {result.items.map((manager) => {
              const unavailable = !manager.availableForInvites;
              const alreadyInvited = manager.namedInviteStatus === "pending";
              const accepted = manager.namedInviteStatus === "accepted";
              return (
                <li key={manager.userId} className="fa-manager-directory__item">
                  <CoachAvatar
                    name={manager.displayName}
                    avatarUrl={manager.avatarUrl}
                    className="fa-manager-directory__avatar"
                  />
                  <Link
                    to={profileHref(manager)}
                    className="fa-manager-directory__identity"
                    aria-label={`Apri il profilo di ${manager.displayName}`}
                    data-testid={`manager-open-${manager.userId}`}
                  >
                    <span className="fa-manager-directory__name">{manager.displayName}</span>
                    <span className="fa-manager-directory__badges">
                      <Badge variant={manager.userType === "ai" ? "accent" : "neutral"}>
                        {userTypeLabel(manager.userType)}
                      </Badge>
                      <Badge variant={unavailable ? "neutral" : "success"}>
                        {unavailable ? "Non disponibile" : "Disponibile"}
                      </Badge>
                      {manager.memberSince ? (
                        <span className="fa-manager-directory__meta">dal {manager.memberSince}</span>
                      ) : null}
                    </span>
                    <span
                      className="fa-manager-directory__history"
                      data-testid={`manager-history-${manager.userId}`}
                    >
                      {manager.historySummary}
                    </span>
                  </Link>
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
