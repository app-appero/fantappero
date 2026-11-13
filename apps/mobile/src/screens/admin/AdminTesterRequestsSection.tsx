import type { AdminTesterRequest } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";
import * as Linking from "expo-linking";
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { adminUiStyles as styles } from "../../admin/adminUiStyles";
import { whatsappUrl } from "../../admin/whatsapp";
import { decideTesterRequests, fetchTesterRequests } from "../../api/admin";
import { UiStatePanel } from "../../components/UiStatePanel";
import { getApiErrorMessage, useAuthSession } from "../../session/DemoSessionContext";
import { lazyStyles } from "../../theme/lazyStyles";

function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
}

/**
 * Richieste di accesso al pilota di chi non è ancora tester — porta mobile della scheda
 * «Richieste tester» di `apps/web/src/pages/AdminTesterRequestsPanel.tsx`.
 */
export function AdminTesterRequestsSection({
  onPendingCount,
}: {
  onPendingCount?: (count: number) => void;
}) {
  const { accessToken } = useAuthSession();
  const [requests, setRequests] = useState<AdminTesterRequest[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const apply = useCallback(
    (rows: AdminTesterRequest[]) => {
      setRequests(rows);
      onPendingCount?.(rows.filter((row) => row.status === "pending").length);
    },
    [onPendingCount],
  );

  useEffect(() => {
    if (!accessToken) {
      return;
    }
    void fetchTesterRequests(accessToken)
      .then((result) => apply(result.requests))
      .catch((cause: unknown) =>
        setError(getApiErrorMessage(cause, "Impossibile caricare le richieste.")),
      );
  }, [accessToken, apply]);

  async function decide(ids: string[], action: "approve" | "reject") {
    if (!accessToken || ids.length === 0) {
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await decideTesterRequests(accessToken, { ids, action });
      apply(result.requests);
      setSelected([]);
      setMessage(
        action === "approve"
          ? "Approvate: ora possono accedere con Google. Ricordati di aggiungerli al gruppo WhatsApp."
          : "Richieste rifiutate.",
      );
    } catch (cause) {
      setError(getApiErrorMessage(cause, "Operazione non riuscita."));
    } finally {
      setBusy(false);
    }
  }

  const visible = requests.filter((row) => showAll || row.status === "pending");
  const pendingIds = visible.filter((row) => row.status === "pending").map((row) => row.id);

  return (
    <View style={styles.listRow} testID="admin-tester-requests">
      <Text style={styles.sectionTitle}>Richieste di accesso</Text>
      <Text style={styles.meta}>
        Chi accede con Google senza essere tester può inviare nome, telefono e un messaggio.
        Approvare aggiunge l&apos;indirizzo ai tester.
      </Text>
      <View style={styles.rowActions}>
        <Pressable
          style={styles.secondaryButton}
          onPress={() => setShowAll((value) => !value)}
          testID="admin-requests-toggle"
        >
          <Text style={styles.secondaryButtonLabel}>
            {showAll ? "Solo in attesa" : "Mostra tutte"}
          </Text>
        </Pressable>
        {pendingIds.length > 1 ? (
          <Pressable
            style={styles.secondaryButton}
            onPress={() => setSelected(pendingIds)}
            testID="admin-requests-select-all"
          >
            <Text style={styles.secondaryButtonLabel}>Seleziona tutte</Text>
          </Pressable>
        ) : null}
      </View>
      {selected.length > 0 ? (
        <View style={styles.rowActions}>
          <Pressable
            style={[styles.button, busy && styles.disabled]}
            disabled={busy}
            onPress={() => void decide(selected, "approve")}
            testID="admin-requests-approve-selected"
          >
            <Text style={styles.buttonLabel}>{`Approva (${selected.length})`}</Text>
          </Pressable>
          <Pressable
            style={[styles.secondaryButton, busy && styles.disabled]}
            disabled={busy}
            onPress={() => void decide(selected, "reject")}
            testID="admin-requests-reject-selected"
          >
            <Text style={styles.secondaryButtonLabel}>{`Rifiuta (${selected.length})`}</Text>
          </Pressable>
        </View>
      ) : null}
      {error ? <UiStatePanel state="error" title="Errore" message={error} /> : null}
      {message ? <Text style={styles.meta}>{message}</Text> : null}
      {visible.length === 0 ? (
        <Text style={styles.meta} testID="admin-requests-empty">
          Nessuna richiesta in attesa.
        </Text>
      ) : (
        visible.map((row) => {
          const isPending = row.status === "pending";
          const isSelected = selected.includes(row.id);
          return (
            <View key={row.id} style={local.card} testID={`admin-request-${row.id}`}>
              <Pressable
                disabled={!isPending}
                onPress={() =>
                  setSelected((current) =>
                    current.includes(row.id)
                      ? current.filter((id) => id !== row.id)
                      : [...current, row.id],
                  )
                }
                accessibilityRole="checkbox"
                accessibilityState={{ checked: isSelected, disabled: !isPending }}
              >
                <Text style={local.name}>
                  {isPending ? (isSelected ? "☑ " : "☐ ") : ""}
                  {row.firstName} {row.lastName}
                </Text>
              </Pressable>
              <Text style={styles.meta}>{row.email}</Text>
              <Pressable
                onPress={() => void Linking.openURL(whatsappUrl(row.phone))}
                accessibilityRole="link"
                accessibilityLabel={`Apri WhatsApp con ${row.phone}`}
                testID={`admin-request-phone-${row.id}`}
              >
                <Text style={local.phone}>{`Tel. ${row.phone} · apri su WhatsApp`}</Text>
              </Pressable>
              {row.motivation ? <Text style={styles.meta}>{`«${row.motivation}»`}</Text> : null}
              <Text style={styles.meta}>
                {`${formatDate(row.createdAt)} · ${
                  isPending ? "in attesa" : row.status === "approved" ? "approvata" : "rifiutata"
                }`}
              </Text>
              {isPending ? (
                <View style={styles.rowActions}>
                  <Pressable
                    style={[styles.button, busy && styles.disabled]}
                    disabled={busy}
                    onPress={() => void decide([row.id], "approve")}
                    testID={`admin-request-approve-${row.id}`}
                  >
                    <Text style={styles.buttonLabel}>Approva</Text>
                  </Pressable>
                  <Pressable
                    style={[styles.secondaryButton, busy && styles.disabled]}
                    disabled={busy}
                    onPress={() => void decide([row.id], "reject")}
                    testID={`admin-request-reject-${row.id}`}
                  >
                    <Text style={styles.secondaryButtonLabel}>Rifiuta</Text>
                  </Pressable>
                </View>
              ) : null}
            </View>
          );
        })
      )}
    </View>
  );
}

const local = lazyStyles(() =>
  StyleSheet.create({
    card: {
      gap: 4,
      paddingVertical: 10,
      borderTopWidth: 1,
      borderTopColor: theme.colors.border,
    },
    name: { color: theme.colors.foreground, fontSize: 16, fontWeight: "700" },
    phone: { color: theme.colors.brand, fontSize: 14, textDecorationLine: "underline" },
  }),
);
