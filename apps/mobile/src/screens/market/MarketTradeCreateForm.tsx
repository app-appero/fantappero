import type { FantasyRosterSlot, TeamRosterPlayer } from "@fantappero/contracts";
import { DateTimeField, formatDateTimeValue } from "../../components/DateTimeField";
import { Pressable, Text, View } from "react-native";
import { AthleteName } from "../../athletes/AthleteCard";
import { AppTextInput as TextInput } from "../../components/AppTextInput";
import { HScroll } from "../../components/HScroll";
import type { OptionPickerOption } from "../../components/OptionPicker";
import { UiStatePanel } from "../../components/UiStatePanel";
import { marketUiStyles as styles } from "../../market/marketUiStyles";
import { roleBadgeColors } from "../roster/rosterHelpers";
import { useState } from "react";

export type TradeAthleteMeta = { role: string | null; club: string | null };

/** Riga selezionabile con pallino del ruolo, squadra e prezzo di acquisto. */
function AthleteCheckRow({
  label,
  athleteId,
  checked,
  onToggle,
  disabled = false,
  meta,
  price,
  testID,
}: {
  label: string;
  athleteId?: string | null;
  checked: boolean;
  onToggle: () => void;
  disabled?: boolean;
  meta?: TradeAthleteMeta;
  price?: number | null;
  testID?: string;
}) {
  const dot = roleBadgeColors(meta?.role);
  return (
    <Pressable
      style={[styles.pickRow, checked && styles.pickRowActive, disabled && styles.disabled]}
      onPress={onToggle}
      disabled={disabled}
      accessibilityRole="checkbox"
      accessibilityState={{ disabled, checked }}
      testID={testID}
    >
      <View style={[styles.checkBox, checked && styles.checkBoxActive]}>
        {checked ? <Text style={styles.pillLabelActive}>✓</Text> : null}
      </View>
      <View style={[styles.proposalAvatar, { width: 30, height: 30, borderRadius: 15, backgroundColor: dot.backgroundColor }]}>
        <Text style={[styles.proposalAvatarLabel, { color: dot.color }]}>{meta?.role ?? "?"}</Text>
      </View>
      <View style={{ flex: 1, minWidth: 0 }}>
        <AthleteName athleteId={athleteId} style={styles.optionLabel} numberOfLines={1} plain>
          {label}
        </AthleteName>
        {meta?.club ? <Text style={styles.meta}>{meta.club}</Text> : null}
      </View>
      {price != null ? <Text style={styles.heroValue}>{price}</Text> : null}
    </Pressable>
  );
}

const PREVIEW_LIMIT = 6;

/** Pannello di scelta giocatori (tuoi o dell'altra squadra) con ricerca e filtro per ruolo. */
function PickPanel({
  title,
  hint,
  rows,
  selected,
  onToggle,
  meta,
  disabled,
  emptyText,
  testID,
}: {
  title: string;
  hint: string;
  rows: Array<{ athleteId: string; name: string; price: number | null }>;
  selected: string[];
  onToggle: (athleteId: string) => void;
  meta: Map<string, TradeAthleteMeta>;
  disabled?: boolean;
  emptyText: string;
  testID: string;
}) {
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<"all" | "P" | "D" | "C" | "A">("all");
  const [showAll, setShowAll] = useState(false);
  const needle = query.trim().toLocaleLowerCase("it-IT");
  const filtered = rows.filter((row) => {
    const m = meta.get(row.athleteId);
    if (role !== "all" && m?.role !== role) {
      return false;
    }
    return !needle || `${row.name} ${m?.club ?? ""}`.toLocaleLowerCase("it-IT").includes(needle);
  });
  // I selezionati restano sempre visibili anche con l'elenco ridotto.
  const ordered = [...filtered].sort((a, b) => Number(selected.includes(b.athleteId)) - Number(selected.includes(a.athleteId)));
  const visible = showAll || needle || role !== "all" ? ordered : ordered.slice(0, PREVIEW_LIMIT);
  return (
    <View style={styles.proposalCard} testID={testID}>
      <View style={styles.proposalHead}>
        <View style={{ flex: 1 }}>
          <Text style={styles.sectionTitle}>{title}</Text>
          <Text style={styles.meta}>{hint}</Text>
        </View>
        {selected.length > 0 ? (
          <View style={styles.creditsChip}>
            <Text style={styles.creditsChipLabel}>{selected.length} scelti</Text>
          </View>
        ) : null}
      </View>
      {rows.length === 0 ? (
        <Text style={styles.meta}>{emptyText}</Text>
      ) : (
        <>
          <TextInput
            style={styles.input}
            value={query}
            onChangeText={setQuery}
            placeholder="Cerca per nome o squadra"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <HScroll>
            {(["all", "P", "D", "C", "A"] as const).map((value) => (
              <Pressable key={value} style={[styles.pill, role === value && styles.pillActive]} onPress={() => setRole(value)}>
                <Text style={[styles.pillLabel, role === value && styles.pillLabelActive]}>{value === "all" ? "Tutti" : value}</Text>
              </Pressable>
            ))}
          </HScroll>
          <View style={{ gap: 6 }}>
            {visible.map((row) => (
              <AthleteCheckRow
                key={row.athleteId}
                label={row.name}
                athleteId={row.athleteId}
                checked={selected.includes(row.athleteId)}
                disabled={disabled}
                onToggle={() => onToggle(row.athleteId)}
                meta={meta.get(row.athleteId)}
                price={row.price}
                testID={`${testID}-${row.athleteId}`}
              />
            ))}
            {filtered.length === 0 ? <Text style={styles.meta}>Nessun giocatore trovato.</Text> : null}
          </View>
          {!showAll && !needle && role === "all" && ordered.length > PREVIEW_LIMIT ? (
            <Pressable style={styles.secondaryButton} onPress={() => setShowAll(true)}>
              <Text style={styles.secondaryButtonLabel}>{`Mostra tutti (${ordered.length})`}</Text>
            </Pressable>
          ) : null}
        </>
      )}
    </View>
  );
}

