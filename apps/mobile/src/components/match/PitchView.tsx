import { lazyStyles } from "../../theme/lazyStyles";
import type { MatchBadge, PitchPosition } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useEffect, useRef } from "react";
import { Animated, Easing, Image, Pressable, StyleSheet, Text, View } from "react-native";
import { TONE_COLOR, type ProbableTone } from "../../screens/formation/FormationParts";
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
  /** Id interno del calciatore, quando il pallino deve aprire la scheda. */
  athleteId?: string | null;
  /** Partita in corso: alone blu lampeggiante. */
  live?: boolean;
  /** `sv` = titolare senza voto (viola vivo); `provisional` = 6 LIVE provvisorio (bollino tratteggiato). */
  voteKind?: "sv" | "provisional" | "final" | null;
  /** Stato dalla formazione probabile: titolare/possibile panchina/espulso/indisponibile. */
  probable?: ProbableTone | null;
};

function probableCardStyle(tone: ProbableTone) {
  return {
    borderColor: TONE_COLOR[tone],
    borderWidth: 2,
    shadowColor: TONE_COLOR[tone],
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: tone === "unavailable" ? 0 : 1,
    shadowRadius: 8,
    elevation: tone === "unavailable" ? 0 : 6,
    opacity: tone === "unavailable" ? 0.7 : 1,
  } as const;
}

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

/** Alone blu che pulsa mentre la partita del giocatore è in corso. */
function LiveGlow({ color = "#3b82f6", fill = "rgba(59,130,246,0.25)" }: { color?: string; fill?: string }) {
  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 600, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 600, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);
  return (
    <Animated.View
      pointerEvents="none"
      style={[
        styles.liveGlow,
        { borderColor: color, backgroundColor: fill },
        {
          opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.25, 1] }),
          transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.18] }) }],
        },
      ]}
    />
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
      <View
        style={[
          styles.card,
          player.live ? styles.cardLive : null,
          player.voteKind === "sv" ? styles.cardSv : null,
          player.voteKind === "final" ? styles.cardFinal : null,
          player.probable ? probableCardStyle(player.probable) : null,
        ]}
      >
        {player.live ? <LiveGlow /> : null}
        {player.voteKind === "sv" ? <View pointerEvents="none" style={styles.svGlow} /> : null}
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
      <Text style={[styles.name, player.voteKind === "sv" ? styles.nameSv : null]} numberOfLines={1}>
        {abbreviateName(player.name)}
      </Text>
      {player.scoreLabel ? (
        <Text
          style={[
            styles.score,
            player.voteKind === "sv" ? styles.scoreSv : null,
            player.voteKind === "provisional" ? styles.scoreProvisional : null,
            player.voteKind === "final" ? styles.scoreFinal : null,
          ]}
        >
          {player.scoreLabel}
        </Text>
      ) : null}
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
    aspectRatio: 3 / 4,
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
    transform: [{ translateX: -30 }, { translateY: -28 }],
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
  cardLive: { borderColor: "#60a5fa", borderWidth: 2 },
  liveGlow: {
    position: "absolute",
    top: -5,
    left: -5,
    right: -5,
    bottom: -5,
    borderRadius: 20,
    borderWidth: 3,
    borderColor: "#3b82f6",
    backgroundColor: "rgba(59,130,246,0.25)",
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
  svGlow: {
    position: "absolute",
    top: -4,
    left: -4,
    right: -4,
    bottom: -4,
    borderRadius: 19,
    borderWidth: 3,
    borderColor: "#a855f7",
    backgroundColor: "rgba(168,85,247,0.25)",
  },
  cardSv: { borderColor: "#c084fc", borderWidth: 2 },
  cardFinal: {
    borderColor: "#ffffff",
    borderWidth: 3,
    shadowColor: "#ffffff",
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 8,
    elevation: 6,
  },
  scoreFinal: { backgroundColor: "#ffffff", color: "#11162B" },
  nameSv: {
    backgroundColor: "#7c3aed",
    borderRadius: 999,
    paddingHorizontal: 5,
    overflow: "hidden",
  },
  scoreSv: { backgroundColor: "#7c3aed", color: "#fff" },
  scoreProvisional: {
    backgroundColor: "#2563eb",
    color: "#fff",
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: "rgba(255,255,255,0.8)",
  },
  score: {
    fontSize: 9,
    fontWeight: "700",
    color: "#ffffff",
    backgroundColor: "rgba(0,0,0,0.45)",
    borderRadius: radius.sm,
    paddingHorizontal: 3,
  },
}));
