/**
 * Valore da mettere in un `FormData` per un file locale dell'app.
 *
 * Con Expo 58 la `fetch` globale è quella di Expo (`expo/fetch`), il cui convertitore di `FormData`
 * NON accetta il formato classico di React Native `{ uri, name, type }`: lancia «Unsupported
 * FormDataPart implementation» e la richiesta fallisce senza arrivare al server (la nostra rete
 * la mostra come «Connessione non disponibile»). Senza file la richiesta funziona, per questo il
 * difetto compariva solo allegando qualcosa. Expo vuole un valore che sappia dare i propri byte
 * (`bytes()`) e che abbia `name` e `type`.
 *
 * L'oggetto qui sotto ha tutto: `bytes` per `expo/fetch`, `uri` per la `fetch` classica di React
 * Native, quindi funziona con entrambe.
 */
export type LocalUploadFile = { uri: string; name: string; type?: string };

export type UploadFormValue = {
  uri: string;
  name: string;
  type: string;
  bytes: () => Promise<Uint8Array>;
};

/**
 * @param readBytes legge il file per intero (in produzione `new File(uri).bytes()` di
 * `expo-file-system`). Si chiama solo al momento dell'invio, non quando si aggiunge il valore.
 */
export function buildUploadFormValue(
  file: LocalUploadFile,
  readBytes: (uri: string) => Promise<Uint8Array>,
): UploadFormValue {
  return {
    uri: file.uri,
    name: file.name,
    type: file.type ?? "text/csv",
    bytes: () => readBytes(file.uri),
  };
}
