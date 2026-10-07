import type { FantasyTeamSummary, LiveLot, LiveTurnOrderEntry, MarketLiveNominationMode } from "@fantappero/contracts";
import {
  LIVE_SEAT_LEGEND,
  LIVE_SEAT_ME_COLOR,
  liveSeatCueColor,
  liveSeatCueLabel,
  liveSeatGlow,
  resolveLiveSeatCue,
} from "@fantappero/contracts";
import { lazyStyles } from "../../theme/lazyStyles";
import { theme } from "@fantappero/ui/theme";
import { StyleSheet, Text, View } from "react-native";

const { colors, typography } = theme;

function seatPosition(index: number, total: number): { left: `${number}%`; top: `${number}%` } {
  const angle = (index / total) * 2 * Math.PI - Math.PI / 2;
  const rx = 42;
  const ry = 38;
  return {
    left: `${50 + rx * Math.cos(angle)}%`,
    top: `${50 + ry * Math.sin(angle)}%`,
  };
}

/**
 * Mobile port of `apps/web/src/pages/auction-live/LiveAuctionTable.tsx`: le
 * squadre della lega "sedute" intorno a un tavolo ovale, con il lotto
 * corrente al centro. Stesse tre luci del web: blu = tu, oro = tocca
 * chiamare o ha chiamato, rosa = in testa al rilancio.
 */
export function LiveAuctionTable({
  teams,
  currentLot,
  secondsRemaining,
  currentTurnTeamId = null,
  myTeamId = null,
  nominationMode = null,
  turnOrder = [],
}: {
  teams: readonly FantasyTeamSummary[];
  currentLot: LiveLot | null;
  secondsRemaining: number | null;
  /** Modalità "a turno": id della squadra a cui tocca chiamare il prossimo lotto. */
  currentTurnTeamId?: string | null;
  myTeamId?: string | null;
  nominationMode?: MarketLiveNominationMode | null;
  turnOrder?: readonly LiveTurnOrderEntry[];
}) {
  if (teams.length === 0) {
    return null;
  }

  return (
    <View style={styles.wrap} testID="auction-live-table">
      <View style={styles.surface}>
        <View style={styles.center}>
          {currentLot ? (
            <>
              <Text style={styles.athlete}>{currentLot.athleteName}</Text>
              <Text style={styles.amount}>{currentLot.currentAmountCredits} crediti</Text>
              {secondsRemaining !== null ? (
                <Text style={styles.countdown} testID="auction-live-table-countdown">
                  {secondsRemaining}s
                </Text>
              ) : null}
            </>
          ) : (
            <Text style={styles.waiting}>In attesa del prossimo lotto…</Text>
          )}
        </View>
        {teams.map((team, index) => {
          const position = seatPosition(index, teams.length);
          const isMe = myTeamId === team.id;
          const cue = resolveLiveSeatCue({
            teamId: team.id,
            currentTurnTeamId,
            currentLot,
            nominationMode,
            turnOrder,
          });
          const cueColor = liveSeatCueColor(cue);
          const cueLabel = liveSeatCueLabel(cue, isMe);
          const nameColor = cueColor ?? (isMe ? LIVE_SEAT_ME_COLOR : "#fff");
          return (
            <View
              key={team.id}
              style={[styles.seat, { left: position.left, top: position.top }]}
              testID={`auction-live-seat-${team.id}`}
            >
              <View
                style={[
                  styles.avatar,
                  {
                    borderColor: cueColor ?? (isMe ? LIVE_SEAT_ME_COLOR : "rgba(255,255,255,0.35)"),
                    boxShadow: liveSeatGlow(cue, isMe),
                  },
                ]}
              >
                <Text style={styles.avatarLabel}>{team.name.charAt(0).toUpperCase()}</Text>
              </View>
              <Text style={[styles.seatName, { color: nameColor }]} numberOfLines={1}>
                {team.name}
              </Text>
              {isMe ? <Text style={styles.you}>Tu</Text> : null}
              {cueLabel ? (
                <Text style={[styles.cue, { color: cueColor ?? nameColor }]} numberOfLines={1}>
                  {cueLabel}
                </Text>
              ) : null}
            </View>
          );
        })}
      </View>
      <View style={styles.legend} testID="auction-live-seat-legend">
        {LIVE_SEAT_LEGEND.map((item) => (
          <View key={item.id} style={styles.legendItem}>
            <View style={[styles.legendSwatch, { backgroundColor: item.color }]} />
            <Text style={styles.legendLabel}>{item.label}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = lazyStyles(() => StyleSheet.create({
  wrap: {
    alignItems: "center",
    paddingVertical: 8,
    gap: 10,
  },
  surface: {
    position: "relative",
    width: "100%",
    maxWidth: 420,
    aspectRatio: 16 / 11,
    borderRadius: 999,
    backgroundColor: "#123c26",
    borderWidth: 6,
    borderColor: "#3a2416",
    alignItems: "center",
    justifyContent: "center",
  },
  center: {
    width: "55%",
    alignItems: "center",
  },
  athlete: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.bold,
    fontSize: typography.fontSize.md,
    textAlign: "center",
  },
  amount: {
    color: colors.accentContrast,
    fontWeight: typography.fontWeight.semibold,
    marginTop: 2,
    textAlign: "center",
  },
  countdown: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    marginTop: 2,
    textAlign: "center",
  },
  waiting: {
    color: colors.foregroundMuted,
    fontSize: typography.fontSize.sm,
    textAlign: "center",
  },
  seat: {
    position: "absolute",
    alignItems: "center",
    width: 84,
    marginLeft: -42,
    marginTop: -34,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.backgroundElevated,
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.35)",
  },
  avatarLabel: {
    color: colors.foreground,
    fontWeight: typography.fontWeight.bold,
  },
  seatName: {
    marginTop: 2,
    fontSize: 11,
    color: "#fff",
    textAlign: "center",
    fontWeight: typography.fontWeight.semibold,
  },
  you: {
    fontSize: 10,
    fontWeight: typography.fontWeight.bold,
    color: LIVE_SEAT_ME_COLOR,
    textTransform: "uppercase",
  },
  cue: {
    fontSize: 10,
    fontWeight: typography.fontWeight.semibold,
    textAlign: "center",
  },
  legend: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 12,
  },
  legendItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  legendSwatch: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  legendLabel: {
    color: colors.foregroundMuted,
    fontSize: 11,
  },
}));
