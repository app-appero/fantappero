import type { LeagueListoneEntry, MarketLiveNominationMode } from "@fantappero/contracts";
import { Pressable, Text, View } from "react-native";
import { AthleteName } from "../../athletes/AthleteCard";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { OptionPicker, type OptionPickerOption } from "../../components/OptionPicker";
import { marketUiStyles as styles } from "../../market/marketUiStyles";
import {
  NOMINATION_MODE_HINT,
  NOMINATION_MODE_OPTIONS,
  NOMINATION_MODE_SHORT_LABEL,
} from "../../market/liveAuctionLabels";

const MODE_ICON: Record<MarketLiveNominationMode, string> = {
  manual: "☝",
  turn_based: "⟳",
  sequential: "☰",
  alphabetical_by_role: "A–Z",
  random: "⚄",
};

function Stepper({
  label,
  value,
  unit,
  step,
  min,
  max,
  onChange,
  testID,
}: {
  label: string;
  value: string;
  unit: string;
  step: number;
  min: number;
  max: number;
  onChange: (value: string) => void;
  testID: string;
}) {
  const current = Number(value) || min;
  const set = (next: number) => onChange(String(Math.min(max, Math.max(min, next))));
  return (
    <View style={{ gap: 6 }}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.stepper} testID={testID}>
        <Pressable style={styles.stepperBtn} onPress={() => set(current - step)} accessibilityLabel={`Diminuisci ${label}`}>
          <Text style={styles.stepperBtnLabel}>−</Text>
        </Pressable>
        <Text style={styles.stepperValue}>
          {current}
          <Text style={styles.meta}> {unit}</Text>
        </Text>
        <Pressable style={styles.stepperBtn} onPress={() => set(current + step)} accessibilityLabel={`Aumenta ${label}`}>
          <Text style={styles.stepperBtnLabel}>+</Text>
        </Pressable>
      </View>
    </View>
  );
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <View style={styles.heroCard}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {subtitle ? <Text style={styles.meta}>{subtitle}</Text> : null}
      {children}
    </View>
  );
}

