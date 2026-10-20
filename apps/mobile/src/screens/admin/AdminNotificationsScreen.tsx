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
import { theme } from "@fantappero/ui/theme";
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, View } from "react-native";
import {
  createBroadcast,
  fetchBroadcasts,
  fetchNotificationRecipients,
  fetchTestSamples,
  sendTestSamples,
} from "../../api/notifications";
import { adminUiStyles as base } from "../../admin/adminUiStyles";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { DateTimeField, parseDateTimeValue } from "../../components/DateTimeField";
import { HScroll } from "../../components/HScroll";
import { UiStatePanel } from "../../components/UiStatePanel";
import { PageContainer } from "../../layout/PageContainer";
import { lazyStyles } from "../../theme/lazyStyles";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";

type Tab = "nuova" | "test" | "storico";
type RecipientFilter = "all" | "push" | "noPush" | "operators";

const PAGE_SIZE = 10;
const KIND_GLYPH: Record<BroadcastKind, string> = { test: "🧪", avviso: "📣", novita: "✨", manutenzione: "🛠" };
const { colors, spacing, radius } = theme;

function Pill({ label, on, onPress, testID }: { label: string; on: boolean; onPress: () => void; testID?: string }) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.pill, on && styles.pillOn]}
      accessibilityState={{ selected: on }}
      testID={testID}
    >
      <Text style={[styles.pillLabel, on && styles.pillLabelOn]}>{label}</Text>
    </Pressable>
  );
}

function RadioCard({ label, hint, on, onPress, testID }: { label: string; hint: string; on: boolean; onPress: () => void; testID?: string }) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.radio, on && styles.radioOn]}
      accessibilityRole="radio"
      accessibilityState={{ selected: on }}
      testID={testID}
    >
      <View style={[styles.radioDot, on && styles.radioDotOn]}>{on ? <View style={styles.radioDotInner} /> : null}</View>
      <View style={styles.flex}>
        <Text style={styles.radioLabel}>{label}</Text>
        <Text style={styles.hint}>{hint}</Text>
      </View>
    </Pressable>
  );
}

function Check({ on }: { on: boolean }) {
  return (
    <View style={[styles.check, on && styles.checkOn]}>
      {on ? <Text style={styles.checkMark}>✓</Text> : null}
    </View>
  );
}

