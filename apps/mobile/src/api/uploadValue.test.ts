import assert from "node:assert/strict";
import test from "node:test";
import { buildUploadFormValue } from "./uploadValue.ts";

test("il valore ha uri, nome e tipo per React Native e bytes per expo/fetch", async () => {
  const reads: string[] = [];
  const value = buildUploadFormValue(
    { uri: "file:///cache/ImagePicker/foto.jpg", name: "foto.jpg", type: "image/jpeg" },
    async (uri) => {
      reads.push(uri);
      return new Uint8Array([1, 2, 3]);
    },
  );
  assert.equal(value.uri, "file:///cache/ImagePicker/foto.jpg");
  assert.equal(value.name, "foto.jpg");
  assert.equal(value.type, "image/jpeg");
  // Il file non si legge finché non si invia.
  assert.deepEqual(reads, []);
  assert.deepEqual(Array.from(await value.bytes()), [1, 2, 3]);
  assert.deepEqual(reads, ["file:///cache/ImagePicker/foto.jpg"]);
});

test("senza tipo usa quello storico dei CSV importati", () => {
  const value = buildUploadFormValue({ uri: "file:///x/rose.csv", name: "rose.csv" }, async () => new Uint8Array());
  assert.equal(value.type, "text/csv");
});

test("un errore di lettura emerge solo all'invio", async () => {
  const value = buildUploadFormValue({ uri: "file:///x/manca.jpg", name: "manca.jpg", type: "image/jpeg" }, async () => {
    throw new Error("File non trovato");
  });
  await assert.rejects(() => value.bytes(), /File non trovato/);
});
