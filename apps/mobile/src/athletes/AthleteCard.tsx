import type { AthleteCard } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  Image,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from "react-native";
import { fetchAthleteCard } from "../api/leagues";
import { UiStatePanel } from "../components/UiStatePanel";
import { getApiErrorMessage, useAuthSession } from "../session/DemoSessionContext";
import { lazyStyles } from "../theme/lazyStyles";

const { colors, spacing, radius, typography } = theme;

const ROLE_LABEL: Record<string, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};

type AthleteCardContextValue = {
  open: (athleteId: string) => void;
};

const AthleteCardContext = createContext<AthleteCardContextValue | null>(null);

export function useAthleteCard(): AthleteCardContextValue | null {
  return useContext(AthleteCardContext);
}

/** Nome cliccabile. Senza provider resta testo normale. */
export function AthleteName({
  athleteId,
  children,
  style,
  containerStyle,
  numberOfLines,
}: {
  athleteId?: string | null;
  children: string;
  style?: StyleProp<TextStyle>;
  /** Layout della cella: applicato al Pressable, o al testo se la scheda non è disponibile. */
  containerStyle?: StyleProp<ViewStyle>;
  numberOfLines?: number;
}) {
  const card = useAthleteCard();
  if (!card || !athleteId) {
    return (
      <Text style={[style, containerStyle as StyleProp<TextStyle>]} numberOfLines={numberOfLines}>
        {children}
      </Text>
    );
  }
  return (
    <Pressable
      style={containerStyle}
      accessibilityRole="button"
      accessibilityLabel={`Apri scheda di ${children}`}
      onPress={() => card.open(athleteId)}
    >
      <Text style={[style, styles.link]} numberOfLines={numberOfLines}>
        {children}
      </Text>
    </Pressable>
  );
}

function formatIsoDate(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) {
    return value;
  }
  return `${match[3]}/${match[2]}/${match[1]}`;
}

function roleLabel(code: string | null): string | null {
  if (!code) {
    return null;
  }
  return ROLE_LABEL[code] ? `${ROLE_LABEL[code]} (${code})` : code;
}

function transferLabel(transferType: string): string {
  if (transferType === "Loan") {
    return "Prestito";
  }
  if (transferType === "Free") {
    return "Parametro zero";
  }
  if (transferType === "N/A" || transferType === "€") {
    return "Trasferimento";
  }
  return transferType;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return "?";
  }
  if (parts.length === 1) {
    return parts[0]!.slice(0, 2).toUpperCase();
  }
  return `${parts[0]!.charAt(0)}${parts[parts.length - 1]!.charAt(0)}`.toUpperCase();
}

function AthleteCardView({ card }: { card: AthleteCard }) {
  const facts: Array<{ label: string; value: string }> = [];
  const birth = formatIsoDate(card.birthDate);
  if (birth) {
    facts.push({ label: "Nascita", value: card.age != null ? `${birth} · ${card.age} anni` : birth });
  } else if (card.age != null) {
    facts.push({ label: "Età", value: `${card.age} anni` });
  }
  if (card.nationality) {
    facts.push({ label: "Nazionalità", value: card.nationality });
  }
  if (card.height) {
    facts.push({ label: "Altezza", value: card.height });
  }
  if (card.weight) {
    facts.push({ label: "Peso", value: card.weight });
  }
  const role = roleLabel(card.effectiveRole ?? card.role);
  if (role) {
    facts.push({
      label: card.effectiveRole && card.role && card.effectiveRole !== card.role ? "Ruolo in lega" : "Ruolo",
      value: role,
    });
  }
  if (card.providerPositionRaw) {
    facts.push({ label: "Posizione provider", value: card.providerPositionRaw });
  }
  if (card.shirtNumber != null) {
    facts.push({ label: "Maglia", value: String(card.shirtNumber) });
  }
  if (card.injured != null) {
    facts.push({ label: "Stato", value: card.injured ? "Infortunato" : "Disponibile" });
  }
  facts.push({
    label: "In questa lega",
    value: card.assignment
      ? `${card.assignment.teamName} · slot ${card.assignment.slotIndex + 1}${
          card.assignment.purchaseCredits != null ? ` · ${card.assignment.purchaseCredits} crediti` : ""
        }`
      : "Libero",
  });

  return (
    <View testID="athlete-card">
      <View style={styles.hero}>
        {card.photoUrl ? (
          <Image source={{ uri: card.photoUrl }} style={styles.photo} />
        ) : (
          <View style={[styles.photo, styles.photoEmpty]}>
            <Text style={styles.initials}>{initials(card.canonicalName)}</Text>
          </View>
        )}
        <View style={styles.heroText}>
          <Text style={styles.sub}>
            {[card.firstName, card.lastName].filter(Boolean).join(" ") || card.canonicalName}
          </Text>
          <Text style={styles.sub}>{card.clubName ?? "Club non disponibile"}</Text>
        </View>
      </View>
      <View style={styles.facts}>
        {facts.map((fact) => (
          <View key={fact.label} style={styles.fact}>
            <Text style={styles.factLabel}>{fact.label}</Text>
            <Text style={styles.factValue}>{fact.value}</Text>
          </View>
        ))}
      </View>
      <Text style={styles.sectionTitle}>Stagioni</Text>
      {card.seasons.length === 0 ? (
        <Text style={styles.sub}>Nessuna stagione salvata dal provider.</Text>
      ) : (
        card.seasons.map((season) => (
          <Text key={`${season.seasonYear}-${season.clubName}-${season.shirtNumber ?? ""}`} style={styles.line}>
            {season.seasonYear} · {season.clubName}
            {season.shirtNumber != null ? ` · n. ${season.shirtNumber}` : ""}
            {season.positionRaw ? ` · ${season.positionRaw}` : ""}
            {season.isActive ? " · in rosa" : ""}
          </Text>
        ))
      )}
      <Text style={styles.sectionTitle}>Trasferimenti</Text>
      {card.transfers.length === 0 ? (
        <Text style={styles.sub}>Nessun trasferimento salvato dal provider.</Text>
      ) : (
        card.transfers.map((transfer) => (
          <Text
            key={`${transfer.transferDate}-${transfer.fromClubName ?? ""}-${transfer.toClubName ?? ""}`}
            style={styles.line}
          >
            {formatIsoDate(transfer.transferDate)} · {transfer.fromClubName ?? "—"} → {transfer.toClubName ?? "—"} ·{" "}
            {transferLabel(transfer.transferType)}
          </Text>
        ))
      )}
    </View>
  );
}