function RecipientPicker({
  selected,
  onChange,
  onSelectAll,
  onClose,
  accessToken,
}: {
  selected: Map<string, string>;
  onChange: (next: Map<string, string>) => void;
  onSelectAll: (total: number) => void;
  onClose: () => void;
  accessToken: string;
}) {
  const [data, setData] = useState<NotificationRecipientList | null>(null);
  const [filter, setFilter] = useState<RecipientFilter>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
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
  }, [accessToken, filter, search, page]);

  const items: NotificationRecipient[] = data?.items ?? [];
  const pageAll = items.length > 0 && items.every((u) => selected.has(u.userId));
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const counts = data?.counts;

  function toggle(user: NotificationRecipient) {
    const next = new Map(selected);
    if (next.has(user.userId)) next.delete(user.userId);
    else next.set(user.userId, user.displayName);
    onChange(next);
  }
  function togglePage() {
    const next = new Map(selected);
    for (const u of items) {
      if (pageAll) next.delete(u.userId);
      else next.set(u.userId, u.displayName);
    }
    onChange(next);
  }

  const filters: Array<[RecipientFilter, string, number | undefined]> = [
    ["all", "Tutti", counts?.all],
    ["push", "Con push", counts?.push],
    ["noPush", "Senza push", counts?.noPush],
    ["operators", "Operatori", counts?.operators],
  ];

  return (
    <View style={styles.card} testID="admin-notifications-picker">
      <Text style={styles.cardTitle}>Scegli utenti</Text>
      <Text style={styles.hint}>Cerca, filtra e spunta. La selezione resta anche cambiando pagina.</Text>
      <TextInput
        style={base.input}
        placeholder="Cerca per nome o email…"
        value={search}
        onChangeText={(value) => {
          setSearch(value);
          setPage(1);
        }}
        testID="admin-notifications-search"
      />
      <HScroll testID="admin-notifications-filters">
        {filters.map(([value, label, count]) => (
          <Pill
            key={value}
            label={`${label}${count !== undefined ? ` ${count}` : ""}`}
            on={filter === value}
            onPress={() => {
              setFilter(value);
              setPage(1);
            }}
            testID={`admin-notifications-filter-${value}`}
          />
        ))}
        <View style={[styles.pill, styles.pillSel]}>
          <Text style={styles.pillSelLabel}>{`Selezionati ${selected.size}`}</Text>
        </View>
      </HScroll>
      <View style={styles.between}>
        <Pressable style={styles.inline} onPress={togglePage} testID="admin-notifications-select-page">
          <Check on={pageAll} />
          <Text style={styles.strong}>Seleziona pagina</Text>
        </Pressable>
        {data ? (
          <Pressable onPress={() => onSelectAll(data.total)} testID="admin-notifications-select-all">
            <Text style={styles.link}>{`Tutti i ${data.total}`}</Text>
          </Pressable>
        ) : null}
      </View>
      {loading ? <UiStatePanel state="loading" title="Caricamento utenti" message="Un attimo…" /> : null}
      {error ? <UiStatePanel state="error" title="Utenti non disponibili" message={error} /> : null}
      {!loading && !error
        ? items.map((user) => {
            const on = selected.has(user.userId);
            return (
              <Pressable
                key={user.userId}
                onPress={() => toggle(user)}
                style={[styles.userRow, on && styles.userRowOn]}
                accessibilityState={{ selected: on }}
                testID={`admin-notifications-user-${user.userId}`}
              >
                <Check on={on} />
                <View style={styles.avatar}>
                  <Text style={styles.avatarLabel}>{user.displayName.slice(0, 1).toUpperCase()}</Text>
                </View>
                <View style={styles.flex}>
                  <Text style={styles.strong} numberOfLines={1}>{user.displayName}</Text>
                  <Text style={styles.hint} numberOfLines={1}>
                    {user.leagues.map((l) => l.name).join(", ") || user.email}
                  </Text>
                </View>
                {user.pushEnabled ? <Text style={styles.chipOk}>Push</Text> : null}
              </Pressable>
            );
          })
        : null}
      <View style={styles.between}>
        <Text style={styles.hint}>
          {data && data.total > 0
            ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, data.total)} di ${data.total}`
            : "Nessun utente"}
        </Text>
        <View style={styles.inline}>
          <Pressable style={[base.secondaryButton, page <= 1 && base.disabled]} disabled={page <= 1} onPress={() => setPage(page - 1)}>
            <Text style={base.secondaryButtonLabel}>‹</Text>
          </Pressable>
          <Pressable style={[base.secondaryButton, page >= totalPages && base.disabled]} disabled={page >= totalPages} onPress={() => setPage(page + 1)}>
            <Text style={base.secondaryButtonLabel}>›</Text>
          </Pressable>
        </View>
      </View>
      <View style={styles.footer}>
        <Text style={styles.strong}>{`${selected.size} selezionati`}</Text>
        <View style={styles.inline}>
          <Pressable style={base.secondaryButton} onPress={() => onChange(new Map())}>
            <Text style={base.secondaryButtonLabel}>Svuota</Text>
          </Pressable>
          <Pressable style={base.button} onPress={onClose} testID="admin-notifications-picker-confirm">
            <Text style={base.buttonLabel}>Conferma</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

function ComposeTab({ accessToken, myId }: { accessToken: string; myId: string | null }) {
  const [kind, setKind] = useState<BroadcastKind>("avviso");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [deepLink, setDeepLink] = useState("/");
  const [category, setCategory] = useState<NotificationCategory>("sistema");
  const [push, setPush] = useState(true);
  const [email, setEmail] = useState(false);
  const [mode, setMode] = useState<"all" | "users">("users");
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
    if (!title.trim() || !body.trim()) {
      setError("Titolo e testo sono obbligatori.");
      return;
    }
    if (toMeOnly && !myId) {
      setError("Utente non riconosciuto.");
      return;
    }
    if (!toMeOnly && mode === "users" && selected.size === 0) {
      setError("Scegli almeno un destinatario.");
      return;
    }
    let when: Date | null = null;
    if (scheduled && !toMeOnly) {
      when = parseDateTimeValue(scheduledAt);
      if (!when || when.getTime() <= Date.now()) {
        setError("Scegli una data e un'ora nel futuro.");
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
          ? { mode: "users", userIds: [myId as string] }
          : mode === "all"
            ? { mode: "all" }
            : { mode: "users", userIds: [...selected.keys()] },
        scheduledAt: when ? when.toISOString() : null,
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

  return (
    <View style={styles.stack}>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>1 · Tipo</Text>
        <View style={styles.radios}>
          {BROADCAST_KIND_OPTIONS.map((o) => (
            <RadioCard key={o.value} label={o.label} hint={o.description} on={kind === o.value} onPress={() => setKind(o.value)} testID={`admin-notifications-kind-${o.value}`} />
          ))}
        </View>
      </View>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>2 · Messaggio</Text>
        <Text style={styles.label}>Titolo</Text>
        <TextInput style={base.input} value={title} onChangeText={setTitle} testID="admin-notifications-title" />
        <Text style={styles.label}>Testo</Text>
        <TextInput style={[base.input, styles.textarea]} value={body} onChangeText={setBody} multiline testID="admin-notifications-body" />
        <Text style={styles.label}>Al tocco apre</Text>
        <HScroll testID="admin-notifications-destination">
          {BROADCAST_DESTINATIONS.map((d) => (
            <Pill key={d.value} label={d.label} on={deepLink === d.value} onPress={() => setDeepLink(d.value)} />
          ))}
        </HScroll>
        <Text style={styles.label}>Categoria</Text>
        <HScroll testID="admin-notifications-category">
          {BROADCAST_CATEGORY_OPTIONS.map((c) => (
            <Pill key={c.value} label={c.label} on={category === c.value} onPress={() => setCategory(c.value)} />
          ))}
        </HScroll>
        <View style={styles.between}>
          <Text style={styles.strong}>Push sul telefono</Text>
          <Switch value={push} onValueChange={setPush} trackColor={{ true: colors.brand, false: colors.border }} thumbColor="#ffffff" testID="admin-notifications-push" />
        </View>
        <View style={styles.between}>
          <Text style={styles.strong}>Email</Text>
          <Switch value={email} onValueChange={setEmail} trackColor={{ true: colors.brand, false: colors.border }} thumbColor="#ffffff" testID="admin-notifications-email" />
        </View>
      </View>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>3 · Destinatari</Text>
        <View style={styles.radios}>
          <RadioCard label="Tutti gli utenti" hint="Tutti gli iscritti" on={mode === "all"} onPress={() => { setMode("all"); setPickerOpen(false); }} testID="admin-notifications-audience-all" />
          <RadioCard label="Selezione manuale" hint="Scegli tu uno per uno" on={mode === "users"} onPress={() => setMode("users")} testID="admin-notifications-audience-users" />
        </View>
        {mode === "users" ? (
          <Pressable style={styles.selected} onPress={() => setPickerOpen(true)} testID="admin-notifications-open-picker">
            <Text style={styles.strong}>{selected.size === 1 ? "1 utente selezionato" : `${selected.size} utenti selezionati`}</Text>
            <Text style={styles.link}>Scegli utenti ›</Text>
          </Pressable>
        ) : allTotal !== null ? (
          <Text style={styles.hint}>{`Tutti i ${allTotal} utenti.`}</Text>
        ) : null}
      </View>
      {pickerOpen && mode === "users" ? (
        <RecipientPicker
          accessToken={accessToken}
          selected={selected}
          onChange={setSelected}
          onSelectAll={(total) => { setMode("all"); setAllTotal(total); setPickerOpen(false); }}
          onClose={() => setPickerOpen(false)}
        />
      ) : null}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>4 · Invio</Text>
        <View style={styles.radios}>
          <RadioCard label="Subito" hint="Parte appena confermi" on={!scheduled} onPress={() => setScheduled(false)} testID="admin-notifications-now" />
          <RadioCard label="Programma" hint="Scegli data e ora dal calendario" on={scheduled} onPress={() => setScheduled(true)} testID="admin-notifications-schedule" />
        </View>
        {scheduled ? <DateTimeField label="Data e ora" value={scheduledAt} onChange={setScheduledAt} testID="admin-notifications-when" /> : null}
        {error ? <Text style={styles.error} testID="admin-notifications-error">{error}</Text> : null}
        {done ? <Text style={styles.done} testID="admin-notifications-done">{done}</Text> : null}
        <Pressable style={[base.button, busy && base.disabled]} disabled={busy} onPress={() => void submit(false)} testID="admin-notifications-send">
          <Text style={base.buttonLabel}>{recipients === null ? "Invia" : `Invia a ${recipients} utenti`}</Text>
        </Pressable>
        <Pressable style={[base.secondaryButton, busy && base.disabled]} disabled={busy} onPress={() => void submit(true)} testID="admin-notifications-send-me">
          <Text style={base.secondaryButtonLabel}>Invia a me come prova</Text>
        </Pressable>
      </View>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Anteprima</Text>
        <View style={styles.push}>
          <View style={styles.glyph}><Text style={styles.glyphLabel}>{KIND_GLYPH[kind]}</Text></View>
          <View style={styles.flex}>
            <Text style={styles.hint}>{`FantApperò · ${BROADCAST_KIND_OPTIONS.find((o) => o.value === kind)?.label} · ora`}</Text>
            <Text style={styles.strong}>{title || "Titolo della notifica"}</Text>
            <Text style={styles.hint}>{body || "Il testo del messaggio comparirà qui."}</Text>
          </View>
        </View>
      </View>
    </View>
  );
}

function TestTab({ accessToken }: { accessToken: string }) {
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
    fetchTestSamples(accessToken)
      .then((r) => {
        setSamples(r.items);
        setChosen(new Set(r.items.map((s) => s.key)));
      })
      .catch((e) => setError(getApiErrorMessage(e, "Impossibile caricare le notifiche di prova.")))
      .finally(() => setLoading(false));
  }, [accessToken]);

  async function send() {
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
    <View style={styles.stack}>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Notifiche di prova</Text>
        <Text style={styles.hint}>Una per ogni tipo reale, con dati di esempio.</Text>
        {loading ? <UiStatePanel state="loading" title="Caricamento" message="Un attimo…" /> : null}
        {samples.map((sample) => {
          const on = chosen.has(sample.key);
          return (
            <Pressable
              key={sample.key}
              style={[styles.userRow, on && styles.userRowOn]}
              onPress={() => {
                const next = new Set(chosen);
                if (on) next.delete(sample.key);
                else next.add(sample.key);
                setChosen(next);
              }}
              accessibilityState={{ selected: on }}
              testID={`admin-notifications-sample-${sample.key}`}
            >
              <Check on={on} />
              <View style={styles.flex}>
                <Text style={styles.strong}>{sample.title}</Text>
                <Text style={styles.hint} numberOfLines={1}>{sample.body}</Text>
              </View>
            </Pressable>
          );
        })}
      </View>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Invio</Text>
        <View style={styles.radios}>
          <RadioCard label="A me" hint="Solo il mio account" on={!toOthers} onPress={() => setToOthers(false)} testID="admin-notifications-test-me" />
          <RadioCard label="A utenti scelti" hint="Scegli utenti di prova" on={toOthers} onPress={() => setToOthers(true)} testID="admin-notifications-test-others" />
        </View>
        {toOthers ? (
          <Pressable style={styles.selected} onPress={() => setPickerOpen(true)}>
            <Text style={styles.strong}>{`${users.size} utenti selezionati`}</Text>
            <Text style={styles.link}>Scegli utenti ›</Text>
          </Pressable>
        ) : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {done ? <Text style={styles.done} testID="admin-notifications-test-done">{done}</Text> : null}
        <Pressable style={[base.button, (busy || chosen.size === 0) && base.disabled]} disabled={busy || chosen.size === 0} onPress={() => void send()} testID="admin-notifications-test-send">
          <Text style={base.buttonLabel}>{`Invia ${chosen.size} notifiche di prova`}</Text>
        </Pressable>
        <Text style={styles.hint}>Sono segnate come “Test” e non contano nelle statistiche.</Text>
      </View>
      {pickerOpen ? (
        <RecipientPicker accessToken={accessToken} selected={users} onChange={setUsers} onSelectAll={() => undefined} onClose={() => setPickerOpen(false)} />
      ) : null}
    </View>
  );
}

function formatWhen(item: BroadcastItem): string {
  const value = item.status === "scheduled" ? item.scheduledAt : item.sentAt;
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("it-IT", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Rome" }).format(new Date(value));
  } catch {
    return value;
  }
}

function HistoryTab({ accessToken }: { accessToken: string }) {
  const [items, setItems] = useState<BroadcastItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems((await fetchBroadcasts(accessToken)).items);
    } catch (e) {
      setError(getApiErrorMessage(e, "Impossibile caricare lo storico."));
    } finally {
      setLoading(false);
    }
  }, [accessToken]);
  useEffect(() => {
    void load();
  }, [load]);

  const statusLabel: Record<BroadcastItem["status"], string> = { sent: "Inviato", scheduled: "Programmato", test: "Test" };
  return (
    <View style={styles.stack} testID="admin-notifications-history">
      {loading ? <UiStatePanel state="loading" title="Caricamento storico" message="Un attimo…" /> : null}
      {error ? <UiStatePanel state="error" title="Storico non disponibile" message={error} /> : null}
      {!loading && !error && items.length === 0 ? (
        <UiStatePanel state="empty" title="Nessuna comunicazione" message="Le notifiche inviate compariranno qui." />
      ) : null}
      {items.map((item) => (
        <View key={item.id} style={styles.card} testID={`admin-notifications-hist-${item.id}`}>
          <View style={styles.push}>
            <View style={styles.glyph}><Text style={styles.glyphLabel}>{KIND_GLYPH[item.kind]}</Text></View>
            <View style={styles.flex}>
              <Text style={styles.strong}>{item.title}</Text>
              <Text style={styles.hint}>{`${item.audienceLabel} · ${formatWhen(item)}`}</Text>
              <View style={styles.chipsRow}>
                <Text style={item.status === "scheduled" ? styles.chipWarn : item.status === "sent" ? styles.chipOk : styles.chip}>{statusLabel[item.status]}</Text>
                <Text style={styles.chip}>{`Consegnate ${item.deliveredCount}/${item.recipientCount}`}</Text>
                <Text style={styles.chip}>{`Lette ${item.readCount}/${item.recipientCount}`}</Text>
              </View>
            </View>
          </View>
        </View>
      ))}
    </View>
  );
}

export function AdminNotificationsScreen() {
  const { accessToken, user } = useAuthSession();
  const [tab, setTab] = useState<Tab>("nuova");
  const tabs: Array<[Tab, string]> = [["nuova", "Nuova"], ["test", "Test"], ["storico", "Storico"]];
  return (
    <PageContainer title="Notifiche" testID="admin-notifications">
      <View style={styles.stack}>
        <Text style={base.meta}>Invia avvisi, novità, manutenzioni e notifiche di prova agli utenti.</Text>
        <HScroll testID="admin-notifications-tabs">
          {tabs.map(([value, label]) => (
            <Pill key={value} label={label} on={tab === value} onPress={() => setTab(value)} testID={`admin-notifications-tab-${value}`} />
          ))}
        </HScroll>
        {!accessToken ? (
          <UiStatePanel state="error" title="Sessione assente" message="Accedi come operatore." />
        ) : tab === "nuova" ? (
          <ComposeTab accessToken={accessToken} myId={user?.id ?? null} />
        ) : tab === "test" ? (
          <TestTab accessToken={accessToken} />
        ) : (
          <HistoryTab accessToken={accessToken} />
        )}
      </View>
    </PageContainer>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  stack: { gap: spacing.md },
  flex: { flex: 1, minWidth: 0 },
  card: { gap: spacing.sm, padding: spacing.md, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.backgroundElevated },
  cardTitle: { color: colors.foreground, fontSize: 20, fontWeight: "800", fontStyle: "italic", textTransform: "uppercase" },
  label: { color: colors.foregroundMuted, fontSize: 11, letterSpacing: 1.4, textTransform: "uppercase" },
  hint: { color: colors.foregroundMuted, fontSize: 13 },
  strong: { color: colors.foreground, fontWeight: "700" },
  link: { color: colors.brand, fontWeight: "600" },
  textarea: { minHeight: 92, textAlignVertical: "top" },
  radios: { gap: spacing.sm },
  radio: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start", padding: spacing.md, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.border },
  radioOn: { borderColor: colors.brand, borderWidth: 1.5 },
  radioLabel: { color: colors.foreground, fontWeight: "700" },
  radioDot: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: colors.border, alignItems: "center", justifyContent: "center", marginTop: 2 },
  radioDotOn: { borderColor: colors.brand },
  radioDotInner: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.brand },
  pill: { paddingHorizontal: spacing.md, paddingVertical: spacing.sm, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border },
  pillOn: { backgroundColor: colors.brand, borderColor: colors.brand },
  pillLabel: { color: colors.foreground, fontWeight: "600" },
  pillLabelOn: { color: colors.onBrand },
  pillSel: { backgroundColor: colors.backgroundElevated },
  pillSelLabel: { color: colors.brand, fontWeight: "600" },
  between: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  inline: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  selected: { flexDirection: "row", justifyContent: "space-between", padding: spacing.md, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.brand },
  check: { width: 22, height: 22, borderRadius: 7, borderWidth: 1.5, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  checkOn: { backgroundColor: colors.brand, borderColor: colors.brand },
  checkMark: { color: colors.onBrand, fontWeight: "800", fontSize: 13 },
  userRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.sm, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.border },
  userRowOn: { borderColor: colors.brand },
  avatar: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.brand, alignItems: "center", justifyContent: "center" },
  avatarLabel: { color: colors.onBrand, fontWeight: "800" },
  footer: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm, padding: spacing.md, borderRadius: radius.xl, borderWidth: 1, borderColor: colors.brand },
  push: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" },
  glyph: { width: 40, height: 40, borderRadius: 13, alignItems: "center", justifyContent: "center", backgroundColor: colors.backgroundElevated },
  glyphLabel: { fontSize: 20 },
  chipsRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 6 },
  chip: { color: colors.foregroundMuted, fontSize: 12, fontWeight: "600", paddingHorizontal: 10, paddingVertical: 3, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border, overflow: "hidden" },
  chipOk: { color: "#6EE7B7", fontSize: 12, fontWeight: "600", paddingHorizontal: 10, paddingVertical: 3, borderRadius: radius.pill, borderWidth: 1, borderColor: "#6EE7B7", overflow: "hidden" },
  chipWarn: { color: "#FFD23F", fontSize: 12, fontWeight: "600", paddingHorizontal: 10, paddingVertical: 3, borderRadius: radius.pill, borderWidth: 1, borderColor: "#FFD23F", overflow: "hidden" },
  error: { color: "#FF8FA8" },
  done: { color: "#6EE7B7", fontWeight: "600" },
}));
