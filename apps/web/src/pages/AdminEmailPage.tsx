import type { OperatorEmailHistoryItem } from "@fantappero/contracts";
import { Breadcrumb, Button, Input, PageContainer, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import { fetchOperatorEmails, sendOperatorEmail } from "../api/notifications";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { RadioCard, RecipientPicker } from "./AdminNotificationsPage";

type Tab = "nuova" | "storico";

function formatSent(value: string): string {
  try {
    return new Intl.DateTimeFormat("it-IT", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Rome" }).format(
      new Date(value),
    );
  } catch {
    return value;
  }
}

function ComposeTab() {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [mode, setMode] = useState<"all" | "users">("users");
  const [selected, setSelected] = useState<Map<string, string>>(new Map());
  const [pickerOpen, setPickerOpen] = useState(false);
  const [allTotal, setAllTotal] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const recipients = mode === "all" ? allTotal : selected.size;

  async function submit(toMeOnly: boolean) {
    const session = loadStoredSession();
    if (!session?.accessToken) return;
    if (!subject.trim() || !body.trim()) {
      setError("Oggetto e testo sono obbligatori.");
      return;
    }
    if (!toMeOnly && mode === "users" && selected.size === 0) {
      setError("Scegli almeno un destinatario.");
      return;
    }
    if (toMeOnly && !session.user?.id) {
      setError("Utente non riconosciuto.");
      return;
    }
    if (!toMeOnly && !window.confirm(`Inviare l'email a ${recipients ?? "tutti gli"} utenti?`)) {
      return;
    }
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const result = await sendOperatorEmail(session.accessToken, {
        subject: subject.trim(),
        body: body.trim(),
        audience: toMeOnly
          ? { mode: "users", userIds: [session.user.id] }
          : mode === "all"
            ? { mode: "all" }
            : { mode: "users", userIds: [...selected.keys()] },
      });
      setDone(`Email inviata a ${result.recipientCount} utenti.`);
    } catch (e) {
      setError(getApiErrorMessage(e, "Invio non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fa-nop-cols">
      <div className="fa-nop-stack">
        <section className="fa-nop-card">
          <header className="fa-nop-card__head"><h3>1 · Destinatari</h3></header>
          <div className="fa-nop-radios" role="radiogroup" aria-label="Destinatari">
            <RadioCard label="Tutti gli utenti" hint="Tutti gli iscritti" checked={mode === "all"} onSelect={() => { setMode("all"); setPickerOpen(false); }} testId="admin-email-audience-all" />
            <RadioCard label="Selezione manuale" hint="Scegli tu uno per uno" checked={mode === "users"} onSelect={() => setMode("users")} testId="admin-email-audience-users" />
          </div>
          {mode === "users" ? (
            <button type="button" className="fa-nop-selected" onClick={() => setPickerOpen(true)} data-testid="admin-email-open-picker">
              <strong>{selected.size === 1 ? "1 utente selezionato" : `${selected.size} utenti selezionati`}</strong>
              <span>Scegli utenti ›</span>
            </button>
          ) : null}
          <p className="fa-nop-hint">Chi ha disattivato le email non riceve il messaggio.</p>
        </section>
        {pickerOpen && mode === "users" ? (
          <RecipientPicker
            selected={selected}
            onChange={setSelected}
            onSelectAll={(total) => { setMode("all"); setAllTotal(total); setPickerOpen(false); }}
            onClose={() => setPickerOpen(false)}
          />
        ) : null}
        <section className="fa-nop-card">
          <header className="fa-nop-card__head"><h3>2 · Messaggio</h3></header>
          <Input label="Oggetto" name="admin-email-subject" value={subject} maxLength={120} onChange={(e) => setSubject(e.target.value)} data-testid="admin-email-subject" />
          <label className="fa-field">
            <span className="fa-field__label">Testo</span>
            <textarea className="fa-nop-textarea" rows={7} maxLength={5000} value={body} onChange={(e) => setBody(e.target.value)} data-testid="admin-email-body" />
          </label>
        </section>
        <section className="fa-nop-card">
          <header className="fa-nop-card__head"><h3>3 · Invio</h3></header>
          {error ? <UiStatePanel state="error" title="Invio non riuscito" message={error} testId="admin-email-error" /> : null}
          {done ? <p className="fa-nop-done" data-testid="admin-email-done">{done}</p> : null}
          <div className="fa-nop-row">
            <Button type="button" loading={busy} disabled={busy} onClick={() => void submit(false)} data-testid="admin-email-send">
              {recipients === null ? "Invia" : `Invia a ${recipients} utenti`}
            </Button>
            <Button type="button" variant="secondary" disabled={busy} onClick={() => void submit(true)} data-testid="admin-email-send-me">
              Invia a me come prova
            </Button>
          </div>
          <p className="fa-nop-hint">Le email automatiche (registrazione, verifica, reset password) partono da sole e non passano di qui.</p>
        </section>
      </div>
      <aside className="fa-nop-stack fa-nop-aside">
        <section className="fa-nop-card">
          <header className="fa-nop-card__head"><h3>Anteprima email</h3></header>
          <div className="fa-nop-mail">
            <strong>FantApperò</strong>
            <h4>{subject || "Oggetto dell'email"}</h4>
            <p>{body || "Il testo del messaggio comparirà qui."}</p>
            <small>Ricevi questa email perché hai un account FantApperò.</small>
          </div>
        </section>
        <section className="fa-nop-card">
          <header className="fa-nop-card__head"><h3>Riepilogo</h3></header>
          <dl className="fa-nop-sum">
            <div><dt>Destinatari</dt><dd>{recipients === null ? "—" : `${recipients} utenti`}</dd></div>
          </dl>
        </section>
      </aside>
    </div>
  );
}

function HistoryTab() {
  const [items, setItems] = useState<OperatorEmailHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    const token = loadStoredSession()?.accessToken;
    if (!token) return;
    try {
      setItems((await fetchOperatorEmails(token)).items);
    } catch (e) {
      setError(getApiErrorMessage(e, "Impossibile caricare lo storico."));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <div className="fa-nop-stack" data-testid="admin-email-history">
      {loading ? <UiStatePanel state="loading" title="Caricamento storico" message="Un attimo…" /> : null}
      {error ? <UiStatePanel state="error" title="Storico non disponibile" message={error} /> : null}
      {!loading && !error && items.length === 0 ? (
        <UiStatePanel state="empty" title="Nessuna email inviata" message="Le email inviate dal portale compariranno qui." />
      ) : null}
      <ul className="fa-nop-history">
        {items.map((item) => (
          <li key={item.id} className="fa-nop-hist">
            <div className="fa-nop-hist__main">
              <strong>{item.subject}</strong>
              <small>{item.audienceLabel} · {formatSent(item.sentAt)}</small>
            </div>
            <span className="fa-nop-hist__nums">{item.recipientCount} destinatari</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AdminEmailPage() {
  const [tab, setTab] = useState<Tab>("nuova");
  return (
    <PageContainer title="Email" header={<Breadcrumb items={[{ label: "Operazioni", href: "/admin" }, { label: "Email" }]} />}>
      <div className="fa-nop" data-testid="admin-email">
        <p className="fa-jobs__intro">
          Scrivi e invia email agli utenti dal portale: solo per segnalazioni e comunicazioni particolari.
        </p>
        <div className="fa-nop-filters" role="tablist" aria-label="Sezioni email">
          {(["nuova", "storico"] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              className={tab === value ? "fa-nop-pill fa-nop-pill--on fa-nop-pill--big" : "fa-nop-pill fa-nop-pill--big"}
              onClick={() => setTab(value)}
              data-testid={`admin-email-tab-${value}`}
            >
              {value === "nuova" ? "Nuova" : "Storico"}
            </button>
          ))}
        </div>
        {tab === "nuova" ? <ComposeTab /> : <HistoryTab />}
      </div>
    </PageContainer>
  );
}
