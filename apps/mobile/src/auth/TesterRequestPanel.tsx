import { lazyStyles } from "../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import Ionicons from "@expo/vector-icons/Ionicons";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { submitTesterRequest } from "../api/auth";
import { AppTextInput as TextInput } from "../components/AppTextInput";
import { UiStatePanel } from "../components/UiStatePanel";
import { getApiErrorMessage } from "../session/DemoSessionContext";
import { authFormStyles } from "./authFormStyles";
import {
  buildTesterRequestBody,
  formatTesterRequestDate,
  testerRequestPrefill,
  type TesterGateInfo,
} from "./testerGate";

const { colors, spacing, typography, radius } = theme;

const STEPS = [
  { title: "Invii la richiesta", detail: "Nome e cognome, telefono facoltativo" },
  { title: "La valutiamo", detail: "Ti avvisiamo noi" },
  { title: "Entri nel gruppo", detail: "Poi accedi con lo stesso account" },
] as const;

function TesterSteps({ current }: { current: number }) {
  return (
    <View style={styles.steps} accessibilityLabel="Come funziona">
      {STEPS.map((step, index) => {
        const done = index < current;
        const now = index === current;
        return (
          <View key={step.title} style={styles.step}>
            <View style={[styles.stepDot, done && styles.stepDotDone, now && styles.stepDotNow]}>
              <Text style={[styles.stepDotLabel, (done || now) && styles.stepDotLabelOn]}>{done ? "✓" : index + 1}</Text>
            </View>
            <View style={styles.stepText}>
              <Text style={styles.stepTitle}>{step.title}</Text>
              <Text style={styles.stepDetail}>{step.detail}</Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

/**
 * Pilota in modalità test: chi non è tra i tester non entra, ma può chiedere di partecipare.
 * Stessa richiesta del sito (`apps/web/src/pages/auth/TesterRequestPanel.tsx`), qui per chi
 * accede con email dall'app. Il telefono è facoltativo: serve solo per la chat WhatsApp.
 */
export function TesterRequestPanel({ info, onBack }: { info: TesterGateInfo; onBack: () => void }) {
  const prefill = testerRequestPrefill(info);
  const [firstName, setFirstName] = useState(prefill.firstName);
  const [lastName, setLastName] = useState(prefill.lastName);
  const [phone, setPhone] = useState("");
  const [motivation, setMotivation] = useState("");
  const [consent, setConsent] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const intro = (
    <>
      <Text style={styles.kick}>Fase pilota · accesso su richiesta</Text>
      <Text style={styles.title}>
        Il pilota è riservato ai <Text style={styles.titleAccent}>tester</Text>
      </Text>
    </>
  );

  if (sent || info.status === "pending") {
    const date = formatTesterRequestDate(info.submittedAt) || (sent ? formatTesterRequestDate(new Date().toISOString()) : "");
    return (
      <View style={styles.wrap} testID="tester-request-pending">
        {intro}
        <UiStatePanel
          state="success"
          title={sent ? "Richiesta inviata!" : "Richiesta in valutazione"}
          message={`${sent ? "Abbiamo ricevuto la tua richiesta." : `La tua richiesta${date ? ` del ${date}` : ""} è in valutazione.`} Quando verrà accolta potrai accedere con lo stesso account e ti aggiungeremo al gruppo WhatsApp dei tester. Non serve inviarla di nuovo.`}
        />
        <TesterSteps current={1} />
        {info.email ? <Text style={styles.note}>{info.email}</Text> : null}
        <BackButton onBack={onBack} />
      </View>
    );
  }

  if (info.status === "rejected") {
    return (
      <View style={styles.wrap} testID="tester-request-rejected">
        {intro}
        <UiStatePanel
          state="forbidden"
          title="Accesso non disponibile"
          message="La tua richiesta è già stata valutata e per ora non è stata accolta. Potrai riprovare più avanti."
        />
        <BackButton onBack={onBack} />
      </View>
    );
  }

  async function onSubmit() {
    const built = buildTesterRequestBody(info, { firstName, lastName, phone, motivation, consent });
    if (!built.ok) {
      setError(built.error);
      return;
    }
    setSending(true);
    setError(null);
    try {
      await submitTesterRequest(built.body);
      setSent(true);
    } catch (cause) {
      setError(getApiErrorMessage(cause, "Impossibile inviare la richiesta."));
    } finally {
      setSending(false);
    }
  }

  return (
    <View style={styles.wrap} testID="tester-request-form">
      {intro}
      <Text style={styles.lead}>
        Stiamo provando il gioco con un gruppo ristretto. Lasciaci i tuoi dati: valuteremo la richiesta e, se accolta,
        entri con lo stesso account.
      </Text>
      <TesterSteps current={0} />
      {info.email ? (
        <View style={authFormStyles.accountRow} testID="tester-request-account">
          <View style={authFormStyles.accountText}>
            <Text style={authFormStyles.accountCaption}>Account</Text>
            <Text style={authFormStyles.accountEmail} numberOfLines={1}>
              {info.email}
            </Text>
          </View>
          <Pressable accessibilityRole="button" accessibilityLabel="Cambia account" onPress={onBack}>
            <Text style={authFormStyles.link}>Cambia</Text>
          </Pressable>
        </View>
      ) : null}
      <View>
        <Text style={authFormStyles.label}>Nome</Text>
        <TextInput
          value={firstName}
          onChangeText={setFirstName}
          maxLength={80}
          autoComplete="given-name"
          style={authFormStyles.input}
          accessibilityLabel="Nome"
          testID="tester-request-first-name"
        />
      </View>
      <View>
        <Text style={authFormStyles.label}>Cognome</Text>
        <TextInput
          value={lastName}
          onChangeText={setLastName}
          maxLength={80}
          autoComplete="family-name"
          style={authFormStyles.input}
          accessibilityLabel="Cognome"
          testID="tester-request-last-name"
        />
      </View>
      <View>
        <Text style={authFormStyles.label}>Numero di telefono (facoltativo)</Text>
        <TextInput
          value={phone}
          onChangeText={setPhone}
          maxLength={30}
          keyboardType="phone-pad"
          autoComplete="tel"
          style={authFormStyles.input}
          accessibilityLabel="Numero di telefono, facoltativo"
          testID="tester-request-phone"
        />
        <Text style={styles.hint}>
          Chi lascia il numero viene inserito nella chat WhatsApp dei tester. Lo useremo solo per questo.
        </Text>
      </View>
      <View>
        <Text style={authFormStyles.label}>Perché vuoi partecipare? (facoltativo)</Text>
        <TextInput
          value={motivation}
          onChangeText={setMotivation}
          maxLength={1000}
          multiline
          textAlignVertical="top"
          style={[authFormStyles.input, styles.multiline]}
          accessibilityLabel="Perché vuoi partecipare, facoltativo"
          testID="tester-request-motivation"
        />
      </View>
      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked: consent }}
        onPress={() => setConsent((current) => !current)}
        style={styles.consent}
        testID="tester-request-consent"
      >
        <Ionicons name={consent ? "checkbox" : "square-outline"} size={24} color={consent ? colors.accent : colors.foregroundMuted} />
        <Text style={styles.consentText}>
          Acconsento al trattamento di questi dati per valutare la richiesta e, se ho lasciato il numero, per aggiungermi
          alla chat WhatsApp dei tester. Se la richiesta non viene accolta i dati si cancellano entro 30 giorni.
        </Text>
      </Pressable>
      {error ? (
        <UiStatePanel state="error" title="Richiesta non inviata" message={error} testID="tester-request-error" />
      ) : null}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Invia richiesta"
        accessibilityState={{ disabled: !consent || sending }}
        disabled={!consent || sending}
        onPress={() => void onSubmit()}
        style={[authFormStyles.primaryButton, (!consent || sending) && authFormStyles.disabled]}
        testID="tester-request-submit"
      >
        <Text style={authFormStyles.primaryLabel}>{sending ? "Invio…" : "Invia richiesta"}</Text>
      </Pressable>
      <BackButton onBack={onBack} label="Annulla" />
    </View>
  );
}

function BackButton({ onBack, label = "Torna all'accesso" }: { onBack: () => void; label?: string }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onBack}
      style={authFormStyles.centerLink}
      testID="tester-request-back"
    >
      <Text style={authFormStyles.linkUnderline}>{label}</Text>
    </Pressable>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  wrap: { gap: spacing.sm },
  kick: { color: colors.accentSecondary, fontSize: 12, fontWeight: "700", letterSpacing: 1, textTransform: "uppercase" },
  title: { color: colors.foreground, fontSize: 32, lineHeight: 36, fontWeight: "800", fontStyle: "italic", letterSpacing: -0.5 },
  titleAccent: { color: "#9DB4FF" },
  lead: { color: colors.foregroundMuted, fontSize: 15 },
  steps: { gap: spacing.sm, marginVertical: spacing.xs },
  step: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  stepDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  stepDotDone: { backgroundColor: colors.success, borderColor: colors.success },
  stepDotNow: { backgroundColor: colors.accent, borderColor: colors.accent },
  stepDotLabel: { color: colors.foregroundMuted, fontSize: 12, fontWeight: "800" },
  stepDotLabelOn: { color: "#FFFFFF" },
  stepText: { flex: 1, minWidth: 0 },
  stepTitle: { color: colors.foreground, fontWeight: typography.fontWeight.semibold, fontSize: typography.fontSize.sm },
  stepDetail: { color: colors.foregroundMuted, fontSize: 12 },
  note: { color: colors.foregroundMuted, fontSize: typography.fontSize.sm, textAlign: "center" },
  hint: { marginTop: spacing.xs, color: colors.foregroundMuted, fontSize: 12 },
  multiline: { minHeight: 96, paddingTop: spacing.sm + 4 },
  consent: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    marginTop: spacing.sm,
    padding: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  consentText: { flex: 1, color: colors.foregroundMuted, fontSize: 13, lineHeight: 18 },
}));
