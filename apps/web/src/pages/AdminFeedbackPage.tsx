import {
  FEEDBACK_CATEGORY_LABEL,
  FEEDBACK_NOTE_MAX_CHARS,
  FEEDBACK_STATUSES,
  FEEDBACK_STATUS_LABEL,
  type FeedbackAdminList,
  type FeedbackAdminReport,
  type FeedbackAttachment,
  type FeedbackStatus,
} from "@fantappero/contracts";
import { Breadcrumb, Button, Modal, PageContainer, Select, Textarea, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { impersonateUser } from "../api/admin";
import { deleteAdminFeedback, fetchAdminFeedback, updateAdminFeedback } from "../api/feedback";
import { ApiError, buildApiUrl } from "../api/client";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { impersonationDestination } from "../feedback/impersonation";
import { useNavigate } from "../router/simpleRouter";

const FILTER_OPTIONS = [
  { value: "", label: "Tutte" },
  ...FEEDBACK_STATUSES.map((value) => ({ value, label: FEEDBACK_STATUS_LABEL[value] })),
];

const NEXT_ACTIONS: Array<{ status: FeedbackStatus; label: string }> = [
  { status: "in_review", label: "Prendi in carico" },
  { status: "resolved", label: "Segna come risolta" },
  { status: "dismissed", label: "Chiudi" },
  { status: "new", label: "Riapri" },
];

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat("it-IT", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Rome",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function Media({ attachment, onExpired }: { attachment: FeedbackAttachment; onExpired: () => void }) {
  const src = buildApiUrl(attachment.url);
  if (attachment.kind === "video") {
    return (
      <video
        className="fa-feedback-admin__media"
        src={src}
        controls
        preload="metadata"
        onError={onExpired}
        data-testid="feedback-admin-video"
      />
    );
  }
  return (
    <a href={src} target="_blank" rel="noopener noreferrer" data-testid="feedback-admin-image-link">
      <img className="fa-feedback-admin__media" src={src} alt="Allegato della segnalazione" onError={onExpired} />
    </a>
  );
}

function ReportCard({
  report,
  canImpersonate,
  onImpersonate,
  onDelete,
  onChanged,
  onExpired,
}: {
  report: FeedbackAdminReport;
  canImpersonate: boolean;
  onImpersonate: (report: FeedbackAdminReport) => void;
  onDelete: (report: FeedbackAdminReport) => void;
  onChanged: (next: FeedbackAdminReport) => void;
  onExpired: () => void;
}) {
  const [note, setNote] = useState(report.operatorNote ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(status?: FeedbackStatus) {
    const token = loadStoredSession()?.accessToken;
    if (!token) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onChanged(await updateAdminFeedback(token, report.id, { status, operatorNote: note }));
    } catch (saveError) {
      setError(getApiErrorMessage(saveError, "Aggiornamento non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  const noteChanged = note.trim() !== (report.operatorNote ?? "");
  return (
    <article className="fa-feedback-admin__card" data-testid={`feedback-admin-${report.id}`}>
      <header className="fa-feedback-admin__head">
        <span className={`fa-feedback__status fa-feedback__status--${report.status}`}>
          {FEEDBACK_STATUS_LABEL[report.status]}
        </span>
        <strong>{FEEDBACK_CATEGORY_LABEL[report.category]}</strong>
        <span className="fa-feedback-admin__who">
          {report.authorName} · {report.authorEmail}
        </span>
        {canImpersonate ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => onImpersonate(report)}
            data-testid={`feedback-admin-impersonate-${report.id}`}
          >
            Impersona
          </Button>
        ) : null}
        <time dateTime={report.createdAt}>{formatDate(report.createdAt)}</time>
      </header>

      <p className="fa-feedback-admin__message">{report.message}</p>

      <dl className="fa-feedback-admin__meta">
        {report.pageContext ? (
          <div>
            <dt>Pagina</dt>
            <dd>{report.pageContext}</dd>
          </div>
        ) : null}
        {report.platform ? (
          <div>
            <dt>Piattaforma</dt>
            <dd>{report.platform}</dd>
          </div>
        ) : null}
        {report.appVersion ? (
          <div>
            <dt>Versione</dt>
            <dd>{report.appVersion}</dd>
          </div>
        ) : null}
        {report.userAgent ? (
          <div>
            <dt>Dispositivo</dt>
            <dd>{report.userAgent}</dd>
          </div>
        ) : null}
      </dl>

      {report.attachments.length > 0 ? (
        <div className="fa-feedback-admin__attachments">
          {report.attachments.map((attachment) => (
            <Media key={attachment.id} attachment={attachment} onExpired={onExpired} />
          ))}
        </div>
      ) : null}

      <Textarea
        label="Nota interna (visibile solo agli operatori)"
        value={note}
        rows={2}
        maxLength={FEEDBACK_NOTE_MAX_CHARS}
        onChange={(event) => setNote(event.target.value)}
        data-testid={`feedback-admin-note-${report.id}`}
      />
      {error ? <UiStatePanel state="error" title="Non salvato" message={error} /> : null}
      <div className="fa-feedback-admin__actions">
        {NEXT_ACTIONS.filter((action) => action.status !== report.status).map((action) => (
          <Button
            key={action.status}
            type="button"
            variant={action.status === "resolved" ? "primary" : "secondary"}
            disabled={busy}
            onClick={() => void save(action.status)}
            data-testid={`feedback-admin-${action.status}-${report.id}`}
          >
            {action.label}
          </Button>
        ))}
        {noteChanged ? (
          <Button type="button" variant="ghost" disabled={busy} onClick={() => void save()}>
            Salva nota
          </Button>
        ) : null}
        <Button
          type="button"
          variant="danger"
          disabled={busy}
          onClick={() => onDelete(report)}
          data-testid={`feedback-admin-delete-${report.id}`}
        >
          Elimina
        </Button>
      </div>
    </article>
  );
}

/** Pannello operatore: segnalazioni degli utenti, con allegati e stato di lavorazione. */
export function AdminFeedbackPage() {
  const { user, startImpersonation } = useAuth();
  const navigate = useNavigate();
  const [pending, setPending] = useState<FeedbackAdminReport | null>(null);
  const [impersonating, setImpersonating] = useState(false);
  const [impersonationError, setImpersonationError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<FeedbackAdminReport | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FeedbackStatus | "">("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<FeedbackAdminList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);

  const load = useCallback(async () => {
    const token = loadStoredSession()?.accessToken;
    if (!token) {
      setError("Sessione non disponibile. Accedi di nuovo.");
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setData(await fetchAdminFeedback(token, { status: filter || undefined, page }));
      setError(null);
      setExpired(false);
    } catch (loadError) {
      setError(getApiErrorMessage(loadError, "Impossibile caricare le segnalazioni."));
    } finally {
      setLoading(false);
    }
  }, [filter, page]);

  useEffect(() => {
    void load();
  }, [load]);

  function replace(next: FeedbackAdminReport) {
    setData((current) =>
      current ? { ...current, items: current.items.map((item) => (item.id === next.id ? next : item)) } : current,
    );
    // Lo stato è cambiato: il conteggio delle «da leggere» e il filtro attivo vanno riallineati.
    void load();
  }

  async function confirmDelete() {
    if (!pendingDelete) {
      return;
    }
    const token = loadStoredSession()?.accessToken;
    if (!token) {
      setDeleteError("Sessione non disponibile. Accedi di nuovo.");
      setPendingDelete(null);
      return;
    }
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteAdminFeedback(token, pendingDelete.id);
      setData((current) =>
        current
          ? { ...current, items: current.items.filter((item) => item.id !== pendingDelete.id) }
          : current,
      );
      // Il totale, la pagina e le «da leggere» cambiano: si riallineano col server.
      void load();
    } catch (removeError) {
      setDeleteError(getApiErrorMessage(removeError, "Eliminazione non riuscita."));
    } finally {
      setDeleting(false);
      setPendingDelete(null);
    }
  }

  async function confirmImpersonation() {
    if (!pending) {
      return;
    }
    const token = loadStoredSession()?.accessToken;
    if (!token) {
      setImpersonationError("Sessione non disponibile. Accedi di nuovo.");
      setPending(null);
      return;
    }
    setImpersonating(true);
    setImpersonationError(null);
    try {
      const result = await impersonateUser(token, pending.authorUserId);
      await startImpersonation(result);
      // Si entra come l'utente direttamente nella pagina dove ha visto il problema.
      navigate(impersonationDestination(pending.pageContext));
    } catch (impersonateError) {
      if (impersonateError instanceof ApiError && impersonateError.code === "cannot_impersonate_self") {
        setImpersonationError("Non puoi impersonare te stesso.");
      } else if (impersonateError instanceof ApiError && impersonateError.status === 403) {
        setImpersonationError("Non hai i permessi per impersonare questo utente.");
      } else {
        setImpersonationError(getApiErrorMessage(impersonateError, "Impossibile impersonare l'utente."));
      }
      setPending(null);
    } finally {
      setImpersonating(false);
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1;
  return (
    <PageContainer
      title="Segnalazioni degli utenti"
      header={<Breadcrumb items={[{ label: "Pannello", href: "/admin" }, { label: "Segnalazioni" }]} />}
    >
      <div className="fa-feedback-admin__toolbar">
        <Select
          label="Stato"
          name="status"
          value={filter}
          onChange={(event) => {
            setFilter(event.target.value as FeedbackStatus | "");
            setPage(1);
          }}
          options={FILTER_OPTIONS}
        />
        {data ? (
          <p className="fa-feedback-admin__count" data-testid="feedback-admin-new-count">
            {data.newCount === 0 ? "Nessuna segnalazione da leggere" : `${data.newCount} da leggere`}
          </p>
        ) : null}
        <Button type="button" variant="secondary" onClick={() => void load()}>
          Aggiorna
        </Button>
      </div>

      {expired ? (
        <UiStatePanel
          state="empty"
          title="Allegato non disponibile"
          message="I link degli allegati durano pochi minuti. Premi «Aggiorna» per rigenerarli."
          testId="feedback-admin-expired"
        />
      ) : null}
      {impersonationError ? (
        <UiStatePanel
          state="error"
          title="Impersonificazione non riuscita"
          message={impersonationError}
          testId="feedback-admin-impersonate-error"
        />
      ) : null}
      {deleteError ? (
        <UiStatePanel
          state="error"
          title="Eliminazione non riuscita"
          message={deleteError}
          testId="feedback-admin-delete-error"
        />
      ) : null}
      {loading && !data ? <UiStatePanel state="loading" title="Caricamento" message="Recupero le segnalazioni…" /> : null}
      {error ? <UiStatePanel state="error" title="Errore di caricamento" message={error} testId="feedback-admin-error" /> : null}
      {data && data.items.length === 0 && !error ? (
        <UiStatePanel
          state="empty"
          title="Nessuna segnalazione"
          message="Quando un utente ne invia una, la trovi qui e ricevi una notifica."
          testId="feedback-admin-empty"
        />
      ) : null}

      <div className="fa-feedback-admin__list">
        {data?.items.map((report) => (
          <ReportCard
            key={report.id}
            report={report}
            canImpersonate={report.authorEmail !== "" && report.authorUserId !== user?.id}
            onImpersonate={setPending}
            onDelete={setPendingDelete}
            onChanged={replace}
            onExpired={() => setExpired(true)}
          />
        ))}
      </div>

      {data && pages > 1 ? (
        <div className="fa-feedback-admin__pager">
          <Button type="button" variant="secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
            Precedente
          </Button>
          <span>
            Pagina {page} di {pages}
          </span>
          <Button type="button" variant="secondary" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>
            Successiva
          </Button>
        </div>
      ) : null}

      <Modal
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Elimina segnalazione"
        footer={
          <>
            <Button type="button" variant="ghost" onClick={() => setPendingDelete(null)}>
              Annulla
            </Button>
            <Button
              type="button"
              variant="danger"
              loading={deleting}
              disabled={deleting}
              onClick={() => void confirmDelete()}
              data-testid="feedback-admin-delete-confirm"
            >
              Elimina definitivamente
            </Button>
          </>
        }
      >
        <p>
          {pendingDelete
            ? `Vuoi eliminare la segnalazione di ${pendingDelete.authorName}? Si cancellano per sempre anche il testo${
                pendingDelete.attachments.length > 0 ? ", le immagini e i video allegati" : ""
              }. L'operazione non si può annullare.`
            : ""}
        </p>
      </Modal>

      <Modal
        open={pending !== null}
        onClose={() => setPending(null)}
        title="Impersona utente"
        footer={
          <>
            <Button type="button" variant="ghost" onClick={() => setPending(null)}>
              Annulla
            </Button>
            <Button
              type="button"
              variant="primary"
              loading={impersonating}
              disabled={impersonating}
              onClick={() => void confirmImpersonation()}
              data-testid="feedback-admin-impersonate-confirm"
            >
              Conferma
            </Button>
          </>
        }
      >
        <p>
          {pending
            ? `Accederai come ${pending.authorName} per qualche minuto, a scopo di assistenza, e aprirai la pagina da cui ha segnalato il problema. L'operazione viene registrata nell'audit log.`
            : ""}
        </p>
      </Modal>
    </PageContainer>
  );
}
