import type {
  AdminListoneEntry,
  AdminMarketValueDetail,
  AdminMarketValueSeasonDetail,
} from "@fantappero/contracts";
import {
  formatPercentileOrdinal,
  formatValueNumber,
  formatWeightPercent,
  marketValueBaseSentence,
  marketValueBudgetSentence,
  marketValueCreditsForBudget,
  marketValueCurveSentence,
  marketValueExcludedText,
  marketValueIndexSentence,
  marketValueRolePlural,
  marketValueSeasonName,
  marketValueSeasonSentence,
  marketValueSourceLabel,
  marketValueStatusText,
} from "@fantappero/contracts";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  UiStatePanel,
  roleBadgeVariant,
} from "@fantappero/ui";
import { type ReactNode, useMemo, useRef, useState } from "react";
import { fetchAdminMarketValueDetail } from "../api/admin";
import { ApiError } from "../api/client";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { foldSearchText } from "../utils/searchText";

/** Quanti calciatori proporre sotto la ricerca. */
export const VALUE_DETAIL_MAX_RESULTS = 8;
const MIN_QUERY_LENGTH = 2;

function matches(entries: AdminListoneEntry[], query: string): AdminListoneEntry[] {
  const normalized = foldSearchText(query);
  if (normalized.length < MIN_QUERY_LENGTH) {
    return [];
  }
  const found: AdminListoneEntry[] = [];
  for (const entry of entries) {
    if (foldSearchText(`${entry.canonicalName} ${entry.clubName ?? ""}`).includes(normalized)) {
      found.push(entry);
      if (found.length >= VALUE_DETAIL_MAX_RESULTS) {
        break;
      }
    }
  }
  return found;
}

function numberOrDash(value: number | null, digits = 2): string {
  return value === null ? "—" : formatValueNumber(value, digits);
}

function percentileCell(season: AdminMarketValueSeasonDetail): string {
  if (season.percentile === null) {
    return season.isCurrent ? "—" : `${formatValueNumber(season.indexUsed)} (senza dati)`;
  }
  const rank = season.rank !== null && season.poolSize !== null ? ` · ${season.rank}° di ${season.poolSize}` : "";
  return `${formatPercentileOrdinal(season.percentile)}${rank}`;
}

const DATE_TIME = new Intl.DateTimeFormat("it-IT", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Rome",
});

function computedAtLabel(detail: AdminMarketValueDetail): string | null {
  if (!detail.computedAt) {
    return null;
  }
  const date = new Date(detail.computedAt);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  const version = detail.version ? ` · formula ${detail.version}` : "";
  return `Ultimo ricalcolo: ${DATE_TIME.format(date)}${version}`;
}

type Row = { label: string; title?: string; cell: (season: AdminMarketValueSeasonDetail) => ReactNode };

function seasonRows(detail: AdminMarketValueDetail): Row[] {
  const plural = marketValueRolePlural(detail.role);
  return [
    { label: "Fonte", cell: (season) => (season.source ? marketValueSourceLabel(season.source) : "—") },
    {
      label: "Competizioni",
      title: "Righe di campionato contate (le coppe non contano)",
      cell: (season) => (season.competitions.length > 0 ? season.competitions.join(", ") : "—"),
    },
    {
      label: "Presenze con voto",
      cell: (season) => (season.hasData || season.appearances > 0 ? String(season.appearances) : "—"),
    },
    { label: "Media", cell: (season) => numberOrDash(season.average) },
    { label: `Media dei ${plural}`, cell: (season) => numberOrDash(season.roleAverage) },
    {
      label: "Media ristretta",
      title: `(n × media + ${detail.shrinkAppearances} × media del ruolo) / (n + ${detail.shrinkAppearances})`,
      cell: (season) => numberOrDash(season.shrunkAverage),
    },
    { label: "Percentile", cell: percentileCell },
    { label: "Peso", cell: (season) => formatWeightPercent(season.weight) },
    { label: "Contributo a p", cell: (season) => formatValueNumber(season.contribution) },
  ];
}

