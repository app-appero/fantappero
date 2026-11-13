import type { AdminTesterRequest } from "@fantappero/contracts";
import { Button } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { decideTesterRequests, fetchTesterRequests } from "../api/admin";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
}

/** Richieste di accesso al pilota di chi non è ancora tester (modalità test). */
export function AdminTesterRequestsPanel({
  onPendingCount,
}: {
  onPendingCount?: (count: number) => void;
}) {
  const [requests, setRequests] = useState<AdminTesterRequest[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const session = loadStoredSession();
    if (!session?.accessToken) {
      return;
    }
    try {
      const result = await fetchTesterRequests(session.accessToken);
      setRequests(result.requests);
      onPendingCount?.(result.requests.filter((row) => row.status === "pending").length);
    } catch (cause) {
      setError(getApiErrorMessage(cause, "Impossibile caricare le richieste."));
    }
  }, [onPendingCount]);

  useEffect(() => {
    void load();
  }, [load]);

  async function decide(ids: string[], action: "approve" | "reject") {
    const session = loadStoredSession();
    if (!session?.accessToken || ids.length === 0) {
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await decideTesterRequests(session.accessToken, { ids, action });
      setRequests(result.requests);
      setSelected(new Set());
      onPendingCount?.(result.requests.filter((row) => row.status === "pending").length);
      setMessage(
        action === "approve"
          ? "Approvate: ora possono accedere con Google. Ricordati di aggiungerli al gruppo WhatsApp."
          : "Richieste rifiutate.",
      );
    } catch (cause) {
      setError(getApiErrorMessage(cause, "Operazione non riuscita."));
    } finally {
      setBusy(false);
    }
  }

  const visible = requests.filter((row) => showAll || row.status === "pending");
  const pendingVisible = visible.filter((row) => row.status === "pending");

  function toggle(id: string) {
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

  return (
    <section className="fa-admin-testrequests" data-testid="admin-tester-requests">
      <h2>Richieste di accesso</h2>
      <p>
        Chi accede con Google senza essere tester può inviare nome, telefono e un messaggio.
        Approvare aggiunge l&apos;indirizzo ai tester.
      </p>
      <div className="fa-admin-users__actions">
        <Button
          type="button"
          size="sm"
          variant={showAll ? "secondary" : "primary"}
          onClick={() => setShowAll((value) => !value)}
          data-testid="admin-requests-toggle"
        >
          {showAll ? "Mostra solo in attesa" : "Mostra tutte"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="primary"
          disabled={selected.size === 0}
          loading={busy}
          onClick={() => void decide([...selected], "approve")}
          data-testid="admin-requests-approve-selected"
        >
          Approva selezionate
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={selected.size === 0}
          loading={busy}
          onClick={() => void decide([...selected], "reject")}
          data-testid="admin-requests-reject-selected"
        >
          Rifiuta selezionate
        </Button>
      </div>
      {error ? (
        <p role="alert" className="fa-field__error">
          {error}
        </p>
      ) : null}
      {message ? <p role="status">{message}</p> : null}
      {visible.length === 0 ? (
        <p data-testid="admin-requests-empty">Nessuna richiesta in attesa.</p>
      ) : (
        <ul className="fa-admin-users__list" data-testid="admin-requests-list">
          {visible.map((row) => (
            <li key={row.id} className="fa-admin-users__item" data-testid={`admin-request-${row.id}`}>
              {row.status === "pending" ? (
                <input
                  type="checkbox"
                  aria-label={`Seleziona ${row.firstName} ${row.lastName}`}
                  checked={selected.has(row.id)}
                  onChange={() => toggle(row.id)}
                />
              ) : null}
              <span className="fa-admin-users__identity">
                <strong>
                  {row.firstName} {row.lastName}
                </strong>
                <small>{row.email}</small>
                <small>Tel. {row.phone}</small>
                {row.motivation ? <small>«{row.motivation}»</small> : null}
                <small>
                  {formatDate(row.createdAt)} ·{" "}
                  {row.status === "pending"
                    ? "in attesa"
                    : row.status === "approved"
                      ? "approvata"
                      : "rifiutata"}
                </small>
              </span>
              {row.status === "pending" ? (
                <span className="fa-admin-users__actions">
                  <Button
                    type="button"
                    size="sm"
                    variant="primary"
                    loading={busy}
                    onClick={() => void decide([row.id], "approve")}
                    data-testid={`admin-request-approve-${row.id}`}
                  >
                    Approva
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    loading={busy}
                    onClick={() => void decide([row.id], "reject")}
                    data-testid={`admin-request-reject-${row.id}`}
                  >
                    Rifiuta
                  </Button>
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {pendingVisible.length > 1 ? (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => setSelected(new Set(pendingVisible.map((row) => row.id)))}
          data-testid="admin-requests-select-all"
        >
          Seleziona tutte
        </Button>
      ) : null}
    </section>
  );
}
