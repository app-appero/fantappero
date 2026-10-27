import { DISPLAY_FONT } from "../../theme/fonts";
import { lazyStyles } from "../../theme/lazyStyles";
import type { H2HPlayerScore, H2HSideLineup } from "@fantappero/contracts";
import {
  MAX_AUTOMATIC_SUBSTITUTIONS,
  cleanDisplayName,
  computeCountdown,
  fantasyBadgesFromBonusMalus,
  substitutionBadges,
  formatFantasyPoints,
  formatCountdown,
  playerVoteState,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import { useEffect, useRef, useState, type ReactElement } from "react";
import { Animated, Easing, Pressable, StyleSheet, Text, View } from "react-native";
import { AthleteName } from "../../athletes/AthleteCard";
import { EventBadges } from "./EventBadges";

const { colors, spacing, typography, radius } = theme;

const ROLE_COLOR: Record<string, string> = { P: "#ffd23f", D: "#38bdf8", C: "#b58cff", A: "#ff6b8a" };

/** Orologio che scatta ogni secondo, per i countdown ai calci d'inizio. */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

function kickoffCountdown(player: H2HPlayerScore, now: number): string | null {
  if (!player.kickoffAt || player.fixtureStatusLabel !== "Da giocare") {
    return null;
  }
  const parts = computeCountdown(player.kickoffAt, new Date(now));
  if (!parts || (parts.days === 0 && parts.hours === 0 && parts.minutes === 0 && parts.seconds === 0)) {
    return null;
  }
  return `tra ${formatCountdown(parts)}`;
}

/** Bordo blu che pulsa: solo per chi sta giocando ora. */
function LivePulse() {
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
      style={[styles.livePulse, { opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.25, 1] }) }]}
    />
  );
}

export function MatchupPlayerRow({
  player,
  order,
  dim,
  compact,
  now,
  testIDPrefix,
}: {
  player: H2HPlayerScore;
  order?: number;
  dim?: boolean;
  compact?: boolean;
  now: number;
  testIDPrefix: string;
}) {
  const vote = playerVoteState(player);
  const countdown = vote.kind === "pending" ? kickoffCountdown(player, now) : null;
  const badges = [...fantasyBadgesFromBonusMalus(player.bonusMalus ?? []), ...substitutionBadges(player)];
  return (
    <View
      style={[
        styles.row,
        compact ? styles.rowCompact : null,
        dim ? styles.dim : null,
        vote.live ? styles.rowLive : null,
        vote.kind === "sv" ? styles.rowSv : null,
      ]}
      testID={`${testIDPrefix}-${player.athleteId}`}
    >
      {vote.live ? <LivePulse /> : null}
      {order != null ? <Text style={styles.order}>{order}°</Text> : null}
      <View style={[styles.role, compact ? styles.roleCompact : null, { backgroundColor: ROLE_COLOR[player.role] ?? colors.border }]}>
        <Text style={styles.roleText}>{player.role}</Text>
      </View>
      <View style={styles.body}>
        <View style={styles.nameLine}>
          <AthleteName plain athleteId={player.athleteId} style={compact ? styles.nameCompact : styles.name} numberOfLines={1}>
            {player.name}
          </AthleteName>
          <EventBadges badges={badges} size={12} />
        </View>
        {compact ? null : (
          <Text style={styles.team} numberOfLines={1}>
            {player.realTeamName ?? "Squadra reale non associata"}
          </Text>
        )}
        {countdown ? (
          <Text style={styles.countdown} testID={`${testIDPrefix}-countdown-${player.athleteId}`}>
            {countdown}
          </Text>
        ) : null}
      </View>
      {vote.label ? (
        <Text
          style={[
            styles.vote,
            vote.live ? styles.voteLive : null,
            vote.kind === "provisional" ? styles.voteProvisional : null,
            vote.kind === "sv" ? styles.voteSv : null,
          ]}
          testID={`${testIDPrefix}-score-${player.athleteId}`}
        >
          {vote.label}
        </Text>
      ) : null}
    </View>
  );
}

