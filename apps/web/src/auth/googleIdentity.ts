/** Minimal wrapper around Google Identity Services (GIS) — no npm SDK needed. */

const GIS_SCRIPT_SRC = "https://accounts.google.com/gsi/client";

type GoogleCredentialResponse = {
  credential: string;
};

type GoogleIdConfig = {
  client_id: string;
  callback: (response: GoogleCredentialResponse) => void;
};

type GoogleButtonOptions = {
  type?: "standard";
  theme?: "outline" | "filled_blue" | "filled_black";
  size?: "large" | "medium" | "small";
  text?: "signin_with" | "continue_with";
  shape?: "rectangular" | "pill";
  width?: number;
};

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: GoogleIdConfig) => void;
          renderButton: (parent: HTMLElement, options: GoogleButtonOptions) => void;
        };
      };
    };
  }
}

let scriptLoadPromise: Promise<void> | null = null;

function loadGisScript(): Promise<void> {
  if (window.google?.accounts?.id) {
    return Promise.resolve();
  }
  scriptLoadPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GIS_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Impossibile caricare Google Identity Services."));
    document.head.appendChild(script);
  });
  return scriptLoadPromise;
}

/** Loads GIS, then renders the official Google button into `container` with the given callback. */
export async function renderGoogleButton(
  container: HTMLElement,
  clientId: string,
  onIdToken: (idToken: string) => void,
): Promise<void> {
  await loadGisScript();
  const accountsId = window.google?.accounts.id;
  if (!accountsId) {
    throw new Error("Google Identity Services non disponibile.");
  }
  accountsId.initialize({
    client_id: clientId,
    callback: (response) => onIdToken(response.credential),
  });
  accountsId.renderButton(container, {
    type: "standard",
    theme: "outline",
    size: "large",
    text: "continue_with",
    shape: "rectangular",
  });
}
