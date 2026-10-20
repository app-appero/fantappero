import type { FantasyRole, LeagueListoneEntry } from "@fantappero/contracts";
import { useEffect, useMemo, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { AthleteName } from "../athletes/AthleteCard";
import { marketUiStyles as styles } from "../market/marketUiStyles";
import { roleBadgeColors } from "../screens/roster/rosterHelpers";
import { AppTextInput as TextInput } from "./AppTextInput";
import { HScroll } from "./HScroll";

const PAGE_SIZE = 10;
const ROLE_PILLS: Array<{ value: "all" | FantasyRole; label: string }> = [
  { value: "all", label: "Tutti" },
  { value: "P", label: "Portieri" },
  { value: "D", label: "Difensori" },
  { value: "C", label: "Centrocampisti" },
  { value: "A", label: "Attaccanti" },
];

/**
 * Scelta di calciatori dal listone: mostra solo i disponibili (non in rosa a nessuno),
 * con ricerca, filtro per ruolo e pagine da 10. `single` seleziona un solo giocatore;
 * altrimenti l'ordine di selezione diventa il numero accanto al giocatore.
 */
export function AthleteChooser({
  entries,
  ownedAthleteIds,
  selected,
  onToggle,
  single = false,
  testID,
}: {
  entries: LeagueListoneEntry[];
  ownedAthleteIds: Set<string>;
  selected: string[];
  onToggle: (athleteId: string) => void;
  single?: boolean;
  testID?: string;
}) {
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<"all" | FantasyRole>("all");
  const [page, setPage] = useState(0);

  const available = useMemo(
    () => entries.filter((entry) => !ownedAthleteIds.has(entry.athleteId)),
    [entries, ownedAthleteIds],
  );
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("it-IT");
    return available.filter(
      (entry) =>
        (role === "all" || entry.effectiveRole === role) &&
        (!needle || `${entry.canonicalName} ${entry.clubName ?? ""}`.toLocaleLowerCase("it-IT").includes(needle)),
    );
  }, [available, query, role]);

  useEffect(() => {
    setPage(0);
  }, [query, role]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const rows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);
  const countFor = (value: "all" | FantasyRole) =>
    value === "all" ? available.length : available.filter((entry) => entry.effectiveRole === value).length;

  return (
    <View style={{ gap: 10 }} testID={testID}>
      <TextInput
        style={styles.input}
        value={query}
        onChangeText={setQuery}
        placeholder="Cerca per nome o squadra"
        autoCapitalize="none"
        autoCorrect={false}
        testID={testID ? `${testID}-search` : undefined}
      />
      <HScroll>
        {ROLE_PILLS.map((pill) => (
          <Pressable
            key={pill.value}
            style={[styles.pill, role === pill.value && styles.pillActive]}
            onPress={() => setRole(pill.value)}
            accessibilityState={{ selected: role === pill.value }}
          >
            <Text style={[styles.pillLabel, role === pill.value && styles.pillLabelActive]}>
              {`${pill.label} ${countFor(pill.value)}`}
            </Text>
          </Pressable>
        ))}
      </HScroll>
      <Text style={styles.meta}>
        {filtered.length} {filtered.length === 1 ? "giocatore disponibile" : "giocatori disponibili"}
        {selected.length > 0 && !single ? ` · ${selected.length} scelti` : ""}
      </Text>
      {rows.length === 0 ? <Text style={styles.meta}>Nessun giocatore disponibile con questi filtri.</Text> : null}
      <View style={{ gap: 6 }}>
        {rows.map((entry) => {
          const position = selected.indexOf(entry.athleteId) + 1;
          const active = position > 0;
          const dot = roleBadgeColors(entry.effectiveRole);
          return (
            <Pressable
              key={entry.athleteId}
              style={[styles.pickRow, active && styles.pickRowActive]}
              onPress={() => onToggle(entry.athleteId)}
              accessibilityRole={single ? "radio" : "checkbox"}
              accessibilityState={{ checked: active }}
              testID={testID ? `${testID}-${entry.athleteId}` : undefined}
            >
              <View style={[styles.checkBox, active && styles.checkBoxActive, single && { borderRadius: 11 }]}>
                {active ? <Text style={styles.pillLabelActive}>{single ? "✓" : position}</Text> : null}
              </View>
              <View style={[styles.proposalAvatar, { width: 30, height: 30, borderRadius: 15, backgroundColor: dot.backgroundColor }]}>
                <Text style={[styles.proposalAvatarLabel, { color: dot.color }]}>{entry.effectiveRole}</Text>
              </View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <AthleteName athleteId={entry.athleteId} style={styles.optionLabel} numberOfLines={1} plain>
                  {entry.canonicalName}
                </AthleteName>
                {entry.clubName ? <Text style={styles.meta}>{entry.clubName}</Text> : null}
              </View>
            </Pressable>
          );
        })}
      </View>
      {pageCount > 1 ? (
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <Pressable style={[styles.secondaryButton, { flex: 1 }, safePage === 0 && styles.disabled]} disabled={safePage === 0} onPress={() => setPage(safePage - 1)}>
            <Text style={styles.secondaryButtonLabel}>Precedente</Text>
          </Pressable>
          <Text style={styles.meta}>
            {safePage + 1} / {pageCount}
          </Text>
          <Pressable style={[styles.secondaryButton, { flex: 1 }, safePage >= pageCount - 1 && styles.disabled]} disabled={safePage >= pageCount - 1} onPress={() => setPage(safePage + 1)}>
            <Text style={styles.secondaryButtonLabel}>Successiva</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}
