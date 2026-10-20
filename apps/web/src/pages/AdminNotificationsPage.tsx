import {
  BROADCAST_CATEGORY_OPTIONS,
  BROADCAST_DESTINATIONS,
  BROADCAST_KIND_OPTIONS,
  type BroadcastItem,
  type BroadcastKind,
  type NotificationCategory,
  type NotificationRecipient,
  type NotificationRecipientList,
  type TestSampleItem,
} from "@fantappero/contracts";
import { Breadcrumb, Button, Input, PageContainer, Select, Switch, UiStatePanel } from "@fantappero/ui";
import { useCallback, useEffect, useState } from "react";
import {
  createBroadcast,
  fetchBroadcasts,
  fetchNotificationRecipients,
  fetchTestSamples,
  sendTestSamples,
} from "../api/notifications";
import { getApiErrorMessage } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

type Tab = "nuova" | "test" | "storico";
type AudienceMode = "all" | "users";
type RecipientFilter = "all" | "push" | "noPush" | "operators";

const PAGE_SIZE = 10;
const KIND_GLYPH: Record<BroadcastKind, string> = { test: "🧪", avviso: "📣", novita: "✨", manutenzione: "🛠" };

function token(): string | null {
  return loadStoredSession()?.accessToken ?? null;
}

function formatWhen(item: BroadcastItem): string {
  const value = item.status === "scheduled" ? item.scheduledAt : item.sentAt;
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("it-IT", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Rome" }).format(
      new Date(value),
    );
  } catch {
    return value;
  }
}

function RadioCard(props: { label: string; hint: string; checked: boolean; onSelect: () => void; testId: string }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={props.checked}
      className={props.checked ? "fa-nop-radio fa-nop-radio--on" : "fa-nop-radio"}
      onClick={props.onSelect}
      data-testid={props.testId}
    >
      <span className="fa-nop-radio__dot" aria-hidden="true" />
      <span>
        <strong>{props.label}</strong>
        <small>{props.hint}</small>
      </span>
    </button>
  );
}

function Check(props: { on: boolean }) {
  return (
    <span className={props.on ? "fa-nop-check fa-nop-check--on" : "fa-nop-check"} aria-hidden="true">
      {props.on ? "✓" : ""}
    </span>
  );
}