function DetailTable({ detail }: { detail: AdminMarketValueDetail }) {
  return (
    <Table compact className="fa-value-detail__table" data-testid="admin-value-detail-table">
      <TableHead>
        <TableRow>
          <TableHeaderCell>
            <span className="fa-value-detail__sr">Voce</span>
          </TableHeaderCell>
          {detail.seasons.map((season) => (
            <TableHeaderCell key={season.slot}>
              {marketValueSeasonName(season.seasonYear)}
              {season.isCurrent ? <small> in corso</small> : null}
            </TableHeaderCell>
          ))}
        </TableRow>
      </TableHead>
      <TableBody>
        {seasonRows(detail).map((row) => (
          <TableRow key={row.label}>
            <TableHeaderCell scope="row" title={row.title}>
              {row.label}
            </TableHeaderCell>
            {detail.seasons.map((season) => (
              <TableCell key={season.slot}>{row.cell(season)}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function parseBudget(text: string): number | null {
  const value = Number(text);
  return Number.isInteger(value) && value >= 1 && value <= 100_000 ? value : null;
}

/**
 * «Dettaglio del Valore» nel Listone del pannello operatore (1.4, `docs/operations/
 * valore_di_mercato_e_storico.md` § 8): cerca un calciatore del listone già caricato nella
 * pagina, poi mostra per ogni stagione da dove vengono i numeri (tabella) e il calcolo finale in
 * italiano. Legge l'ultimo ricalcolo, non chiama il fornitore. La pagina è solo per gli
 * operatori (`global:operate`).
 */
export function MarketValueDetailPanel({
  entries,
  seasonYear,
}: {
  entries: AdminListoneEntry[];
  seasonYear: number | null;
}) {
  const [query, setQuery] = useState("");
  const [budgetText, setBudgetText] = useState("1000");
  const [detail, setDetail] = useState<AdminMarketValueDetail | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef(0);

  const results = useMemo(() => matches(entries, query), [entries, query]);
  const budget = parseBudget(budgetText);

  async function onPick(entry: AdminListoneEntry) {
    const session = loadStoredSession();
    if (seasonYear === null) {
      setError("Inserisci un anno stagione valido nel listone.");
      return;
    }
    if (!session?.accessToken) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    const request = ++requestRef.current;
    setLoadingId(entry.athleteId);
    setError(null);
    try {
      const loaded = await fetchAdminMarketValueDetail(session.accessToken, entry.athleteId, { seasonYear });
      if (request === requestRef.current) {
        setDetail(loaded);
      }
    } catch (loadError) {
      if (request === requestRef.current) {
        setDetail(null);
        setError(
          loadError instanceof ApiError && loadError.status === 404
            ? "Il calciatore non è nel listone di questa stagione."
            : getApiErrorMessage(loadError, "Impossibile leggere il dettaglio del Valore."),
        );
      }
    } finally {
      if (request === requestRef.current) {
        setLoadingId(null);
      }
    }
  }

  const statusText = detail ? marketValueStatusText(detail) : null;
  const computedAt = detail ? computedAtLabel(detail) : null;

  return (
    <Card className="fa-admin-listone-restore fa-value-detail" data-testid="admin-value-detail">
      <CardHeader>
        <h2 className="fa-admin-listone-restore__title">Dettaglio del Valore</h2>
      </CardHeader>
      <CardBody>
        <p className="fa-admin-listone-restore__intro">
          Cerca un calciatore del listone per vedere come si arriva al suo Valore: stagione per
          stagione, poi il calcolo finale. Mostra l'ultimo ricalcolo («Ricalcola valori» lo rifà);
          non chiama il fornitore.
        </p>
        <div className="fa-admin-listone-restore__form">
          <Input
            label="Cerca calciatore"
            name="admin-value-detail-query"
            value={query}
            placeholder="Nome o club"
            autoComplete="off"
            onChange={(event) => setQuery(event.target.value)}
            data-testid="admin-value-detail-query"
          />
          <Input
            label="Budget della lega"
            name="admin-value-detail-budget"
            type="number"
            inputMode="numeric"
            value={budgetText}
            onChange={(event) => setBudgetText(event.target.value)}
            data-testid="admin-value-detail-budget"
          />
        </div>

        {entries.length === 0 ? (
          <p className="fa-value-detail__hint" data-testid="admin-value-detail-no-listone">
            Il listone della stagione non è caricato: la ricerca usa i calciatori qui sopra.
          </p>
        ) : null}

        {results.length > 0 ? (
          <ul className="fa-value-detail__results" data-testid="admin-value-detail-results">
            {results.map((entry) => (
              <li key={entry.athleteId}>
                <Button
                  type="button"
                  variant={detail?.athleteId === entry.athleteId ? "secondary" : "ghost"}
                  loading={loadingId === entry.athleteId}
                  disabled={loadingId !== null}
                  onClick={() => void onPick(entry)}
                  data-testid={`admin-value-detail-pick-${entry.athleteId}`}
                >
                  <Badge variant={roleBadgeVariant(entry.officialRole)}>{entry.officialRole}</Badge>
                  <span className="fa-value-detail__pick">
                    {entry.canonicalName}
                    {entry.clubName ? <span className="fa-value-detail__club"> · {entry.clubName}</span> : null}
                  </span>
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        {query.trim().length >= MIN_QUERY_LENGTH && results.length === 0 && entries.length > 0 ? (
          <p className="fa-value-detail__hint" data-testid="admin-value-detail-no-results">
            Nessun calciatore del listone con questo nome o club.
          </p>
        ) : null}

        {error ? (
          <UiStatePanel
            state="error"
            title="Dettaglio non disponibile"
            message={error}
            testId="admin-value-detail-error"
          />
        ) : null}

        {detail ? (
          <section className="fa-value-detail__result" data-testid="admin-value-detail-result" aria-live="polite">
            <p className="fa-season-history__summary" data-testid="admin-value-detail-summary">
              <strong>{detail.canonicalName}</strong> ({detail.role}
              {detail.clubName ? `, ${detail.clubName}` : ""}): Valore{" "}
              <strong>
                {detail.referenceCredits} {detail.referenceCredits === 1 ? "credito" : "crediti"}
              </strong>{" "}
              a budget {detail.referenceBudget}
              {budget !== null && budget !== detail.referenceBudget ? (
                <>
                  , <strong>{marketValueCreditsForBudget(detail.referenceValue, budget, detail.referenceBudget)}</strong> a
                  budget {budget}
                </>
              ) : null}{" "}
              · p = {formatValueNumber(detail.valueIndex)}
            </p>
            {statusText ? (
              <UiStatePanel
                state="empty"
                title={detail.status === "outdated" ? "Dettaglio incompleto" : "Valore non ancora calcolato"}
                message={statusText}
                testId="admin-value-detail-status"
              />
            ) : null}

            <DetailTable detail={detail} />

            <h3 className="fa-value-detail__subtitle">Come si arriva al Valore</h3>
            <ol className="fa-value-detail__steps" data-testid="admin-value-detail-steps">
              {detail.seasons.map((season) => {
                const excluded = marketValueExcludedText(season);
                return (
                  <li key={season.slot}>
                    {marketValueSeasonSentence(season, detail.role, detail.missingSeasonIndex)}
                    {excluded ? <span className="fa-value-detail__excluded">{excluded}</span> : null}
                  </li>
                );
              })}
              <li>{marketValueIndexSentence(detail)}</li>
              <li>{marketValueCurveSentence(detail)}</li>
              {budget !== null && budget !== detail.referenceBudget ? (
                <li data-testid="admin-value-detail-budget-step">{marketValueBudgetSentence(detail, budget)}</li>
              ) : null}
            </ol>
            <p className="fa-value-detail__note">
              {marketValueBaseSentence(detail)}. Media ristretta = (n × media + {detail.shrinkAppearances} × media
              del ruolo) / (n + {detail.shrinkAppearances}); una stagione passata senza dati vale{" "}
              {formatValueNumber(detail.missingSeasonIndex)}; la stagione in corso pesa fino al 50% (pieno a{" "}
              {detail.currentFullWeightAppearances} partite con voto), il resto va alle passate 30:20.
              {computedAt ? ` ${computedAt}.` : ""}
            </p>
          </section>
        ) : null}
      </CardBody>
    </Card>
  );
}
