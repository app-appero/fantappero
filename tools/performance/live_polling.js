// EP12-03 (Blocco D3, 27/09/2026) — scenari "live" e "mobile con polling".
//
// critical_flow.js prova le azioni che un utente fa attivamente (login,
// apri rosa, salva formazione...). Questo script prova invece qualcosa di
// diverso: le schermate che restano aperte in background e si aggiornano da
// sole — turno, dettaglio partita, calendario H2H, scontro diretto — usando
// esattamente gli stessi endpoint e gli stessi intervalli di polling reali
// del client (apps/web/src/matchday/useLive*Polling.ts: 15s per turno/H2H,
// 30s per il dettaglio partita).
//
// Due varianti, stesso ciclo di richieste, VU diversi:
//   - "live": pochi utenti (5) che seguono da vicino una partita in corso —
//     misura la latenza per richiesta sotto un carico leggero ma reale.
//   - "mobile_polling": molti client (50) con schermate aperte in
//     background — misura tenuta e throughput sotto polling sostenuto.
//
// Limite dichiarato: questo NON misura la latenza end-to-end "dato normalizzato
// → visibile al client" (richiederebbe orchestrare un aggiornamento reale dal
// provider sincronizzato con il polling, fuori portata di un load test k6).
// Misura invece che l'API risponda in tempo anche sotto il carico di polling
// che il pipeline a valle dovrebbe rispettare — un proxy, non la metrica esatta
// del piano ("aggiornamento live visibile entro 60s"); vedi
// docs/operations/performance_capacity.md per la nota completa.
//
// Secondo limite: i dati seminati per i test di carico non generano/confermano
// un calendario H2H, quindi /calendario/h2h risponde sempre null (caso valido,
// non un errore) e il ciclo non arriva mai a interrogare lo "scontro diretto"
// (slotId sempre assente) — questo scenario misura quindi solo turno/partita
// sotto carico, non lo scontro H2H.

import http from "k6/http";
import { check, fail, sleep } from "k6";

const testType = __ENV.PERF_TEST_TYPE || "live";
const baseUrl = __ENV.PERF_BASE_URL || "http://api-perf:8001";
const seedPath = __ENV.PERF_SEED_PATH || "/artifacts/runtime/seed.json";
const seed = JSON.parse(open(seedPath));

// Stessi intervalli reali usati dagli hook (BASE_INTERVAL_MS): turno/H2H 15s,
// dettaglio partita 30s. Un solo ciclo ogni 15s per VU è quindi un carico
// leggermente più severo del reale (worst case), mai una sottostima.
const CYCLE_INTERVAL_S = 15;

function scenarios(type) {
  if (type === "live") {
    return {
      live_watch: {
        executor: "constant-vus",
        vus: 5,
        duration: "3m",
        gracefulStop: "5s",
      },
    };
  }
  if (type === "mobile_polling") {
    return {
      background_polling: {
        executor: "constant-vus",
        vus: 50,
        duration: "3m",
        gracefulStop: "5s",
      },
    };
  }
  throw new Error(`Unsupported PERF_TEST_TYPE=${type}`);
}

export const options = {
  scenarios: scenarios(testType),
  thresholds: {
    checks: ["rate>0.99"],
    http_req_failed: ["rate<0.01"],
    "http_req_duration{endpoint:turn_detail}": ["p(95)<1500"],
    "http_req_duration{endpoint:fixture_detail}": ["p(95)<1500"],
    "http_req_duration{endpoint:h2h_calendar}": ["p(95)<1500"],
    "http_req_duration{endpoint:h2h_matchup}": ["p(95)<1500"],
  },
  noConnectionReuse: false,
  userAgent: `Fantappero-EP12-03-k6-live/${testType}`,
};

function json(response) {
  try {
    return response.json();
  } catch (_error) {
    return null;
  }
}

