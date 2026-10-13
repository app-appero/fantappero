import { lazyStyles } from "../../theme/lazyStyles";
import type { MatchBadge, PitchPosition } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { LinearGradient } from "expo-linear-gradient";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { fonts } from "../../theme/fonts";
import { EventBadges } from "./EventBadges";
import { roleColor } from "./RoleBadge";

const { colors, spacing, typography, radius, foil } = theme;

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
  /** Id interno del calciatore, quando il pallino deve aprire la scheda. */
  athleteId?: string | null;
};

export type PitchViewProps = {
  title: string;
  players: readonly PitchPlayer[];
  positions: readonly PitchPosition[];
  testID?: string;
  /** Apre la scheda del calciatore toccando il pallino, se `athleteId` è presente. */
  onAthletePress?: (athleteId: string) => void;
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
export function PitchView({ title, players, positions, testID, onAthletePress }: PitchViewProps) {
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
              <PitchPlayerBody player={player} onAthletePress={onAthletePress} />
            </View>
          );
        })}
      </View>
    </View>
  );
}

function PitchPlayerBody({
  player,
  onAthletePress,
}: {
  player: PitchPlayer;
  onAthletePress?: (athleteId: string) => void;
}) {
  const content = (
    <>
      <View style={styles.badgesRow}>
        <EventBadges badges={player.badges ?? []} size={11} />
      </View>
      <LinearGradient colors={[...foil]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.foilFrame}>
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
          <View style={[styles.roleStrip, { backgroundColor: roleColor(player.role) }]}>
            <Text style={styles.roleStripText}>{player.role ?? "?"}</Text>
          </View>
        </View>
      </LinearGradient>
      <Text style={styles.name} numberOfLines={1}>
        {abbreviateName(player.name)}
      </Text>
      {player.scoreLabel ? <Text style={styles.score}>{player.scoreLabel}</Text> : null}
    </>
  );
  if (player.athleteId && onAthletePress) {
    const athleteId = player.athleteId;
    return (
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Apri scheda di ${player.name}`}
        onPress={() => onAthletePress(athleteId)}
        style={styles.player}
      >
        {content}
      </Pressable>
    );
  }
  return <View style={styles.player}>{content}</View>;
}

const styles = lazyStyles(() => StyleSheet.create({
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
    aspectRatio: 3 / 4.2,
    backgroundColor: colors.field,
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
    transform: [{ translateX: -30 }, { translateY: -34 }],
    width: 60,
    alignItems: "center",
    gap: 1,
  },
  player: {
    alignItems: "center",
    width: "100%",
    gap: 1,
  },
  badgesRow: {
    minHeight: 12,
  },
  foilFrame: {
    padding: 2,
    borderRadius: 10,
  },
  card: {
    width: 36,
    height: 46,
    borderRadius: 8,
    backgroundColor: "#0a0f24",
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "flex-end",
  },
  number: {
    color: "#f4f6ff",
    fontFamily: fonts.display,
    fontSize: 22,
    lineHeight: 24,
    paddingBottom: 2,
  },
  roleStrip: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    paddingVertical: 1,
    alignItems: "center",
  },
  roleStripText: {
    color: "#06121f",
    fontSize: 10,
    fontWeight: "700",
  },
  photo: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  numberBadge: {
    position: "absolute",
    bottom: 2,
    left: 2,
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
    fontSize: 10,
    fontWeight: "600",
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
}));
