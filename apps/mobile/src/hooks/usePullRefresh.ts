import { useCallback, useState } from "react";

/** Stato "tira per aggiornare": esegue i caricamenti dati e mostra lo spinner finché finiscono. */
export function usePullRefresh(...loaders: Array<() => unknown | Promise<unknown>>) {
  const [refreshing, setRefreshing] = useState(false);
  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await Promise.all(loaders.map((load) => Promise.resolve(load()).catch(() => undefined)));
    } finally {
      setRefreshing(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, loaders);
  return { refreshing, onRefresh };
}