function headers(token) {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

function assertResponse(response, endpoint, predicate) {
  const ok = check(
    response,
    {
      [`${endpoint} returns expected data`]: (value) =>
        value.status === 200 && predicate(json(value)),
    },
    { endpoint },
  );
  if (!ok && __ENV.PERF_ABORT_ON_CHECK_FAILURE === "true") {
    fail(`${endpoint} failed with HTTP ${response.status}`);
  }
}

export function setup() {
  if (!Array.isArray(seed.users) || seed.users.length === 0) {
    fail(`No users in ${seedPath}`);
  }
  const sessions = seed.users.map((user, index) => {
    const loginResponse = http.post(
      `${baseUrl}/auth/login`,
      JSON.stringify({ email: user.email, password: seed.password }),
      { headers: { "Content-Type": "application/json" }, tags: { endpoint: "login" } },
    );
    const loginBody = json(loginResponse);
    const ok = check(loginResponse, {
      "login returns an access token": () =>
        loginResponse.status === 200 && Boolean(loginBody?.accessToken),
    });
    if (!ok) fail(`Login failed for synthetic account #${index + 1}`);
    const auth = { headers: headers(loginBody.accessToken) };

    // Scopre un turno/fixture e uno scontro H2H reali da seguire. Gira una
    // volta sola in setup(), non ad ogni iterazione: non pesa sul carico
    // misurato dagli scenari.
    const turnResponse = http.get(
      `${baseUrl}/leagues/${user.activeLeagueId}/turni/${user.activeRoundId}`,
      auth,
    );
    const turnBody = json(turnResponse);
    const fixtureId = turnBody?.fixtures?.[0]?.fixtureId ?? null;

    const h2hResponse = http.get(`${baseUrl}/leagues/${user.activeLeagueId}/calendario/h2h`, auth);
    const h2hBody = json(h2hResponse);
    const slotId = h2hBody?.rounds?.[0]?.matchups?.[0]?.slotId ?? null;

    return {
      ...user,
      accessToken: loginBody.accessToken,
      fixtureId,
      slotId,
    };
  });
  return { sessions };
}

export default function (data) {
  const session = data.sessions[(__VU - 1) % data.sessions.length];
  const requestParams = { headers: headers(session.accessToken) };

  let response = http.get(
    `${baseUrl}/leagues/${session.activeLeagueId}/turni/${session.activeRoundId}`,
    { ...requestParams, tags: { endpoint: "turn_detail" } },
  );
  assertResponse(response, "turn_detail", (body) => body?.id === session.activeRoundId);

  if (session.fixtureId) {
    response = http.get(
      `${baseUrl}/leagues/${session.activeLeagueId}/turni/${session.activeRoundId}/partite/${session.fixtureId}`,
      { ...requestParams, tags: { endpoint: "fixture_detail" } },
    );
    assertResponse(response, "fixture_detail", (body) => Boolean(body?.fixtureId));
  }

  response = http.get(`${baseUrl}/leagues/${session.activeLeagueId}/calendario/h2h`, {
    ...requestParams,
    tags: { endpoint: "h2h_calendar" },
  });
  // L'endpoint restituisce legittimamente null quando il calendario H2H
  // della lega non è ancora confermato (i dati seminati per i test di
  // carico non generano/confermano un calendario) — non è un errore.
  assertResponse(response, "h2h_calendar", (body) => body === null || Array.isArray(body?.rounds));

  if (session.slotId) {
    response = http.get(
      `${baseUrl}/leagues/${session.activeLeagueId}/calendario/scontri/${session.slotId}`,
      { ...requestParams, tags: { endpoint: "h2h_matchup" } },
    );
    assertResponse(response, "h2h_matchup", (body) => body?.slotId === session.slotId);
  }

  sleep(CYCLE_INTERVAL_S);
}

function metric(data, name) {
  return data.metrics[name]?.values || {};
}

export function handleSummary(data) {
  const endpointP95Ms = Object.fromEntries(
    ["turn_detail", "fixture_detail", "h2h_calendar", "h2h_matchup"].map((endpoint) => [
      endpoint,
      metric(data, `http_req_duration{endpoint:${endpoint}}`)["p(95)"] ?? null,
    ]),
  );
  const summary = {
    testType,
    generatedAt: new Date().toISOString(),
    checks: metric(data, "checks"),
    requests: metric(data, "http_reqs"),
    failed: metric(data, "http_req_failed"),
    duration: metric(data, "http_req_duration"),
    iterations: metric(data, "iterations"),
    thresholds: Object.fromEntries(
      Object.entries(data.metrics)
        .filter(([, value]) => value.thresholds)
        .map(([name, value]) => [name, value.thresholds]),
    ),
    endpointP95Ms,
  };
  const filename = `${__ENV.PERF_OUTPUT_DIR || "/artifacts/results"}/${testType}-summary.json`;
  const stdout = [
    `EP12-03 ${testType}: requests=${summary.requests.count || 0}`,
    `rate=${(summary.requests.rate || 0).toFixed(2)} req/s`,
    `failed=${((summary.failed.rate || 0) * 100).toFixed(3)}%`,
    `p95=${(summary.duration["p(95)"] || 0).toFixed(2)} ms`,
    `max=${(summary.duration.max || 0).toFixed(2)} ms`,
    `summary=${filename}`,
  ].join(" | ");
  return { stdout: `${stdout}\n`, [filename]: JSON.stringify(summary, null, 2) };
}