export function BenchTabs({ side, title, compact }: { side: H2HSideLineup; title: string; compact?: boolean }) {
  const [tab, setTab] = useState<"panchina" | "tribuna">("panchina");
  const now = useNow();
  const panchina = side.bench.slice(0, MAX_AUTOMATIC_SUBSTITUTIONS);
  const tribuna = side.bench.slice(MAX_AUTOMATIC_SUBSTITUTIONS);
  const rows = tab === "panchina" ? panchina : tribuna;
  const offset = tab === "panchina" ? 0 : MAX_AUTOMATIC_SUBSTITUTIONS;
  return (
    <View style={styles.tabs} testID={`matchup-bench-wrap-${title}`}>
      <View style={styles.tabBar}>
        {(
          [
            ["panchina", "Panchina", panchina.length],
            ["tribuna", "Tribuna", tribuna.length],
          ] as const
        ).map(([id, label, count]) => (
          <Pressable
            key={id}
            accessibilityRole="tab"
            accessibilityState={{ selected: tab === id }}
            onPress={() => setTab(id)}
            style={[styles.tab, tab === id ? styles.tabActive : null]}
            testID={`matchup-tab-${id}-${title}`}
          >
            <Text style={[styles.tabText, tab === id ? styles.tabTextActive : null]}>
              {label} {count}
            </Text>
          </Pressable>
        ))}
      </View>
      {compact ? null : (
        <Text style={styles.hint}>
          {tab === "panchina"
            ? `Entrano al massimo ${MAX_AUTOMATIC_SUBSTITUTIONS} panchinari, nell'ordine e a parità di ruolo.`
            : `Oltre i ${MAX_AUTOMATIC_SUBSTITUTIONS} cambi: restano fuori anche se disponibili.`}
        </Text>
      )}
      {rows.length === 0 ? (
        <Text style={styles.hint}>{tab === "panchina" ? "Nessun panchinaro." : "Nessuno in tribuna."}</Text>
      ) : (
        <View style={styles.list} testID={tab === "panchina" ? `matchup-bench-${title}` : `matchup-tribuna-${title}`}>
          {rows.map((player, index) => (
            <MatchupPlayerRow
              key={player.athleteId}
              player={player}
              order={offset + index + 1}
              dim={tab === "tribuna"}
              compact={compact}
              now={now}
              testIDPrefix="matchup-bench-player"
            />
          ))}
        </View>
      )}
    </View>
  );
}

const ROLE_ORDER = ["P", "D", "C", "A"];

/** Cella della vista affiancata: nome intero su una riga, voto o countdown sotto. */
function VersusCell({ player, dim, now }: { player: H2HPlayerScore | undefined; dim: boolean; now: number }) {
  if (!player) {
    return <View style={styles.cell} />;
  }
  const vote = playerVoteState(player);
  const countdown = vote.kind === "pending" ? kickoffCountdown(player, now) : null;
  const badges = [...fantasyBadgesFromBonusMalus(player.bonusMalus ?? []), ...substitutionBadges(player)];
  return (
    <View
      style={[
        styles.cell,
        styles.vcell,
        dim ? styles.dim : null,
        vote.live ? styles.rowLive : null,
        vote.kind === "sv" ? styles.rowSv : null,
      ]}
      testID={`matchup-versus-player-${player.athleteId}`}
    >
      {vote.live ? <LivePulse /> : null}
      <View style={[styles.role, styles.roleCompact, { backgroundColor: ROLE_COLOR[player.role] ?? colors.border }]}>
        <Text style={styles.roleText}>{player.role}</Text>
      </View>
      <View style={styles.vmain}>
      <View style={styles.nameLine}>
        <AthleteName fit plain athleteId={player.athleteId} style={styles.vname} numberOfLines={1}>
          {cleanDisplayName(player.name)}
        </AthleteName>
      </View>
      {badges.length > 0 ? (
        <View style={styles.badgeLine}>
          <EventBadges badges={badges} size={11} />
        </View>
      ) : null}
      {vote.label ? (
        <Text
          style={[
            styles.vote,
            styles.voteWhite,
            vote.live ? styles.voteLive : null,
            vote.kind === "provisional" ? styles.voteProvisional : null,
            vote.kind === "sv" ? styles.voteSv : null,
          ]}
          testID={`matchup-versus-score-${player.athleteId}`}
        >
          {vote.label}
        </Text>
      ) : countdown ? (
        <Text style={styles.vcd} testID={`matchup-versus-countdown-${player.athleteId}`}>
          {countdown}
        </Text>
      ) : null}
      </View>
    </View>
  );
}