/** Configurazione della sessione d'asta prima di entrare nel tavolo (admin). */
export function LiveSessionConfigForm({
  opensAt,
  onOpensAtChange,
  closesAt,
  onClosesAtChange,
  nominationMode,
  onNominationModeChange,
  minIncrement,
  onMinIncrementChange,
  softClose,
  onSoftCloseChange,
  lotDuration,
  onLotDurationChange,
  operatorUserId,
  onOperatorUserIdChange,
  memberOptions,
  entries,
  ownedAthleteIds,
  queueAthleteIds,
  onToggleQueueAthlete,
  createError,
  creating,
  disabled,
  onSubmit,
}: {
  opensAt: string;
  onOpensAtChange: (value: string) => void;
  closesAt: string;
  onClosesAtChange: (value: string) => void;
  nominationMode: MarketLiveNominationMode;
  onNominationModeChange: (value: MarketLiveNominationMode) => void;
  minIncrement: string;
  onMinIncrementChange: (value: string) => void;
  softClose: string;
  onSoftCloseChange: (value: string) => void;
  lotDuration: string;
  onLotDurationChange: (value: string) => void;
  operatorUserId: string;
  onOperatorUserIdChange: (value: string) => void;
  memberOptions: readonly OptionPickerOption[];
  entries: LeagueListoneEntry[];
  ownedAthleteIds: Set<string>;
  queueAthleteIds: string[];
  onToggleQueueAthlete: (athleteId: string) => void;
  createError: string | null;
  creating: boolean;
  disabled: boolean;
  onSubmit: () => void;
}) {
  const delegate = memberOptions.find((row) => row.value === operatorUserId)?.label ?? "Solo admin";
  const summary: Array<[string, string]> = [
    ["Apertura", opensAt || "—"],
    ["Chiusura", closesAt || "—"],
    ["Chiamata", NOMINATION_MODE_SHORT_LABEL[nominationMode]],
    ["Rilancio minimo", `+${Number(minIncrement) || 1} cr.`],
    ["Soft-close", `${Number(softClose) || 5} s`],
    ["Durata lotto", `${Number(lotDuration) || 10} s`],
    ["Delegato", delegate],
  ];
  return (
    <View style={{ gap: 12 }} testID="auction-live-create">
      <Text style={styles.heroValue}>Configura asta</Text>

      <Section title="1 · Quando" subtitle="Finestra in cui l'asta resta aperta">
        <Text style={styles.fieldLabel}>Apertura (AAAA-MM-GG HH:MM)</Text>
        <TextInput style={styles.input} value={opensAt} onChangeText={onOpensAtChange} placeholder="2026-09-10 20:00" autoCapitalize="none" autoCorrect={false} testID="auction-live-opens-at" />
        <Text style={styles.fieldLabel}>Chiusura (AAAA-MM-GG HH:MM)</Text>
        <TextInput style={styles.input} value={closesAt} onChangeText={onClosesAtChange} placeholder="2026-09-10 23:00" autoCapitalize="none" autoCorrect={false} testID="auction-live-closes-at" />
      </Section>

      <Section title="2 · Come si chiama" subtitle="Modalità di chiamata dei calciatori">
        {NOMINATION_MODE_OPTIONS.map((option) => {
          const active = nominationMode === option.value;
          return (
            <Pressable
              key={option.value}
              style={[styles.modeCard, active && styles.modeCardActive]}
              onPress={() => onNominationModeChange(option.value)}
              accessibilityState={{ selected: active }}
              testID={`auction-live-mode-${option.value}`}
            >
              <View style={styles.modeIcon}>
                <Text style={styles.modeIconLabel}>{MODE_ICON[option.value]}</Text>
              </View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={styles.modeTitle}>{option.label}</Text>
              </View>
              <View style={[styles.radio, active && styles.radioActive]}>{active ? <View style={styles.radioDot} /> : null}</View>
            </Pressable>
          );
        })}
        <Text style={styles.meta} testID="auction-live-mode-hint">
          {NOMINATION_MODE_HINT[nominationMode]}
        </Text>
      </Section>

      {nominationMode === "sequential" ? (
        <Section title="Lista di chiamata" subtitle={`${queueAthleteIds.length} selezionati · in ordine di selezione`}>
          <View testID="auction-live-queue-picker" style={{ gap: 6 }}>
            {entries.map((entry) => {
              const owned = ownedAthleteIds.has(entry.athleteId);
              const position = queueAthleteIds.indexOf(entry.athleteId) + 1;
              return (
                <Pressable
                  key={entry.athleteId}
                  disabled={owned}
                  onPress={() => onToggleQueueAthlete(entry.athleteId)}
                  style={[styles.pickRow, position > 0 && styles.pickRowActive, owned && styles.disabled]}
                  accessibilityLabel={owned ? `${entry.canonicalName} già assegnato` : `Chiama ${entry.canonicalName}`}
                >
                  <View style={[styles.checkBox, position > 0 && styles.checkBoxActive]}>
                    {position > 0 ? <Text style={styles.pillLabelActive}>{position}</Text> : null}
                  </View>
                  <AthleteName athleteId={entry.athleteId} style={styles.optionLabel}>
                    {entry.canonicalName}
                  </AthleteName>
                  {owned ? <Text style={styles.meta}>Assegnato</Text> : null}
                </Pressable>
              );
            })}
          </View>
        </Section>
      ) : null}

      <Section title="3 · Regole di rilancio" subtitle="Come funzionano i rilanci al tavolo">
        <Stepper label="Rilancio minimo" value={minIncrement} unit="cr." step={1} min={1} max={1000} onChange={onMinIncrementChange} testID="auction-live-min-increment" />
        <Stepper label="Soft-close" value={softClose} unit="s" step={5} min={5} max={120} onChange={onSoftCloseChange} testID="auction-live-soft-close" />
        <Text style={styles.meta}>Se rilanci nei secondi finali, il timer si ricarica.</Text>
        <Stepper label="Durata lotto" value={lotDuration} unit="s" step={5} min={10} max={300} onChange={onLotDurationChange} testID="auction-live-lot-duration" />
      </Section>

      <Section title="4 · Delegato" subtitle="Può chiamare i calciatori al posto dell'admin">
        <OptionPicker
          label="Delegato (opzionale)"
          options={memberOptions}
          value={operatorUserId}
          onChange={onOperatorUserIdChange}
          placeholder="Nessun delegato — solo admin"
          testID="auction-live-operator"
        />
      </Section>

      <View style={styles.heroCard}>
        <Text style={styles.heroLabel}>Riepilogo</Text>
        {summary.map(([key, value]) => (
          <View key={key} style={styles.summaryRow}>
            <Text style={styles.summaryKey}>{key}</Text>
            <Text style={styles.summaryVal}>{value}</Text>
          </View>
        ))}
      </View>

      {createError ? <Text style={styles.error} testID="auction-live-create-error">{createError}</Text> : null}
      <Pressable
        style={[styles.bigButton, (creating || disabled) && styles.disabled]}
        disabled={creating || disabled}
        onPress={onSubmit}
        testID="auction-live-create-submit"
      >
        <Text style={styles.bigButtonLabel}>{creating ? "Creazione…" : "Crea sessione ed entra nel tavolo"}</Text>
      </Pressable>
    </View>
  );
}
