import type { OperatorEmailHistoryItem } from "@fantappero/contracts";
import { useCallback, useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { fetchOperatorEmails, sendOperatorEmail } from "../../api/notifications";
import { adminUiStyles as base } from "../../admin/adminUiStyles";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { HScroll } from "../../components/HScroll";
import { UiStatePanel } from "../../components/UiStatePanel";
import { PageContainer } from "../../layout/PageContainer";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";
import {
  adminNotificationStyles as styles,
  Pill,
  RadioCard,
  RecipientPicker,
} from "./AdminNotificationsScreen";

function formatSent(value: string): string {
  try {
    return new Intl.DateTimeFormat("it-IT", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Rome" }).format(new Date(value));
  } catch {
    return value;
  }
}

function ComposeTab({ accessToken, myId }: { accessToken: string; myId: string | null }) {
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
    if (!subject.trim() || !body.trim()) {
      setError("Oggetto e testo sono obbligatori.");
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
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const result = await sendOperatorEmail(accessToken, {
        subject: subject.trim(),
        body: body.trim(),
        audience: toMeOnly
          ? { mode: "users", userIds: [myId as string] }
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
    <View style={styles.stack}>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>1 · Destinatari</Text>
        <View style={styles.radios}>
          <RadioCard label="Tutti gli utenti" hint="Tutti gli iscritti" on={mode === "all"} onPress={() => { setMode("all"); setPickerOpen(false); }} testID="admin-email-audience-all" />
          <RadioCard label="Selezione manuale" hint="Scegli tu uno per uno" on={mode === "users"} onPress={() => setMode("users")} testID="admin-email-audience-users" />
        </View>
        {mode === "users" ? (
          <Pressable style={styles.selected} onPress={() => setPickerOpen(true)} testID="admin-email-open-picker">
            <Text style={styles.strong}>{selected.size === 1 ? "1 utente selezionato" : `${selected.size} utenti selezionati`}</Text>
            <Text style={styles.link}>Scegli utenti ›</Text>
          </Pressable>
        ) : null}
        <Text style={styles.hint}>Chi ha disattivato le email non riceve il messaggio.</Text>
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
        <Text style={styles.cardTitle}>2 · Messaggio</Text>
        <Text style={styles.label}>Oggetto</Text>
        <TextInput style={base.input} value={subject} onChangeText={setSubject} maxLength={120} testID="admin-email-subject" />
        <Text style={styles.label}>Testo</Text>
        <TextInput style={[base.input, styles.textarea]} value={body} onChangeText={setBody} multiline maxLength={5000} testID="admin-email-body" />
      </View>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>3 · Invio</Text>
        {error ? <Text style={styles.error} testID="admin-email-error">{error}</Text> : null}
        {done ? <Text style={styles.done} testID="admin-email-done">{done}</Text> : null}
        <Pressable style={[base.button, busy && base.disabled]} disabled={busy} onPress={() => void submit(false)} testID="admin-email-send">
          <Text style={base.buttonLabel}>{recipients === null ? "Invia" : `Invia a ${recipients} utenti`}</Text>
        </Pressable>
        <Pressable style={[base.secondaryButton, busy && base.disabled]} disabled={busy} onPress={() => void submit(true)} testID="admin-email-send-me">
          <Text style={base.secondaryButtonLabel}>Invia a me come prova</Text>
        </Pressable>
        <Text style={styles.hint}>Le email automatiche (registrazione, verifica, reset password) partono da sole e non passano di qui.</Text>
      </View>
    </View>
  );
}

function HistoryTab({ accessToken }: { accessToken: string }) {
  const [items, setItems] = useState<OperatorEmailHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      setItems((await fetchOperatorEmails(accessToken)).items);
    } catch (e) {
      setError(getApiErrorMessage(e, "Impossibile caricare lo storico."));
    } finally {
      setLoading(false);
    }
  }, [accessToken]);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <View style={styles.stack} testID="admin-email-history">
      {loading ? <UiStatePanel state="loading" title="Caricamento storico" message="Un attimo…" /> : null}
      {error ? <UiStatePanel state="error" title="Storico non disponibile" message={error} /> : null}
      {!loading && !error && items.length === 0 ? (
        <UiStatePanel state="empty" title="Nessuna email inviata" message="Le email inviate dal portale compariranno qui." />
      ) : null}
      {items.map((item) => (
        <View key={item.id} style={styles.card}>
          <Text style={styles.strong}>{item.subject}</Text>
          <Text style={styles.hint}>{`${item.audienceLabel} · ${formatSent(item.sentAt)}`}</Text>
          <Text style={styles.hint}>{`${item.recipientCount} destinatari`}</Text>
        </View>
      ))}
    </View>
  );
}

export function AdminEmailScreen() {
  const { accessToken, user } = useAuthSession();
  const [tab, setTab] = useState<"nuova" | "storico">("nuova");
  return (
    <PageContainer title="Email" testID="admin-email">
      <View style={styles.stack}>
        <Text style={base.meta}>Scrivi e invia email agli utenti: solo per segnalazioni e comunicazioni particolari.</Text>
        <HScroll testID="admin-email-tabs">
          <Pill label="Nuova" on={tab === "nuova"} onPress={() => setTab("nuova")} testID="admin-email-tab-nuova" />
          <Pill label="Storico" on={tab === "storico"} onPress={() => setTab("storico")} testID="admin-email-tab-storico" />
        </HScroll>
        {!accessToken ? (
          <UiStatePanel state="error" title="Sessione assente" message="Accedi come operatore." />
        ) : tab === "nuova" ? (
          <ComposeTab accessToken={accessToken} myId={user?.id ?? null} />
        ) : (
          <HistoryTab accessToken={accessToken} />
        )}
      </View>
    </PageContainer>
  );
}