function TeamHead({ side }: { side: H2HSideLineup }) {
  return (
    <View style={styles.head}>
      <View style={styles.headName}>
        <Text style={styles.headTitle} numberOfLines={1}>
          {side.teamName ?? side.displayName}
        </Text>
        <Text style={styles.headModule}>{side.module ?? ""}</Text>
      </View>
      <Text style={styles.headScore}>{formatFantasyPoints(side.totalScore)}</Text>
    </View>
  );
}

/** Vista affiancata: le rose complete dei due allenatori a confronto; i titolari sempre per ruolo. */
export function RosterVersus({ home, away }: { home: H2HSideLineup; away: H2HSideLineup }) {
  const now = useNow();
  const pair = (key: string, a: H2HPlayerScore | undefined, b: H2HPlayerScore | undefined, dim: boolean) => (
    <View style={styles.versusRow} key={key}>
      <VersusCell player={a} dim={dim} now={now} />
      <VersusCell player={b} dim={dim} now={now} />
    </View>
  );
  const rows: ReactElement[] = [];
  for (const role of ROLE_ORDER) {
    const left = home.starters.filter((p) => p.role === role);
    const right = away.starters.filter((p) => p.role === role);
    for (let i = 0; i < Math.max(left.length, right.length); i += 1) {
      rows.push(pair(`s-${role}-${i}`, left[i], right[i], false));
    }
  }
  const slots = MAX_AUTOMATIC_SUBSTITUTIONS;
  const total = Math.max(home.bench.length, away.bench.length);
  const benchRows: ReactElement[] = [];
  const tribRows: ReactElement[] = [];
  for (let i = 0; i < total; i += 1) {
    (i >= slots ? tribRows : benchRows).push(pair(`b-${i}`, home.bench[i], away.bench[i], i >= slots));
  }
  return (
    <View style={styles.versus} testID="matchup-versus">
      <View style={styles.versusRow}>
        <View style={styles.cell}>
          <TeamHead side={home} />
        </View>
        <View style={styles.cell}>
          <TeamHead side={away} />
        </View>
      </View>
      <Text style={styles.sectionTitle}>Titolari</Text>
      {rows}
      {benchRows.length > 0 ? <Text style={styles.sectionTitle}>Panchina</Text> : null}
      {benchRows}
      {tribRows.length > 0 ? <Text style={styles.sectionTitle}>Tribuna</Text> : null}
      {tribRows}
    </View>
  );
}