export function AthleteCardProvider({ children }: { children: ReactNode }) {
  const { accessToken, activeLeagueId } = useAuthSession();
  const [athleteId, setAthleteId] = useState<string | null>(null);
  const [card, setCard] = useState<AthleteCard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = useCallback((nextId: string) => {
    setAthleteId(nextId);
  }, []);

  const close = useCallback(() => {
    setAthleteId(null);
  }, []);

  useEffect(() => {
    if (!athleteId) {
      setCard(null);
      setError(null);
      setLoading(false);
      return;
    }
    if (!activeLeagueId) {
      setCard(null);
      setLoading(false);
      setError("Seleziona una lega per aprire la scheda del calciatore.");
      return;
    }
    if (!accessToken) {
      setCard(null);
      setLoading(false);
      setError("Accedi per aprire la scheda del calciatore.");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCard(null);
    fetchAthleteCard(accessToken, activeLeagueId, athleteId)
      .then((result) => {
        if (!cancelled) {
          setCard(result);
        }
      })
      .catch((loadError: unknown) => {
        if (!cancelled) {
          setError(getApiErrorMessage(loadError, "Impossibile caricare la scheda."));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, activeLeagueId, athleteId]);

  return (
    <AthleteCardContext.Provider value={{ open }}>
      {children}
      <Modal visible={athleteId != null} transparent animationType="fade" onRequestClose={close}>
        <View style={styles.backdrop}>
          <View style={styles.sheet} testID="athlete-card-modal">
            <View style={styles.header}>
              <Text style={styles.title}>{card?.canonicalName ?? "Calciatore"}</Text>
              <Pressable accessibilityRole="button" accessibilityLabel="Chiudi" onPress={close}>
                <Text style={styles.close}>Chiudi</Text>
              </Pressable>
            </View>
            <ScrollView contentContainerStyle={styles.body}>
              {loading ? (
                <UiStatePanel
                  state="loading"
                  title="Caricamento scheda"
                  message="Recupero foto, anagrafica e rosa di lega…"
                  testID="athlete-card-loading"
                />
              ) : null}
              {!loading && error ? (
                <UiStatePanel
                  state="error"
                  title="Scheda non disponibile"
                  message={error}
                  testID="athlete-card-error"
                />
              ) : null}
              {!loading && !error && card ? <AthleteCardView card={card} /> : null}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </AthleteCardContext.Provider>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    link: {
      color: colors.accent,
      textDecorationLine: "underline",
    },
    backdrop: {
      flex: 1,
      backgroundColor: "rgba(6, 9, 16, 0.72)",
      justifyContent: "center",
      padding: spacing.md,
    },
    sheet: {
      maxHeight: "88%",
      backgroundColor: colors.backgroundElevated,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.border,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: spacing.sm,
      padding: spacing.md,
      borderBottomWidth: 1,
      borderBottomColor: colors.border,
    },
    title: {
      flex: 1,
      color: colors.foreground,
      fontSize: typography.fontSize.lg,
      fontWeight: "700",
    },
    close: {
      color: colors.accent,
      fontWeight: "600",
    },
    body: {
      padding: spacing.md,
      gap: spacing.xs,
    },
    hero: {
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.md,
      marginBottom: spacing.sm,
    },
    heroText: {
      flex: 1,
      gap: 2,
    },
    photo: {
      width: 72,
      height: 72,
      borderRadius: 36,
      backgroundColor: colors.backgroundSubtle,
    },
    photoEmpty: {
      alignItems: "center",
      justifyContent: "center",
    },
    initials: {
      color: colors.foregroundMuted,
      fontWeight: "700",
      fontSize: typography.fontSize.md,
    },
    sub: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.sm,
    },
    facts: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: spacing.sm,
      marginBottom: spacing.sm,
    },
    fact: {
      width: "47%",
      gap: 2,
    },
    factLabel: {
      color: colors.foregroundMuted,
      fontSize: typography.fontSize.xs,
    },
    factValue: {
      color: colors.foreground,
      fontSize: typography.fontSize.sm,
    },
    sectionTitle: {
      color: colors.foreground,
      fontWeight: "700",
      marginTop: spacing.sm,
      marginBottom: spacing.xs,
    },
    line: {
      color: colors.foreground,
      fontSize: typography.fontSize.sm,
      marginBottom: 2,
    },
  }),
);
