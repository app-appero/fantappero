import type { FantasyTeamSummary, LiveLot } from "@fantappero/contracts";
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
 * corrente al centro.
 */
export function LiveAuctionTable({
  teams,
  currentLot,
  secondsRemaining,
  currentTurnTeamId = null,
}: {
  teams: readonly FantasyTeamSummary[];
  currentLot: LiveLot | null;
  secondsRemaining: number | null;
  /** Modalità "a turno": id della squadra a cui tocca chiamare (null altrimenti). */
  currentTurnTeamId?: string | null;
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
          const isLeader = currentLot?.currentLeaderTeamId === team.id;
          const isOnTurn = !isLeader && currentTurnTeamId === team.id;
          return (
            <View
              key={team.id}
              style={[styles.seat, { left: position.left, top: position.top }]}
              testID={`auction-live-seat-${team.id}`}
            >
              <View
                style={[
                  styles.avatar,
                  isLeader && styles.avatarLeading,
                  isOnTurn && styles.avatarOnTurn,
                ]}
              >
                <Text style={styles.avatarLabel}>{team.name.charAt(0).toUpperCase()}</Text>
              </View>
              <Text style={[styles.seatName, isLeader && styles.seatNameLeading]} numberOfLines={1}>
                {team.name}
              </Text>
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: "center",
    paddingVertical: 8,
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
    width: 72,
    marginLeft: -36,
    marginTop: -28,
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
  avatarLeading: {
    borderColor: colors.accent,
  },
  avatarOnTurn: {
    borderColor: "#fff",
    borderStyle: "dashed",
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
  },
  seatNameLeading: {
    color: colors.accent,
    fontWeight: typography.fontWeight.bold,
  },
});