const styles = lazyStyles(() =>
  StyleSheet.create({
    list: { gap: spacing.xs },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.sm,
      padding: spacing.sm,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
      minWidth: 0,
    },
    rowCompact: { padding: 6, gap: 6, borderRadius: radius.md },
    dim: { opacity: 0.6 },
    rowLive: { borderColor: "#60a5fa", backgroundColor: "rgba(59,130,246,0.14)" },
    rowSv: { borderColor: "#c084fc", backgroundColor: "rgba(168,85,247,0.14)" },
    livePulse: {
      position: "absolute",
      top: -2,
      left: -2,
      right: -2,
      bottom: -2,
      borderRadius: radius.lg + 2,
      borderWidth: 2,
      borderColor: "#3b82f6",
    },
    order: { width: 26, color: colors.accent, fontFamily: DISPLAY_FONT },
    role: { width: 26, height: 26, borderRadius: 13, alignItems: "center", justifyContent: "center" },
    roleCompact: { width: 20, height: 20, borderRadius: 10 },
    roleText: { color: "#11162B", fontWeight: "800", fontSize: 11 },
    body: { flex: 1, minWidth: 0 },
    nameLine: { flexDirection: "row", alignItems: "center", gap: 4 },
    badgeLine: { flexDirection: "row", alignItems: "center", marginTop: 2 },
    name: { color: colors.foreground, fontWeight: "700", fontSize: typography.fontSize.md },
    nameCompact: { color: colors.foreground, fontWeight: "700", fontSize: typography.fontSize.sm, flexShrink: 1 },
    team: { color: colors.foregroundMuted, fontSize: typography.fontSize.xs },
    countdown: { color: colors.foregroundMuted, fontSize: 11, fontWeight: "700" },
    vote: {
      color: "#ffffff",
      backgroundColor: "rgba(255,255,255,0.12)",
      borderRadius: 999,
      paddingHorizontal: 8,
      paddingVertical: 2,
      fontSize: 12,
      fontWeight: "700",
      overflow: "hidden",
    },
    voteLive: { backgroundColor: "#2563eb", color: "#ffffff" },
    voteProvisional: { borderWidth: 1, borderStyle: "dashed", borderColor: "rgba(255,255,255,0.8)" },
    voteSv: { backgroundColor: "#7c3aed", color: "#fff" },
    tabs: { gap: spacing.xs },
    tabBar: {
      flexDirection: "row",
      gap: 4,
      padding: 4,
      borderRadius: 999,
      borderWidth: 1,
      borderColor: colors.border,
    },
    tab: { flex: 1, alignItems: "center", paddingVertical: 8, borderRadius: 999 },
    tabActive: { backgroundColor: colors.brand },
    tabText: { color: colors.foreground, fontWeight: "600", fontSize: typography.fontSize.sm },
    tabTextActive: { color: colors.onBrand },
    vcell: {
      gap: 3,
      paddingHorizontal: spacing.sm,
      paddingVertical: 6,
      borderRadius: radius.md,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
      flexDirection: "row",
      alignItems: "center",
    },
    vmain: { flex: 1, minWidth: 0, gap: 3, alignItems: "flex-start" },
    vname: { color: colors.foreground, fontWeight: "700", fontSize: typography.fontSize.sm },
    vcd: { color: "#c9d2f0", fontSize: 11, fontWeight: "700" },
    voteWhite: { color: "#ffffff" },
    versus: { gap: 6 },
    versusRow: { flexDirection: "row", alignItems: "stretch", gap: 4 },
    cell: { flex: 1, minWidth: 0 },
    mid: { width: 30, textAlign: "center", alignSelf: "center", color: colors.accent, fontFamily: DISPLAY_FONT },
    sectionTitle: {
      color: colors.foreground,
      fontSize: typography.fontSize.lg,
      fontStyle: "italic",
      fontWeight: "800",
      textTransform: "uppercase",
      marginTop: spacing.xs,
    },
    head: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 6,
      padding: spacing.sm,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
    },
    headName: { flex: 1, minWidth: 0 },
    headTitle: { color: colors.foreground, fontWeight: "700", fontSize: typography.fontSize.sm },
    headModule: { color: colors.foregroundMuted, fontSize: 10 },
    headScore: { color: colors.foreground, fontSize: 22, fontFamily: DISPLAY_FONT },
    hint: { color: colors.foregroundMuted, fontSize: typography.fontSize.xs },
  }),
);