function RecipientPicker(props: {
  selected: Map<string, string>;
  onChange: (next: Map<string, string>) => void;
  onSelectAll: (total: number) => void;
  onClose: () => void;
}) {
  const { selected, onChange } = props;
  const [data, setData] = useState<NotificationRecipientList | null>(null);
  const [filter, setFilter] = useState<RecipientFilter>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const accessToken = token();
    if (!accessToken) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchNotificationRecipients(accessToken, {
      search: search.trim() || undefined,
      pushOnly: filter === "push",
      noPush: filter === "noPush",
      operatorsOnly: filter === "operators",
      page,
      pageSize: PAGE_SIZE,
    })
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((e) => {
        if (!cancelled) setError(getApiErrorMessage(e, "Impossibile caricare gli utenti."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filter, search, page]);

  function toggle(user: NotificationRecipient) {
    const next = new Map(selected);
    if (next.has(user.userId)) next.delete(user.userId);
    else next.set(user.userId, user.displayName);
    onChange(next);
  }

  const items = data?.items ?? [];
  const pageAll = items.length > 0 && items.every((u) => selected.has(u.userId));
  function togglePage() {
    const next = new Map(selected);
    for (const u of items) {
      if (pageAll) next.delete(u.userId);
      else next.set(u.userId, u.displayName);
    }
    onChange(next);
  }
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const counts = data?.counts;
  const filters: Array<[RecipientFilter, string, number | undefined]> = [
    ["all", "Tutti", counts?.all],
    ["push", "Con push attivo", counts?.push],
    ["noPush", "Senza push", counts?.noPush],
    ["operators", "Operatori", counts?.operators],
  ];

  return (
    <section className="fa-nop-card" data-testid="admin-notifications-picker">
      <header className="fa-nop-card__head">
        <h3>Scegli utenti</h3>
        <p>Cerca, filtra e spunta. La selezione resta anche cambiando pagina.</p>
      </header>
      <Input
        label="Cerca per nome o email"
        name="admin-notifications-search"
        value={search}
        onChange={(event) => {
          setSearch(event.target.value);
          setPage(1);
        }}
        data-testid="admin-notifications-search"
      />
      <div className="fa-nop-filters" role="group" aria-label="Filtri utenti">
        {filters.map(([value, label, count]) => (
          <button
            key={value}
            type="button"
            className={filter === value ? "fa-nop-pill fa-nop-pill--on" : "fa-nop-pill"}
            onClick={() => {
              setFilter(value);
              setPage(1);
            }}
            data-testid={`admin-notifications-filter-${value}`}
          >
            {label}
            {count !== undefined ? ` ${count}` : ""}
          </button>
        ))}
        <span className="fa-nop-pill fa-nop-pill--sel">Selezionati {selected.size}</span>
      </div>
      <div className="fa-nop-pickhead">
        <button type="button" className="fa-nop-linkbtn" onClick={togglePage} data-testid="admin-notifications-select-page">
          <Check on={pageAll} /> Seleziona questa pagina
        </button>
        {data ? (
          <button
            type="button"
            className="fa-nop-link"
            onClick={() => props.onSelectAll(data.total)}
            data-testid="admin-notifications-select-all"
          >
            Seleziona tutti i {data.total}
          </button>
        ) : null}
      </div>
      {loading ? <UiStatePanel state="loading" title="Caricamento utenti" message="Un attimo…" /> : null}
      {error ? <UiStatePanel state="error" title="Utenti non disponibili" message={error} /> : null}
      {!loading && !error ? (
        <ul className="fa-nop-users">
          {items.map((user) => {
            const on = selected.has(user.userId);
            return (
              <li key={user.userId}>
                <button
                  type="button"
                  className={on ? "fa-nop-user fa-nop-user--on" : "fa-nop-user"}
                  onClick={() => toggle(user)}
                  aria-pressed={on}
                  data-testid={`admin-notifications-user-${user.userId}`}
                >
                  <Check on={on} />
                  <span className="fa-nop-user__avatar" aria-hidden="true">
                    {user.displayName.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="fa-nop-user__who">
                    <strong>{user.displayName}</strong>
                    <small>{user.email}</small>
                  </span>
                  <span className="fa-nop-user__leagues">{user.leagues.map((l) => l.name).join(", ") || "—"}</span>
                  {user.pushEnabled ? <span className="fa-nop-chip fa-nop-chip--ok">Push attivo</span> : null}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
      <div className="fa-nop-pager">
        <span>
          {data && data.total > 0 ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, data.total)} di ${data.total}` : "Nessun utente"}
        </span>
        <span>
          <Button type="button" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            ‹
          </Button>{" "}
          <Button type="button" variant="secondary" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
            ›
          </Button>
        </span>
      </div>
      <footer className="fa-nop-pickfoot">
        <strong>{selected.size} selezionati</strong>
        <span>
          <Button type="button" variant="secondary" onClick={() => onChange(new Map())}>
            Svuota
          </Button>{" "}
          <Button type="button" onClick={props.onClose} data-testid="admin-notifications-picker-confirm">
            Conferma
          </Button>
        </span>
      </footer>
    </section>
  );
}

function ComposeTab() {
  const [kind, setKind] = useState<BroadcastKind>("avviso");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [deepLink, setDeepLink] = useState("/");
  const [category, setCategory] = useState<NotificationCategory>("sistema");
  const [push, setPush] = useState(true);
  const [email, setEmail] = useState(false);
  const [mode, setMode] = useState<AudienceMode>("users");
  const [selected, setSelected] = useState<Map<string, string>>(new Map());
  const [pickerOpen, setPickerOpen] = useState(false);
  const [allTotal, setAllTotal] = useState<number | null>(null);
  const [scheduled, setScheduled] = useState(false);
  const [scheduledAt, setScheduledAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const recipients = mode === "all" ? allTotal : selected.size;

  async function submit(toMeOnly: boolean) {
    const accessToken = token();
    if (!accessToken) return;
    if (!title.trim() || !body.trim()) {
      setError("Titolo e testo sono obbligatori.");
      return;
    }
    if (!toMeOnly && mode === "users" && selected.size === 0) {
      setError("Scegli almeno un destinatario.");
      return;
    }
    if (scheduled && !toMeOnly) {
      const when = new Date(scheduledAt);
      if (!scheduledAt || Number.isNaN(when.getTime()) || when.getTime() <= Date.now()) {
        setError("Scegli una data e un’ora nel futuro.");
        return;
      }
    }
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const result = await createBroadcast(accessToken, {
        kind: toMeOnly ? "test" : kind,
        title: title.trim(),
        body: body.trim(),
        category,
        deepLink,
        channels: { inApp: true, push, email },
        audience: toMeOnly
          ? { mode: "users", userIds: [loadStoredSession()?.user?.id ?? ""].filter(Boolean) }
          : mode === "all"
            ? { mode: "all" }
            : { mode: "users", userIds: [...selected.keys()] },
        scheduledAt: scheduled && !toMeOnly ? new Date(scheduledAt).toISOString() : null,
      });
      setDone(
        result.status === "scheduled"
          ? `Programmata per ${result.recipientCount} utenti.`
          : `Inviata a ${result.recipientCount} utenti (${result.pushCount} con push).`,
      );
    } catch (e) {
      setError(getApiErrorMessage(e, "Invio non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  const glyph = KIND_GLYPH[kind];
  return (
    <div className="fa-nop-cols">
      <div className="fa-nop-stack">
        <section className="fa-nop-card">
          <header className="fa-nop-card__head"><h3>1 · Tipo</h3></header>
          <div className="fa-nop-radios" role="radiogroup" aria-label="Tipo di notifica">
            {BROADCAST_KIND_OPTIONS.map((option) => (
              <RadioCard
                key={option.value}
                label={option.label}
                hint={option.description}
                checked={kind === option.value}
                onSelect={() => setKind(option.value)}
                testId={`admin-notifications-kind-${option.value}`}
              />
            ))}
          </div>
        </section>
        <section className="fa-nop-card">
          <header className="fa-nop-card__head"><h3>2 · Messaggio</h3></header>
          <Input label="Titolo" name="admin-notifications-title" value={title} onChange={(e) => setTitle(e.target.value)} data-testid="admin-notifications-title" />
          <label className="fa-field">
            <span className="fa-field__label">Testo</span>
            <textarea
              className="fa-nop-textarea"
              rows={4}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              data-testid="admin-notifications-body"
            />
          </label>
          <div className="fa-nop-row">
            <Select
              label="Al tocco apre"
              options={BROADCAST_DESTINATIONS.map((d) => ({ value: d.value, label: d.label }))}
              value={deepLink}
              onChange={(e) => setDeepLink(e.target.value)}
              data-testid="admin-notifications-destination"
            />
            <Select
              label="Categoria"
              options={BROADCAST_CATEGORY_OPTIONS.map((c) => ({ value: c.value, label: c.label }))}
              value={category}
              onChange={(e) => setCategory(e.target.value as NotificationCategory)}
              data-testid="admin-notifications-category"
            />
          </div>
          <div className="fa-nop-row fa-nop-row--switches">
            <Switch checked disabled onCheckedChange={() => undefined} statusLabel="Centro notifiche" ariaLabel="Centro notifiche" />
            <Switch checked={push} onCheckedChange={setPush} statusLabel="Push sul telefono" ariaLabel="Push sul telefono" testId="admin-notifications-push" />
            <Switch checked={email} onCheckedChange={setEmail} statusLabel="Email" ariaLabel="Email" testId="admin-notifications-email" />
          </div>
        </section>
        <section className="fa-nop-card">
          <header className="fa-nop-card__head"><h3>3 · Destinatari</h3></header>
          <div className="fa-nop-radios" role="radiogroup" aria-label="Destinatari">
            <RadioCard label="Tutti gli utenti" hint="Tutti gli iscritti" checked={mode === "all"} onSelect={() => { setMode("all"); setPickerOpen(false); }} testId="admin-notifications-audience-all" />
            <RadioCard label="Selezione manuale" hint="Scegli tu uno per uno" checked={mode === "users"} onSelect={() => setMode("users")} testId="admin-notifications-audience-users" />
          </div>
          {mode === "users" ? (
            <button type="button" className="fa-nop-selected" onClick={() => setPickerOpen(true)} data-testid="admin-notifications-open-picker">
              <strong>{selected.size === 1 ? "1 utente selezionato" : `${selected.size} utenti selezionati`}</strong>
              <span>Scegli utenti ›</span>
            </button>
          ) : null}
          {mode === "all" && allTotal !== null ? <p className="fa-nop-hint">Tutti i {allTotal} utenti.</p> : null}
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
          <header className="fa-nop-card__head"><h3>4 · Invio</h3></header>
          <div className="fa-nop-radios" role="radiogroup" aria-label="Quando inviare">
            <RadioCard label="Subito" hint="Parte appena confermi" checked={!scheduled} onSelect={() => setScheduled(false)} testId="admin-notifications-now" />
            <RadioCard label="Programma" hint="Scegli data e ora" checked={scheduled} onSelect={() => setScheduled(true)} testId="admin-notifications-schedule" />
          </div>
          {scheduled ? (
            <Input label="Data e ora" name="admin-notifications-when" type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} data-testid="admin-notifications-when" />
          ) : null}
          {error ? <UiStatePanel state="error" title="Invio non riuscito" message={error} testId="admin-notifications-error" /> : null}
          {done ? <p className="fa-nop-done" data-testid="admin-notifications-done">{done}</p> : null}
          <div className="fa-nop-row">
            <Button type="button" loading={busy} disabled={busy} onClick={() => void submit(false)} data-testid="admin-notifications-send">
              {recipients === null ? "Invia" : `Invia a ${recipients} utenti`}
            </Button>
            <Button type="button" variant="secondary" disabled={busy} onClick={() => void submit(true)} data-testid="admin-notifications-send-me">
              Invia a me come prova
            </Button>
          </div>
        </section>
      </div>
      <aside className="fa-nop-stack fa-nop-aside">
        <section className="fa-nop-card">
          <header className="fa-nop-card__head"><h3>Anteprima</h3><p>Così arriva sul telefono</p></header>
          <div className="fa-nop-push">
            <span className="fa-nop-glyph" aria-hidden="true">{glyph}</span>
            <div>
              <small>FantApperò · {BROADCAST_KIND_OPTIONS.find((o) => o.value === kind)?.label} · ora</small>
              <strong>{title || "Titolo della notifica"}</strong>
              <p>{body || "Il testo del messaggio comparirà qui."}</p>
            </div>
          </div>
        </section>
        <section className="fa-nop-card">
          <header className="fa-nop-card__head"><h3>Riepilogo</h3></header>
          <dl className="fa-nop-sum">
            <div><dt>Tipo</dt><dd>{BROADCAST_KIND_OPTIONS.find((o) => o.value === kind)?.label}</dd></div>
            <div><dt>Destinatari</dt><dd>{recipients === null ? "—" : `${recipients} utenti`}</dd></div>
            <div><dt>Canali</dt><dd>{["App", push ? "push" : null, email ? "email" : null].filter(Boolean).join(" + ")}</dd></div>
            <div><dt>Invio</dt><dd>{scheduled ? "Programmato" : "Subito"}</dd></div>
          </dl>
        </section>
      </aside>
    </div>
  );
}

function TestTab() {
  const [samples, setSamples] = useState<TestSampleItem[]>([]);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toOthers, setToOthers] = useState(false);
  const [users, setUsers] = useState<Map<string, string>>(new Map());
  const [pickerOpen, setPickerOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    const accessToken = token();
    if (!accessToken) return;
    fetchTestSamples(accessToken)
      .then((r) => {
        setSamples(r.items);
        setChosen(new Set(r.items.map((s) => s.key)));
      })
      .catch((e) => setError(getApiErrorMessage(e, "Impossibile caricare le notifiche di prova.")))
      .finally(() => setLoading(false));
  }, []);

  async function send() {
    const accessToken = token();
    if (!accessToken) return;
    if (toOthers && users.size === 0) {
      setError("Scegli almeno un utente.");
      return;
    }
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const r = await sendTestSamples(accessToken, {
        sampleKeys: [...chosen],
        userIds: toOthers ? [...users.keys()] : undefined,
      });
      setDone(`${r.markedCount} notifiche di prova create.`);
    } catch (e) {
      setError(getApiErrorMessage(e, "Invio non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fa-nop-cols">
      <section className="fa-nop-card">
        <header className="fa-nop-card__head">
          <h3>Notifiche di prova</h3>
          <p>Una per ogni tipo reale, con dati di esempio.</p>
        </header>
        {loading ? <UiStatePanel state="loading" title="Caricamento" message="Un attimo…" /> : null}
        <div className="fa-nop-samples">
          {samples.map((sample) => {
            const on = chosen.has(sample.key);
            return (
              <button
                key={sample.key}
                type="button"
                className={on ? "fa-nop-user fa-nop-user--on" : "fa-nop-user"}
                aria-pressed={on}
                onClick={() => {
                  const next = new Set(chosen);
                  if (on) next.delete(sample.key);
                  else next.add(sample.key);
                  setChosen(next);
                }}
                data-testid={`admin-notifications-sample-${sample.key}`}
              >
                <Check on={on} />
                <span className="fa-nop-user__who">
                  <strong>{sample.title}</strong>
                  <small>{sample.body}</small>
                </span>
              </button>
            );
          })}
        </div>
      </section>
      <div className="fa-nop-stack">
        <section className="fa-nop-card">
          <header className="fa-nop-card__head"><h3>Invio</h3></header>
          <div className="fa-nop-radios" role="radiogroup" aria-label="Destinatario">
            <RadioCard label="A me" hint="Solo il mio account" checked={!toOthers} onSelect={() => setToOthers(false)} testId="admin-notifications-test-me" />
            <RadioCard label="A utenti scelti" hint="Scegli utenti di prova" checked={toOthers} onSelect={() => setToOthers(true)} testId="admin-notifications-test-others" />
          </div>
          {toOthers ? (
            <button type="button" className="fa-nop-selected" onClick={() => setPickerOpen(true)}>
              <strong>{users.size} utenti selezionati</strong>
              <span>Scegli utenti ›</span>
            </button>
          ) : null}
          {error ? <UiStatePanel state="error" title="Invio non riuscito" message={error} /> : null}
          {done ? <p className="fa-nop-done" data-testid="admin-notifications-test-done">{done}</p> : null}
          <Button type="button" loading={busy} disabled={busy || chosen.size === 0} onClick={() => void send()} data-testid="admin-notifications-test-send">
            {`Invia ${chosen.size} notifiche di prova`}
          </Button>
          <p className="fa-nop-hint">Le notifiche di prova sono segnate come “Test” e non contano nelle statistiche.</p>
        </section>
        {pickerOpen ? (
          <RecipientPicker selected={users} onChange={setUsers} onSelectAll={() => undefined} onClose={() => setPickerOpen(false)} />
        ) : null}
      </div>
    </div>
  );
}

function HistoryTab() {
  const [items, setItems] = useState<BroadcastItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const accessToken = token();
    if (!accessToken) return;
    try {
      setItems((await fetchBroadcasts(accessToken)).items);
    } catch (e) {
      setError(getApiErrorMessage(e, "Impossibile caricare lo storico."));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const sent = items.filter((i) => i.status === "sent");
  const delivered = sent.reduce((a, i) => a + i.deliveredCount, 0);
  const read = sent.reduce((a, i) => a + i.readCount, 0);
  const statusLabel: Record<BroadcastItem["status"], string> = { sent: "Inviato", scheduled: "Programmato", test: "Test" };

  return (
    <div className="fa-nop-stack" data-testid="admin-notifications-history">
      {loading ? <UiStatePanel state="loading" title="Caricamento storico" message="Un attimo…" /> : null}
      {error ? <UiStatePanel state="error" title="Storico non disponibile" message={error} /> : null}
      {!loading && !error ? (
        <>
          <ul className="fa-jobs__tiles" aria-label="Riepilogo">
            <li><span>Inviate</span><strong>{sent.length}</strong><small>in elenco</small></li>
            <li><span>Lette</span><strong>{delivered > 0 ? `${Math.round((read / delivered) * 100)}%` : "—"}</strong><small>media</small></li>
          </ul>
          {items.length === 0 ? (
            <UiStatePanel state="empty" title="Nessuna comunicazione" message="Le notifiche inviate compariranno qui." />
          ) : (
            <ul className="fa-nop-history">
              {items.map((item) => (
                <li key={item.id} className="fa-nop-hist" data-testid={`admin-notifications-hist-${item.id}`}>
                  <span className="fa-nop-glyph" aria-hidden="true">{KIND_GLYPH[item.kind]}</span>
                  <div className="fa-nop-hist__main">
                    <strong>{item.title}</strong>
                    <small>{item.audienceLabel} · {formatWhen(item)}</small>
                  </div>
                  <span className="fa-nop-hist__nums">Consegnate {item.deliveredCount}/{item.recipientCount} · Lette {item.readCount}/{item.recipientCount}</span>
                  <span className={`fa-nop-chip fa-nop-chip--${item.status}`}>{statusLabel[item.status]}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </div>
  );
}

export function AdminNotificationsPage() {
  const [tab, setTab] = useState<Tab>("nuova");
  const tabs: Array<[Tab, string]> = [["nuova", "Nuova"], ["test", "Test"], ["storico", "Storico"]];
  return (
    <PageContainer
      title="Notifiche"
      header={<Breadcrumb items={[{ label: "Operazioni", href: "/admin" }, { label: "Notifiche" }]} />}
    >
      <div className="fa-nop" data-testid="admin-notifications">
        <p className="fa-jobs__intro">
          Invia comunicazioni agli utenti della piattaforma: avvisi, novità, manutenzioni e notifiche di prova.
        </p>
        <div className="fa-nop-filters" role="tablist" aria-label="Sezioni notifiche">
          {tabs.map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              className={tab === value ? "fa-nop-pill fa-nop-pill--on fa-nop-pill--big" : "fa-nop-pill fa-nop-pill--big"}
              onClick={() => setTab(value)}
              data-testid={`admin-notifications-tab-${value}`}
            >
              {label}
            </button>
          ))}
        </div>
        {tab === "nuova" ? <ComposeTab /> : null}
        {tab === "test" ? <TestTab /> : null}
        {tab === "storico" ? <HistoryTab /> : null}
      </div>
    </PageContainer>
  );
}