/** Nuova proposta di scambio: giocatori offerti/richiesti, crediti e scadenza (EP08-05/06). */
export function MarketTradeCreateForm({
  recipientOptions,
  recipientTeamId,
  onRecipientTeamIdChange,
  ownedSlots,
  offeredAthleteIds,
  onToggleOffered,
  recipientPlayers,
  recipientRosterLoading,
  recipientRosterError,
  onRetryRecipientRoster,
  requestedAthleteIds,
  onToggleRequested,
  offeredCredits,
  onOfferedCreditsChange,
  requestedCredits,
  onRequestedCreditsChange,
  expiresAt,
  onExpiresAtChange,
  createError,
  creating,
  onSubmit,
  athleteMeta,
}: {
  recipientOptions: readonly OptionPickerOption[];
  recipientTeamId: string;
  onRecipientTeamIdChange: (teamId: string) => void;
  ownedSlots: FantasyRosterSlot[];
  offeredAthleteIds: string[];
  onToggleOffered: (athleteId: string) => void;
  recipientPlayers: TeamRosterPlayer[];
  recipientRosterLoading: boolean;
  recipientRosterError: string | null;
  onRetryRecipientRoster: () => void;
  requestedAthleteIds: string[];
  onToggleRequested: (athleteId: string) => void;
  offeredCredits: string;
  onOfferedCreditsChange: (value: string) => void;
  requestedCredits: string;
  onRequestedCreditsChange: (value: string) => void;
  expiresAt: string;
  onExpiresAtChange: (value: string) => void;
  createError: string | null;
  creating: boolean;
  onSubmit: () => void;
  /** Ruolo e squadra di ogni calciatore, dal listone della lega. */
  athleteMeta: Map<string, TradeAthleteMeta>;
}) {
  const canPropose = ownedSlots.length > 0;
  const recipientName = recipientOptions.find((row) => row.value === recipientTeamId)?.label ?? null;
  const nameOf = (id: string, fallback: string) =>
    ownedSlots.find((slot) => slot.athleteId === id)?.athleteName ??
    recipientPlayers.find((player) => player.athleteId === id)?.athleteName ??
    fallback;
  const giveText = [...offeredAthleteIds.map((id) => nameOf(id, "Giocatore")), Number(offeredCredits) > 0 ? `${offeredCredits} cr.` : ""]
    .filter(Boolean)
    .join(" + ");
  const getText = [...requestedAthleteIds.map((id) => nameOf(id, "Giocatore")), Number(requestedCredits) > 0 ? `${requestedCredits} cr.` : ""]
    .filter(Boolean)
    .join(" + ");
  return (
    <View style={{ gap: 12 }} testID="market-trade-form-section">
      <Text style={styles.sectionTitle}>Nuova proposta</Text>
      {canPropose ? null : (
        <UiStatePanel
          state="empty"
          title="Nessun calciatore in rosa"
          message="Assegna almeno un calciatore alla rosa per proporre uno scambio."
          testID="market-trade-empty-roster"
        />
      )}
      <View style={styles.proposalCard} testID="market-trade-create-form">
        <Text style={styles.sideLabel}>1 · Con chi scambi</Text>
        <HScroll testID="market-trade-recipient">
          {recipientOptions.map((option) => (
            <Pressable
              key={option.value}
              style={[styles.pill, recipientTeamId === option.value && styles.pillActive]}
              disabled={!canPropose}
              onPress={() => onRecipientTeamIdChange(option.value)}
              testID={`market-trade-recipient-${option.value}`}
            >
              <Text style={[styles.pillLabel, recipientTeamId === option.value && styles.pillLabelActive]}>{option.label}</Text>
            </Pressable>
          ))}
        </HScroll>
        {recipientOptions.length === 0 ? <Text style={styles.meta}>Non ci sono altre squadre in questa lega.</Text> : null}
      </View>

      <PickPanel
        testID="market-trade-offered-athletes"
        title="2 · Tu dai"
        hint="Scegli uno o più giocatori della tua rosa"
        rows={ownedSlots.map((slot) => ({ athleteId: slot.athleteId as string, name: slot.athleteName ?? "Giocatore", price: slot.purchaseCredits ?? null }))}
        selected={offeredAthleteIds}
        onToggle={onToggleOffered}
        meta={athleteMeta}
        disabled={!canPropose}
        emptyText="Nessun giocatore in rosa da offrire."
      />

      <View style={{ gap: 12 }} testID="market-trade-requested-athletes">
        {!recipientTeamId ? (
          <View style={styles.proposalCard}>
            <Text style={styles.sectionTitle}>3 · Tu ricevi</Text>
            <Text style={styles.meta}>Scegli prima la squadra: qui compaiono i suoi giocatori.</Text>
          </View>
        ) : recipientRosterLoading ? (
          <UiStatePanel state="loading" title="Caricamento rosa" message="Recupero i giocatori della squadra selezionata…" testID="market-trade-recipient-loading" />
        ) : recipientRosterError ? (
          <View style={{ gap: 8 }}>
            <UiStatePanel state="error" title="Rosa non disponibile" message={recipientRosterError} testID="market-trade-recipient-error" />
            <Pressable style={styles.secondaryButton} onPress={onRetryRecipientRoster}>
              <Text style={styles.secondaryButtonLabel}>Riprova</Text>
            </Pressable>
          </View>
        ) : (
          <PickPanel
            testID="market-trade-requested"
            title="3 · Tu ricevi"
            hint={`Scegli uno o più giocatori di ${recipientName ?? "questa squadra"}`}
            rows={recipientPlayers.map((player) => ({ athleteId: player.athleteId, name: player.athleteName, price: player.purchaseCredits ?? null }))}
            selected={requestedAthleteIds}
            onToggle={onToggleRequested}
            meta={athleteMeta}
            disabled={!canPropose}
            emptyText="Questa squadra non ha ancora giocatori in rosa."
          />
        )}
      </View>

      <View style={styles.proposalCard}>
        <Text style={styles.sideLabel}>4 · Crediti (facoltativi)</Text>
        <Text style={styles.fieldLabel}>Crediti che dai</Text>
        <TextInput
          style={[styles.input, !canPropose && styles.disabled]}
          value={offeredCredits}
          onChangeText={onOfferedCreditsChange}
          keyboardType="numeric"
          editable={canPropose}
          testID="market-trade-offered-credits"
        />
        <Text style={styles.fieldLabel}>Crediti che ricevi</Text>
        <TextInput
          style={[styles.input, !canPropose && styles.disabled]}
          value={requestedCredits}
          onChangeText={onRequestedCreditsChange}
          keyboardType="numeric"
          editable={canPropose}
          testID="market-trade-requested-credits"
        />
        <DateTimeField
          label="Scadenza"
          value={expiresAt}
          onChange={onExpiresAtChange}
          placeholder="Scegli quando scade la proposta"
          min={formatDateTimeValue(new Date())}
          minHint="La scadenza deve essere futura"
          testID="market-trade-expires-at"
        />
      </View>

      {giveText || getText ? (
        <View style={styles.heroCard} testID="market-trade-summary">
          <Text style={styles.heroLabel}>Riepilogo</Text>
          <Text style={styles.modeTitle}>{`Dai: ${giveText || "—"}`}</Text>
          <Text style={styles.modeTitle}>{`Ricevi: ${getText || "—"}`}</Text>
        </View>
      ) : null}

      {createError ? (
        <Text style={styles.error} testID="market-trade-create-error">
          {createError}
        </Text>
      ) : null}

      <Pressable
        style={[styles.bigButton, (creating || !recipientTeamId || !canPropose) && styles.disabled]}
        disabled={creating || !recipientTeamId || !canPropose}
        onPress={onSubmit}
        testID="market-trade-create-submit"
      >
        <Text style={styles.bigButtonLabel}>{creating ? "Invio…" : "Invia proposta"}</Text>
      </Pressable>
    </View>
  );
}
