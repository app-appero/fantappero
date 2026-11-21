import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import stylesCss from "./styles.css?raw";
import { applyDocumentColorScheme, THEME_COLOR_BY_SCHEME } from "./theme/colorScheme";

/**
 * iPhone, «Aggiungi alla schermata Home» (Rosario, 20/11): i tester con iPhone non possono
 * installare l'APK Android e usano il sito come app. Qui i pezzi che servono a iOS: meta e link
 * in index.html, manifest, icone opache e barra di stato del colore del tema.
 */

// Niente `new URL(..., import.meta.url)`: Vite lo riscrive come import di un asset.
const WEB_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const webRoot = (path: string) => resolve(WEB_DIR, path);

function readIndexHtml(): Document {
  return new DOMParser().parseFromString(readFileSync(webRoot("index.html"), "utf8"), "text/html");
}

function metaContent(doc: Document, name: string): string | null {
  return doc.querySelector(`meta[name="${name}"]`)?.getAttribute("content") ?? null;
}

type ManifestIcon = { src: string; sizes: string; type: string; purpose?: string };

function readManifest(): Record<string, unknown> & { icons: ManifestIcon[] } {
  return JSON.parse(readFileSync(webRoot("public/manifest.webmanifest"), "utf8"));
}

/** Larghezza, altezza e tipo di colore dall'intestazione IHDR di un PNG. */
function pngInfo(publicPath: string): { width: number; height: number; colorType: number } {
  const bytes = readFileSync(webRoot(`public${publicPath}`));
  expect(bytes.subarray(1, 4).toString("latin1")).toBe("PNG");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20), colorType: bytes[25] ?? -1 };
}

/** Tipo di colore 2 = RGB senza canale alfa: iOS non deve trovare trasparenze da riempire di nero. */
const PNG_RGB_OPAQUE = 2;

describe("index.html per l'app sulla schermata Home dell'iPhone", () => {
  it("apre a tutto schermo, con nome FantApperò e barra di stato leggibile", () => {
    const doc = readIndexHtml();
    expect(metaContent(doc, "apple-mobile-web-app-capable")).toBe("yes");
    expect(metaContent(doc, "mobile-web-app-capable")).toBe("yes");
    expect(metaContent(doc, "apple-mobile-web-app-title")).toBe("FantApperò");
    expect(["default", "black-translucent"]).toContain(
      metaContent(doc, "apple-mobile-web-app-status-bar-style"),
    );
  });

  it("arriva sotto notch e indicatore Home senza bloccare lo zoom con due dita", () => {
    const viewport = metaContent(readIndexHtml(), "viewport") ?? "";
    expect(viewport).toContain("viewport-fit=cover");
    expect(viewport).not.toMatch(/maximum-scale|user-scalable/);
  });

  it("ha theme-color per tema scuro e chiaro, uguali allo sfondo dell'header", () => {
    const metas = [...readIndexHtml().querySelectorAll('meta[name="theme-color"]')];
    const byMedia = Object.fromEntries(
      metas.map((meta) => [meta.getAttribute("media"), meta.getAttribute("content")]),
    );
    expect(byMedia).toEqual({
      "(prefers-color-scheme: dark)": THEME_COLOR_BY_SCHEME.dark,
      "(prefers-color-scheme: light)": THEME_COLOR_BY_SCHEME.light,
    });
  });

  it("collega manifest e icona per la schermata Home, file presenti in public/", () => {
    const doc = readIndexHtml();
    const manifestHref = doc.querySelector('link[rel="manifest"]')?.getAttribute("href");
    const touchIconHref = doc.querySelector('link[rel="apple-touch-icon"]')?.getAttribute("href");
    expect(manifestHref).toBe("/manifest.webmanifest");
    expect(touchIconHref).toBe("/apple-touch-icon.png");
    expect(existsSync(webRoot(`public${manifestHref}`))).toBe(true);
    expect(pngInfo(touchIconHref ?? "")).toEqual({ width: 180, height: 180, colorType: PNG_RGB_OPAQUE });
  });
});

describe("manifest.webmanifest", () => {
  it("descrive un'app standalone con i colori del tema scuro", () => {
    const manifest = readManifest();
    expect(manifest).toMatchObject({
      name: "FantApperò",
      short_name: "FantApperò",
      display: "standalone",
      start_url: "/",
      scope: "/",
      background_color: THEME_COLOR_BY_SCHEME.dark,
      theme_color: THEME_COLOR_BY_SCHEME.dark,
    });
  });

  it("ha icone 192 e 512 (più una maskable) opache e delle misure dichiarate", () => {
    const { icons } = readManifest();
    const sizes = icons.map((icon) => icon.sizes);
    expect(sizes).toContain("192x192");
    expect(sizes).toContain("512x512");
    expect(icons.some((icon) => icon.purpose?.split(" ").includes("maskable"))).toBe(true);
    for (const icon of icons) {
      expect(icon.type).toBe("image/png");
      const [width, height] = icon.sizes.split("x").map(Number);
      expect(pngInfo(icon.src)).toEqual({ width, height, colorType: PNG_RGB_OPAQUE });
    }
  });
});

describe("barra di stato con il tema scelto nell'app", () => {
  afterEach(() => {
    document.head.querySelectorAll('meta[name="theme-color"]').forEach((meta) => meta.remove());
  });

  it("allinea i meta theme-color al tema scelto, anche se il telefono usa l'altro", () => {
    for (const media of ["(prefers-color-scheme: dark)", "(prefers-color-scheme: light)"]) {
      const meta = document.createElement("meta");
      meta.name = "theme-color";
      meta.media = media;
      document.head.appendChild(meta);
    }
    const contents = () =>
      [...document.querySelectorAll('meta[name="theme-color"]')].map((meta) => meta.getAttribute("content"));

    applyDocumentColorScheme("light");
    expect(contents()).toEqual([THEME_COLOR_BY_SCHEME.light, THEME_COLOR_BY_SCHEME.light]);

    applyDocumentColorScheme("dark");
    expect(contents()).toEqual([THEME_COLOR_BY_SCHEME.dark, THEME_COLOR_BY_SCHEME.dark]);
  });
});

describe("styles.css per l'iPhone", () => {
  it("porta i campi a 16px, così Safari non ingrandisce la pagina al tocco", () => {
    const iosBlock = /@supports \(-webkit-touch-callout: none\) \{([\s\S]*?)\n\}/.exec(stylesCss)?.[1] ?? "";
    expect(iosBlock).toMatch(/select,\s*textarea,/);
    expect(iosBlock).toContain("font-size: 16px");
  });

  it("tiene la barra azioni della formazione sopra l'indicatore Home", () => {
    expect(stylesCss).toMatch(
      /\.fa-formation-layout__actions \{\s*bottom: calc\(var\(--fa-space-sm\) \+ env\(safe-area-inset-bottom, 0px\)\);/,
    );
  });
});
