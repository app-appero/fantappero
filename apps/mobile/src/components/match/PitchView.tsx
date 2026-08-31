import type { MatchBadge, PitchPosition } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { Image, StyleSheet, Text, View } from "react-native";
import { EventBadges } from "./EventBadges";
import { RoleBadge } from "./RoleBadge";

const { colors, spacing, typography, radius } = theme;

export type PitchPlayer = {
  id: string;
  shirtNumber?: number | null;
  name: string;
  /** Codice ruolo (G/D/M/F o P/D/C/A). */
  role: string | null;
  badges?: readonly MatchBadge[];
  /** Punteggio fantasy da mostrare sulla pill: `"7.5"` o `"7.5 LIVE"`. */
  scoreLabel?: string | null;
  /** Foto dal provider, quando disponibile; altrimenti resta il cerchio con il numero. */
  photoUrl?: string | null;
};

export type PitchViewProps = {
  title: string;
  players: readonly PitchPlayer[];
  positions: readonly PitchPosition[];
  testID?: string;
};

function abbreviateName(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length <= 1) {
    return name;
  }
  const last = parts[parts.length - 1] ?? name;
  const initials = parts.slice(0, -1).map((part) => `${part.charAt(0)}.`);
  return `${initials.join(" ")} ${last}`;
}

/**
 * Campo grafico mobile (EP13-P04-quater §2/§4), porting nativo di
 * `packages/ui`'s `FootballPitch`: stessa logica di posizionamento
 * (`layoutFromGrid`/`layoutFromModule` di `packages/contracts`), rese qui
 * con `View` bordate invece di CSS — nessun asset, nessuna nuova dipendenza.
 */
export function PitchView({ title, players, positions, testID }: PitchViewProps) {
  const positionById = new Map(positions.map((position) => [position.id, position]));
  return (
    <View style={styles.wrap} testID={testID ?? "pitch-view"}>
      <Text style={styles.title}>{title}</Text>
      <View style={styles.pitch}>
        <View style={styles.halfwayLine} />
        <View style={styles.centerCircle} />
        <View style={[styles.box, styles.boxTop]} />
        <View style={[styles.box, styles.boxBottom]} />
        {players.map((player) => {
          const position = positionById.get(player.id);
          if (!position) {
            return null;
          }
          return (
            <View
              key={player.id}
              style={[
                styles.slot,
                { left: `${position.xPercent}%` as `${number}%`, top: `${position.yPercent}%` as `${number}%` },
              ]}
              testID={`pitch-player-${player.id}`}
            >
              <View style={styles.badgesRow}>
                <EventBadges badges={player.badges ?? []} size={11} />
              </View>
              <View style={styles.card}>
                {player.photoUrl ? (
                  <Image source={{ uri: player.photoUrl }} style={styles.photo} />
                ) : player.shirtNumber != null ? (
                  <Text style={styles.number}>{player.shirtNumber}</Text>
                ) : null}
                {player.photoUrl && player.shirtNumber != null ? (
                  <View style={styles.numberBadge}>
                    <Text style={styles.numberBadgeText}>{player.shirtNumber}</Text>
                  </View>
                ) : null}
                <View style={styles.roleBadgeWrap}>
                  <RoleBadge code={player.role} />
                </View>
              </View>
              <Text style={styles.name} numberOfLines={1}>
                {abbreviateName(player.name)}
              </Text>
              {player.scoreLabel ? <Text style={styles.score}>{player.scoreLabel}</Text> : null}
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    minWidth: 240,
    gap: spacing.xs,
  },
  title: {
    color: colors.foreground,
    fontSize: typography.fontSize.md,
    fontWeight: "700",
  },
  pitch: {
    width: "100%",
    aspectRatio: 3 / 4,
    backgroundColor: "#123c26",
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.25)",
    overflow: "hidden",
  },
  halfwayLine: {
    position: "absolute",
    left: 0,
    right: 0,
    top: "50%",
    height: 1,
    backgroundColor: "rgba(255,255,255,0.3)",
  },
  centerCircle: {
    position: "absolute",
    left: "39%",
    top: "43%",
    width: "22%",
    aspectRatio: 1,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.3)",
  },
  box: {
    position: "absolute",
    left: "27%",
    width: "46%",
    height: "16%",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.3)",
  },
  boxTop: {
    top: 0,
    borderTopWidth: 0,
  },
  boxBottom: {
    bottom: 0,
    borderBottomWidth: 0,
  },
  slot: {
    position: "absolute",
    transform: [{ translateX: -30 }, { translateY: -28 }],
    width: 60,
    alignItems: "center",
    gap: 1,
  },
  badgesRow: {
    minHeight: 12,
  },
  card: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.backgroundElevated,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
    alignItems: "center",
    justifyContent: "center",
  },
  number: {
    color: colors.foreground,
    fontSize: 11,
    fontWeight: "700",
  },
  roleBadgeWrap: {
    position: "absolute",
    bottom: -6,
    right: -6,
  },
  photo: {
    width: "100%",
    height: "100%",
    borderRadius: 15,
  },
  numberBadge: {
    position: "absolute",
    top: -6,
    left: -6,
    minWidth: 16,
    paddingHorizontal: 3,
    borderRadius: radius.pill,
    backgroundColor: colors.backgroundElevated,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
    alignItems: "center",
  },
  numberBadgeText: {
    color: colors.foreground,
    fontSize: 9,
    fontWeight: "700",
  },
  name: {
    color: "#fff",
    fontSize: 9,
    textAlign: "center",
  },
  score: {
    fontSize: 9,
    fontWeight: "700",
    color: colors.accentContrast,
    backgroundColor: "rgba(0,0,0,0.45)",
    borderRadius: radius.sm,
    paddingHorizontal: 3,
  },
});
