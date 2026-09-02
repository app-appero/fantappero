import { Pressable, Text, TextInput, View } from "react-native";
import { StatusBadge } from "../../components/StatusBadge";
import { UiStatePanel } from "../../components/UiStatePanel";
import type { MarketSessionFlow } from "../../market/useMarketSessionFlow";
import { SESSION_STATUS_COLOR, SESSION_STATUS_LABEL } from "../../market/marketLabels";
import { marketUiStyles as styles } from "../../market/marketUiStyles";

/**
 * Admin session management panel shared shape for Asta (EP08-01/02) and Svincolati (EP08-03):
 * create/close/resolve a closed-envelope market session and show resolution outcomes.
 */
export function AuctionAdminPanel({
  flow,
  opensAt,
  onOpensAtChange,
  closesAt,
  onClosesAtChange,
  onCreateSession,
  formError,
  closeLabel = "Chiudi asta",
  resolveLabel = "Risolvi asta",
  emptyTitle = "Nessuna sessione d'asta",
  emptyMessage = "Crea la finestra d'asta a buste chiuse per iniziare.",
  testIdPrefix = "auction",
}: {
  flow: MarketSessionFlow;
  opensAt: string;
  onOpensAtChange: (value: string) => void;
  closesAt: string;
  onClosesAtChange: (value: string) => void;
  onCreateSession: () => void;
  formError?: string | null;
  closeLabel?: string;
  resolveLabel?: string;
  emptyTitle?: string;
  emptyMessage?: string;
  testIdPrefix?: string;
}) {
  return (
    <View style={styles.section} testID={`wireframe-region-${testIdPrefix}-admin`}>
      <Text style={styles.sectionTitle}>Gestione sessione (admin)</Text>

      {flow.loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento sessioni"
          message="Recupero le sessioni…"
          testID={`${testIdPrefix}-admin-loading`}
        />
      ) : null}

      {!flow.loading && flow.loadError ? (
        <UiStatePanel
          state="error"
          title="Sessioni non disponibili"
          message={flow.loadError}
          testID={`${testIdPrefix}-admin-error`}
        />
      ) : null}

      {!flow.loading && !flow.loadError && flow.currentSession ? (
        <View testID={`${testIdPrefix}-admin-current-session`}>
          <View style={styles.rowActions}>
            <StatusBadge
              label={SESSION_STATUS_LABEL[flow.currentSession.status]}
              color={SESSION_STATUS_COLOR[flow.currentSession.status].background}
              textColor={SESSION_STATUS_COLOR[flow.currentSession.status].text}
            />
            <Text style={styles.meta}>Offerte: {flow.currentSession.bidCount ?? "—"}</Text>
          </View>
          <View style={styles.rowActions}>
            <Pressable
              style={[
                styles.secondaryButton,
                (flow.currentSession.status !== "open" || flow.sessionActionPending) &&
                  styles.disabled,
              ]}
              disabled={flow.currentSession.status !== "open" || flow.sessionActionPending}
              onPress={() => void flow.closeCurrentSession()}
              testID={`${testIdPrefix}-admin-close`}
            >
              <Text style={styles.secondaryButtonLabel}>{closeLabel}</Text>
            </Pressable>
            <Pressable
              style={[
                styles.button,
                (flow.currentSession.status !== "closed" || flow.sessionActionPending) &&
                  styles.disabled,
              ]}
              disabled={flow.currentSession.status !== "closed" || flow.sessionActionPending}
              onPress={() => void flow.resolveCurrentSession()}
              testID={`${testIdPrefix}-admin-resolve`}
            >
              <Text style={styles.buttonLabel}>{resolveLabel}</Text>
            </Pressable>
          </View>
        </View>
      ) : null}

      {!flow.loading && !flow.loadError && !flow.currentSession ? (
        <UiStatePanel
          state="empty"
          title={emptyTitle}
          message={emptyMessage}
          testID={`${testIdPrefix}-admin-empty`}
        />
      ) : null}

      {flow.sessionActionError ? (
        <UiStatePanel
          state="error"
          title="Operazione non riuscita"
          message={flow.sessionActionError}
          testID={`${testIdPrefix}-admin-action-error`}
        />
      ) : null}

      {flow.resolution ? (
        <View testID={`${testIdPrefix}-resolution-outcomes`}>
          <Text style={styles.sectionTitle}>Esiti risoluzione</Text>
          {flow.resolution.outcomes.length === 0 ? (
            <Text style={styles.meta}>Nessuna offerta da assegnare.</Text>
          ) : (
            <View style={styles.outcomeList}>
              {flow.resolution.outcomes.map((outcome) => (
                <Text key={outcome.athleteId} style={styles.meta}>
                  {outcome.athleteName}:{" "}
                  {outcome.outcome === "assigned"
                    ? `assegnato per ${outcome.amountCredits} crediti`
                    : outcome.outcome === "tiebreak"
                      ? "spareggio aperto (parità)"
                      : "non assegnato"}
                </Text>
              ))}
            </View>
          )}
        </View>
      ) : null}

      <View style={styles.field} testID={`${testIdPrefix}-create-session-form`}>
        <Text style={styles.fieldLabel}>Apertura (AAAA-MM-GG HH:MM)</Text>
        <TextInput
          style={styles.input}
          value={opensAt}
          onChangeText={onOpensAtChange}
          placeholder="2026-08-25 10:00"
          autoCapitalize="none"
          autoCorrect={false}
          testID={`${testIdPrefix}-opens-at`}
        />
        <Text style={styles.fieldLabel}>Chiusura (AAAA-MM-GG HH:MM)</Text>
        <TextInput
          style={styles.input}
          value={closesAt}
          onChangeText={onClosesAtChange}
          placeholder="2026-08-26 10:00"
          autoCapitalize="none"
          autoCorrect={false}
          testID={`${testIdPrefix}-closes-at`}
        />
        {formError ? (
          <Text style={styles.error} testID={`${testIdPrefix}-create-session-format-error`}>
            {formError}
          </Text>
        ) : null}
        {flow.createError ? (
          <Text style={styles.error} testID={`${testIdPrefix}-create-session-error`}>
            {flow.createError}
          </Text>
        ) : null}
        <Pressable
          style={[styles.button, flow.creating && styles.disabled]}
          disabled={flow.creating}
          onPress={onCreateSession}
          testID={`${testIdPrefix}-create-session-submit`}
        >
          <Text style={styles.buttonLabel}>{flow.creating ? "Creazione…" : "Crea sessione"}</Text>
        </Pressable>
      </View>
    </View>
  );
}
