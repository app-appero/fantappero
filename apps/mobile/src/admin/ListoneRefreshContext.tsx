import type { AdminListoneRefreshProgress, AdminListoneRefreshResult } from "@fantappero/contracts";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  fetchActiveAdminListoneRefresh,
  fetchAdminListoneRefreshProgress,
  startAdminListoneRefresh,
} from "../api/admin";
import { ProgressBar } from "../components/ProgressBar";
import { useAuthSession } from "../session/DemoSessionContext";

export type ListoneRefreshProgress = {
  percent: number;
  stage: string;
  message: string;
};

export type ListoneRefreshContextValue = {
  refreshing: boolean;
  progress: ListoneRefreshProgress | null;
  seasonYear: number | null;
  startRefresh: (accessToken: string, seasonYear: number) => Promise<AdminListoneRefreshResult>;
};

const ListoneRefreshContext = createContext<ListoneRefreshContextValue | null>(null);

const POLL_INTERVAL_MS = 800;
const AMBIENT_CHECK_INTERVAL_MS = 15_000;

function isActiveStatus(status: string): boolean {
  return status === "queued" || status === "running";
}

async function pollJob(
  accessToken: string,
  jobId: string,
  onUpdate: (progress: AdminListoneRefreshProgress) => void,
): Promise<AdminListoneRefreshResult> {
  for (;;) {
    const progress = await fetchAdminListoneRefreshProgress(accessToken, jobId);
    onUpdate(progress);
    if (progress.status === "completed") {
      if (!progress.result) {
        throw new Error("Aggiornamento completato senza risultato.");
      }
      return progress.result;
    }
    if (progress.status === "failed") {
      throw new Error(progress.message || "Aggiornamento listone non riuscito.");
    }
    await new Promise((resolve) => {
      setTimeout(resolve, POLL_INTERVAL_MS);
    });
  }
}

/**
 * Owns the listone-refresh progress at the app root (not screen-local state)
 * so it survives navigation and shows up for every global operator's own
 * session — not just the one who tapped "Aggiorna" — since the refresh
 * itself can take several minutes against a rate-limited provider. Mirrors
 * apps/web/src/admin/ListoneRefreshContext.tsx.
 */
export function ListoneRefreshProvider({ children }: { children: ReactNode }) {
  const { accessToken, can } = useAuthSession();
  const [refreshing, setRefreshing] = useState(false);
  const [progress, setProgress] = useState<ListoneRefreshProgress | null>(null);
  const [seasonYear, setSeasonYear] = useState<number | null>(null);
  const inFlightRef = useRef<Promise<AdminListoneRefreshResult> | null>(null);

  const watch = useCallback(
    (token: string, jobId: string, year: number | null): Promise<AdminListoneRefreshResult> => {
      setRefreshing(true);
      setSeasonYear(year);
      const promise = pollJob(token, jobId, (next) =>
        setProgress({ percent: next.percent, stage: next.stage, message: next.message }),
      ).finally(() => {
        inFlightRef.current = null;
        setRefreshing(false);
        setProgress(null);
        setSeasonYear(null);
      });
      inFlightRef.current = promise;
      return promise;
    },
    [],
  );

  const startRefresh = useCallback(
    (token: string, year: number): Promise<AdminListoneRefreshResult> => {
      if (inFlightRef.current) {
        return inFlightRef.current;
      }
      setProgress({ percent: 0, stage: "queued", message: "Avvio in corso…" });
      const promise = startAdminListoneRefresh(token, year).then((job) =>
        watch(token, job.jobId, year),
      );
      inFlightRef.current = promise;
      return promise;
    },
    [watch],
  );

  // Ambient watcher: discovers a refresh some OTHER operator already started,
  // so this session's bar shows it too instead of staying blind to it.
  useEffect(() => {
    if (refreshing || !accessToken || !can(["global:operate"])) {
      return;
    }
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout>;

    async function tick() {
      try {
        const active = await fetchActiveAdminListoneRefresh(accessToken as string);
        if (!cancelled && active && isActiveStatus(active.status)) {
          void watch(accessToken as string, active.jobId, null);
          return;
        }
      } catch {
        // Best-effort ambient check — a transient failure just retries later.
      }
      if (!cancelled) {
        timeoutId = setTimeout(tick, AMBIENT_CHECK_INTERVAL_MS);
      }
    }

    void tick();
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [accessToken, can, refreshing, watch]);

  return (
    <ListoneRefreshContext.Provider value={{ refreshing, progress, seasonYear, startRefresh }}>
      {children}
    </ListoneRefreshContext.Provider>
  );
}

export function useListoneRefresh(): ListoneRefreshContextValue {
  const context = useContext(ListoneRefreshContext);
  if (!context) {
    throw new Error("useListoneRefresh must be used within ListoneRefreshProvider");
  }
  return context;
}

/**
 * Renders on top of every screen (mounted as a sibling of NavigationContainer
 * in App.tsx, not inside any one screen's tree — RN has no CSS `position:
 * fixed`, so this is the only way to stay visible regardless of which
 * screen is focused).
 */
export function GlobalListoneRefreshBar() {
  const { refreshing, progress, seasonYear } = useListoneRefresh();
  const insets = useSafeAreaInsets();

  if (!refreshing) {
    return null;
  }

  return (
    <View
      style={{
        position: "absolute",
        bottom: insets.bottom,
        left: 0,
        right: 0,
        zIndex: 999,
        paddingHorizontal: 8,
        paddingVertical: 4,
      }}
      testID="listone-refresh-global-bar"
    >
      <ProgressBar
        percent={progress?.percent ?? 0}
        label={`Listone${seasonYear ? ` ${seasonYear}` : ""}: ${
          progress?.message ?? "Aggiornamento in corso…"
        } (${progress?.percent ?? 0}%)`}
      />
    </View>
  );
}
