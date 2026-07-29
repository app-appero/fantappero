import { useEffect, useState, type CSSProperties, type FormEvent, type ReactNode } from "react";

import {
  MIN_LEAGUE_COMPETITIONS,
  type CompetitionResponse,
  type LeagueFormState,
  type LeagueResponse,
  type SupportedLanguage,
  ui,
} from "@fantappero/contracts";
import { colors, spacing, typography } from "@fantappero/ui";

import { AuthApiError } from "../api/auth";
import { mapApiErrorMessage } from "../api/errors";
import type { LeagueClient } from "../api/leagues";

const initialFormState: LeagueFormState = { status: "idle" };

function fieldStyle(): CSSProperties {
  return {
    width: "100%",
    padding: spacing.sm,
    borderRadius: 8,
    border: `1px solid ${colors.muted}`,
    background: colors.background,
    color: colors.foreground,
    fontFamily: typography.fontFamily,
    fontSize: typography.fontSize.md,
    boxSizing: "border-box",
  };
}

function buttonStyle(disabled: boolean): CSSProperties {
  return {
    marginTop: spacing.sm,
    padding: `${spacing.sm}px ${spacing.md}px`,
    borderRadius: 8,
    border: "none",
    background: disabled ? colors.muted : colors.ok,
    color: colors.background,
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: typography.fontFamily,
  };
}

function statusBanner(state: LeagueFormState, copy: ReturnType<typeof ui>): ReactNode {
  if (state.status === "loading") {
    return (
      <p data-testid="league-status" style={{ color: colors.muted }}>
        {copy.working}
      </p>
    );
  }
  if (state.status === "error" && state.error) {
    return (
      <p data-testid="league-error" style={{ color: "#f87171" }}>
        {state.error.message}
      </p>
    );
  }
  if (state.status === "success" && state.message) {
    return (
      <p data-testid="league-success" style={{ color: colors.ok }}>
        {state.message}
      </p>
    );
  }
  if (state.status === "empty") {
    return (
      <p data-testid="league-empty" style={{ color: colors.muted }}>
        {copy.leagueEmptyForm}
      </p>
    );
  }
  return null;
}

export interface CreateLeaguePanelProps {
  client: LeagueClient;
  token: string;
  locale: SupportedLanguage;
  emailVerified: boolean;
  onVerifyEmail?: () => void;
  onCreated: (league: LeagueResponse) => void;
}

export function CreateLeaguePanel({
  client,
  token,
  locale,
  emailVerified,
  onVerifyEmail,
  onCreated,
}: CreateLeaguePanelProps) {
  const copy = ui(locale);
  const [form, setForm] = useState(initialFormState);
  const [name, setName] = useState("");
  const [seasonYear, setSeasonYear] = useState(String(new Date().getFullYear()));
  const [catalog, setCatalog] = useState<CompetitionResponse[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setForm({ status: "loading" });
    void client
      .listCompetitions(token)
      .then((rows) => {
        if (!cancelled) {
          setCatalog(rows);
          setForm({ status: "idle" });
        }
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        if (error instanceof AuthApiError) {
          setForm({
            status: "error",
            error: {
              code: error.code,
              message: mapApiErrorMessage(copy, error.code, error.message),
            },
          });
        } else {
          setForm({
            status: "error",
            error: { code: "network_error", message: copy.networkError },
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [client, copy.networkError, token]);

  function toggleCompetition(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!emailVerified) {
      setForm({ status: "error", error: { code: "email_not_verified", message: copy.emailNotVerified } });
      return;
    }

    const trimmedName = name.trim();
    const parsedSeason = Number.parseInt(seasonYear, 10);
    if (!trimmedName || !Number.isFinite(parsedSeason) || selected.size < MIN_LEAGUE_COMPETITIONS) {
      setForm({ status: "empty" });
      return;
    }

    setForm({ status: "loading" });
    try {
      const league = await client.createLeague(token, {
        name: trimmedName,
        season_year: parsedSeason,
        competition_ids: [...selected],
      });
      onCreated(league);
      setForm({ status: "success", message: copy.leagueCreated });
    } catch (error) {
      if (error instanceof AuthApiError) {
        setForm({
          status: "error",
          error: {
            code: error.code,
            message: mapApiErrorMessage(copy, error.code, error.message),
          },
        });
      } else {
        setForm({
          status: "error",
          error: { code: "network_error", message: copy.networkError },
        });
      }
    }
  }

  return (
    <section data-testid="create-league-panel">
      {statusBanner(form, copy)}

      {!emailVerified ? (
        <div data-testid="league-verify-required" style={{ marginBottom: spacing.md }}>
          <p style={{ color: "#fbbf24", marginTop: 0 }}>{copy.emailNotVerified}</p>
          <p style={{ color: colors.muted, marginTop: 0 }}>{copy.emailNotVerifiedHint}</p>
          {onVerifyEmail ? (
            <button type="button" style={buttonStyle(false)} onClick={onVerifyEmail}>
              {copy.goVerifyEmail}
            </button>
          ) : null}
        </div>
      ) : null}

      {catalog.length === 0 && form.status !== "loading" && form.status !== "error" ? (
        <p data-testid="league-catalog-empty" style={{ color: colors.muted }}>
          {copy.networkError}
        </p>
      ) : null}

      <form onSubmit={(event) => void handleSubmit(event)} style={{ maxWidth: 480 }}>
        <label style={{ display: "block", marginBottom: spacing.sm }}>
          {copy.leagueName}
          <input
            data-testid="league-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            style={fieldStyle()}
          />
        </label>

        <label style={{ display: "block", marginBottom: spacing.sm }}>
          {copy.seasonYear}
          <input
            data-testid="league-season-year"
            type="number"
            value={seasonYear}
            onChange={(event) => setSeasonYear(event.target.value)}
            style={fieldStyle()}
          />
        </label>

        <fieldset style={{ border: "none", padding: 0, margin: `0 0 ${spacing.sm}px` }}>
          <legend style={{ marginBottom: spacing.xs }}>{copy.competitions}</legend>
          <p style={{ color: colors.muted, marginTop: 0 }}>
            {copy.selectCompetitionsHint(MIN_LEAGUE_COMPETITIONS)}
          </p>
          {catalog.map((item) => (
            <label key={item.id} style={{ display: "block", marginBottom: spacing.xs }}>
              <input
                data-testid={`league-competition-${item.provider_id}`}
                type="checkbox"
                checked={selected.has(item.id)}
                onChange={() => toggleCompetition(item.id)}
              />{" "}
              {item.name} ({item.country})
            </label>
          ))}
        </fieldset>

        <button
          data-testid="league-submit"
          type="submit"
          style={buttonStyle(form.status === "loading" || !emailVerified)}
          disabled={form.status === "loading" || !emailVerified}
        >
          {copy.createLeague}
        </button>
      </form>
    </section>
  );
}
