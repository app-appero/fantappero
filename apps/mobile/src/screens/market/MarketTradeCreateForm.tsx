import type { FantasyRosterSlot, TeamRosterPlayer } from "@fantappero/contracts";
import { Pressable, Text, TextInput, View } from "react-native";
import { OptionPicker, type OptionPickerOption } from "../../components/OptionPicker";
import { UiStatePanel } from "../../components/UiStatePanel";
import { marketUiStyles as styles } from "../../market/marketUiStyles";

function AthleteCheckRow({
  label,
  checked,
  onToggle,
  testID,
}: {
  label: string;
  checked: boolean;
  onToggle: () => void;
  testID?: string;
}) {
  return (
    <Pressable style={styles.optionRow} onPress={onToggle} testID={testID}>
      <Text style={styles.optionLabel}>{label}</Text>
      <Text style={styles.meta}>{checked ? "☑" : "☐"}</Text>
    </Pressable>
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
}) {
  return (
    <View style={styles.section} testID="market-trade-form-section">
      <Text style={styles.sectionTitle}>Nuova proposta di scambio</Text>
      <View style={styles.field} testID="market-trade-create-form">
        <OptionPicker
          label="Squadra destinataria"
          options={recipientOptions}
          value={recipientTeamId}
          onChange={onRecipientTeamIdChange}
          placeholder="Scegli una squadra…"
          testID="market-trade-recipient"
        />

        <Text style={styles.fieldLabel}>Giocatori offerti (dalla tua rosa)</Text>
        <View testID="market-trade-offered-athletes">
          {ownedSlots.length === 0 ? (
            <Text style={styles.meta}>Nessun giocatore in rosa da offrire.</Text>
          ) : (
            ownedSlots.map((slot) => (
              <AthleteCheckRow
                key={slot.id}
                label={slot.athleteName ?? "Giocatore"}
                checked={offeredAthleteIds.includes(slot.athleteId as string)}
                onToggle={() => onToggleOffered(slot.athleteId as string)}
                testID={`market-trade-offered-${slot.athleteId}`}
              />
            ))
          )}
        </View>

        <Text style={styles.fieldLabel}>Giocatori richiesti</Text>
        <View testID="market-trade-requested-athletes">
          {!recipientTeamId ? <Text style={styles.meta}>Scegli prima una squadra destinataria.</Text> : null}
          {recipientTeamId && recipientRosterLoading ? (
            <UiStatePanel
              state="loading"
              title="Caricamento rosa"
              message="Recupero i giocatori della squadra selezionata…"
              testID="market-trade-recipient-loading"
            />
          ) : null}
          {recipientTeamId && !recipientRosterLoading && recipientRosterError ? (
            <View>
              <UiStatePanel
                state="error"
                title="Rosa non disponibile"
                message={recipientRosterError}
                testID="market-trade-recipient-error"
              />
              <Pressable style={styles.secondaryButton} onPress={onRetryRecipientRoster}>
                <Text style={styles.secondaryButtonLabel}>Riprova</Text>
              </Pressable>
            </View>
          ) : null}
          {recipientTeamId &&
          !recipientRosterLoading &&
          !recipientRosterError &&
          recipientPlayers.length === 0 ? (
            <Text style={styles.meta} testID="market-trade-recipient-empty">
              Questa squadra non ha ancora giocatori in rosa.
            </Text>
          ) : null}
          {recipientTeamId && !recipientRosterLoading && !recipientRosterError
            ? recipientPlayers.map((athlete) => (
                <AthleteCheckRow
                  key={athlete.athleteId}
                  label={athlete.athleteName}
                  checked={requestedAthleteIds.includes(athlete.athleteId)}
                  onToggle={() => onToggleRequested(athlete.athleteId)}
                  testID={`market-trade-requested-${athlete.athleteId}`}
                />
              ))
            : null}
        </View>

        <Text style={styles.fieldLabel}>Crediti offerti</Text>
        <TextInput
          style={styles.input}
          value={offeredCredits}
          onChangeText={onOfferedCreditsChange}
          keyboardType="numeric"
          testID="market-trade-offered-credits"
        />
        <Text style={styles.fieldLabel}>Crediti richiesti</Text>
        <TextInput
          style={styles.input}
          value={requestedCredits}
          onChangeText={onRequestedCreditsChange}
          keyboardType="numeric"
          testID="market-trade-requested-credits"
        />
        <Text style={styles.fieldLabel}>Scadenza (AAAA-MM-GG HH:MM)</Text>
        <TextInput
          style={styles.input}
          value={expiresAt}
          onChangeText={onExpiresAtChange}
          placeholder="2026-09-01 00:00"
          autoCapitalize="none"
          autoCorrect={false}
          testID="market-trade-expires-at"
        />

        {createError ? (
          <Text style={styles.error} testID="market-trade-create-error">
            {createError}
          </Text>
        ) : null}

        <Pressable
          style={[styles.button, (creating || !recipientTeamId) && styles.disabled]}
          disabled={creating || !recipientTeamId}
          onPress={onSubmit}
          testID="market-trade-create-submit"
        >
          <Text style={styles.buttonLabel}>{creating ? "Invio…" : "Proponi scambio"}</Text>
        </Pressable>
      </View>
    </View>
  );
}
