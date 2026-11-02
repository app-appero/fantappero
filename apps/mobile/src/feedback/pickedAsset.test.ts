import assert from "node:assert/strict";
import test from "node:test";
import { resolveAssetMimeType, resolveAssetName, toPickedAttachment } from "./pickedAsset.ts";

test("usa il mimeType dichiarato quando è immagine o video", () => {
  assert.equal(resolveAssetMimeType({ uri: "file:///a", mimeType: "image/png" }), "image/png");
  assert.equal(resolveAssetMimeType({ uri: "file:///a", mimeType: "VIDEO/MP4" }), "video/mp4");
});

test("senza mimeType ricava il formato dall'estensione", () => {
  assert.equal(resolveAssetMimeType({ uri: "file:///x/clip.MOV" }), "video/quicktime");
  assert.equal(resolveAssetMimeType({ uri: "content://media/1", fileName: "foto.webp" }), "image/webp");
  assert.equal(resolveAssetMimeType({ uri: "file:///x/foto.png?v=2" }), "image/png");
});

test("un mimeType non multimediale viene ignorato", () => {
  assert.equal(resolveAssetMimeType({ uri: "file:///x/doc.pdf", mimeType: "application/pdf", type: "image" }), "image/jpeg");
});

test("senza altri indizi decide il tipo di asset", () => {
  assert.equal(resolveAssetMimeType({ uri: "content://media/42", type: "video" }), "video/mp4");
  assert.equal(resolveAssetMimeType({ uri: "content://media/42", type: "image" }), "image/jpeg");
});

test("il nome viene dal file, dall'uri o è un segnaposto", () => {
  assert.equal(resolveAssetName({ uri: "file:///x/a.jpg", fileName: " scatto.jpg " }, 0), "scatto.jpg");
  assert.equal(resolveAssetName({ uri: "file:///x/y/video.mp4?cache=1" }, 0), "video.mp4");
  assert.equal(resolveAssetName({ uri: "" }, 2), "allegato-3");
});

test("toPickedAttachment riporta peso sconosciuto come null", () => {
  assert.deepEqual(toPickedAttachment({ uri: "file:///a.png", mimeType: "image/png" }, 0), {
    uri: "file:///a.png",
    name: "a.png",
    mimeType: "image/png",
    sizeBytes: null,
  });
});
