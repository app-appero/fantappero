import http from "k6/http";
import { check, fail, sleep } from "k6";
import exec from "k6/execution";

const testType = __ENV.PERF_TEST_TYPE || "smoke";
const baseUrl = __ENV.PERF_BASE_URL || "http://api-perf:8001";
const seedPath = __ENV.PERF_SEED_PATH || "/artifacts/runtime/seed.json";
const seed = JSON.parse(open(seedPath));

function scenarios(type) {
  if (type === "smoke") {
    return {
      critical_flow: {
        executor: "constant-vus",
        vus: 1,
        duration: "15s",
        gracefulStop: "5s",
      },
    };
  }
  if (type === "steady") {
    return {
      critical_flow: {
        executor: "ramping-vus",
        stages: [
          { duration: "15s", target: 20 },
          { duration: "90s", target: 20 },
          { duration: "15s", target: 0 },
        ],
        gracefulRampDown: "5s",
      },
    };
  }
  if (type === "spike") {
    return {
      critical_flow: {
        executor: "ramping-vus",
        stages: [
          { duration: "10s", target: 20 },
          { duration: "15s", target: 60 },
          { duration: "30s", target: 20 },
          { duration: "10s", target: 0 },
        ],
        gracefulRampDown: "5s",
      },
    };
  }
  throw new Error(`Unsupported PERF_TEST_TYPE=${type}`);
}

const normalEndpointThresholds = {
  checks: ["rate>0.99"],
  "http_req_duration{endpoint:login}": ["p(95)<1000"],
  "http_req_duration{endpoint:league_read}": ["p(95)<750"],
  "http_req_duration{endpoint:roster_read}": ["p(95)<3000"],
  "http_req_duration{endpoint:lineup_read}": ["p(95)<2000"],
  "http_req_duration{endpoint:lineup_write}": ["p(95)<2000"],
  "http_req_duration{endpoint:results_read}": ["p(95)<750"],
  "http_req_duration{endpoint:standings_read}": ["p(95)<750"],
  "http_req_duration{endpoint:market_preview}": ["p(95)<750"],
  "http_req_duration{endpoint:market_history}": ["p(95)<750"],
};

const spikeEndpointThresholds = {
  checks: ["rate>0.98"],
  "http_req_duration{endpoint:login}": ["p(95)<1000"],
  "http_req_duration{endpoint:league_read}": ["p(95)<5000"],
  "http_req_duration{endpoint:roster_read}": ["p(95)<8000"],
  "http_req_duration{endpoint:lineup_read}": ["p(95)<8000"],
  "http_req_duration{endpoint:lineup_write}": ["p(95)<8000"],
  "http_req_duration{endpoint:results_read}": ["p(95)<5000"],
  "http_req_duration{endpoint:standings_read}": ["p(95)<5000"],
  "http_req_duration{endpoint:market_preview}": ["p(95)<5000"],
  "http_req_duration{endpoint:market_history}": ["p(95)<5000"],
};

export const options = {
  scenarios: scenarios(testType),
  thresholds: {
    ...(testType === "spike" ? spikeEndpointThresholds : normalEndpointThresholds),
    http_req_failed: [testType === "spike" ? "rate<0.02" : "rate<0.01"],
    http_req_duration: [
      testType === "spike" ? "p(95)<5000" : testType === "steady" ? "p(95)<1500" : "p(95)<750",
    ],
    http_reqs: [testType === "smoke" ? "rate>1" : testType === "steady" ? "rate>50" : "rate>40"],
    ...(testType === "spike"
      ? {
          "http_req_failed{phase:recovery}": ["rate<0.01"],
          "http_req_duration{phase:recovery}": ["p(95)<1500"],
        }
      : {}),
  },
  noConnectionReuse: false,
  userAgent: `Fantappero-EP12-03-k6/${testType}`,
};

function json(response) {
  try {
    return response.json();
  } catch (_error) {
    return null;
  }
}

function phase() {
  if (testType !== "spike") return testType;
  const elapsedSeconds = (Date.now() - exec.scenario.startTime) / 1000;
  if (elapsedSeconds < 10) return "baseline";
  if (elapsedSeconds < 25) return "spike";
  return "recovery";
}

function headers(token) {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

function assertResponse(response, endpoint, currentPhase, predicate) {
  const ok = check(
    response,
    {
      [`${endpoint} returns expected data`]: (value) =>
        value.status === 200 && predicate(json(value)),
    },
    { endpoint, phase: currentPhase },
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
    const response = http.post(
      `${baseUrl}/auth/login`,
      JSON.stringify({ email: user.email, password: seed.password }),
      { headers: { "Content-Type": "application/json" }, tags: { endpoint: "login" } },
    );
    const body = json(response);
    const ok = check(response, {
      "login returns an access token": () => response.status === 200 && Boolean(body?.accessToken),
    });
    if (!ok) fail(`Login failed for synthetic account #${index + 1}`);
    return { ...user, accessToken: body.accessToken };
  });
  return { sessions };
}

export default function (data) {
  const session = data.sessions[(__VU - 1) % data.sessions.length];
  const currentPhase = phase();
  const requestParams = { headers: headers(session.accessToken) };

  let response = http.get(`${baseUrl}/leagues/${session.activeLeagueId}`, {
    ...requestParams,
    tags: { endpoint: "league_read", phase: currentPhase },
  });
  assertResponse(
    response,
    "league_read",
    currentPhase,
    (body) => body?.id === session.activeLeagueId,
  );

  response = http.get(`${baseUrl}/leagues/${session.activeLeagueId}/rosa`, {
    ...requestParams,
    tags: { endpoint: "roster_read", phase: currentPhase },
  });
  assertResponse(response, "roster_read", currentPhase, (body) => body?.filledSlots === 35);

  response = http.get(
    `${baseUrl}/leagues/${session.activeLeagueId}/turni/${session.activeRoundId}/formazione`,
    { ...requestParams, tags: { endpoint: "lineup_read", phase: currentPhase } },
  );
  assertResponse(
    response,
    "lineup_read",
    currentPhase,
    (body) => body?.roundId === session.activeRoundId && body?.modificationAllowed === true,
  );

  // Writes are 20% of journeys; the payload is an idempotent update of the
  // already-seeded lineup, so runs are repeatable and do not consume players.
  if (__ITER % 5 === 0) {
    response = http.put(
      `${baseUrl}/leagues/${session.activeLeagueId}/turni/${session.activeRoundId}/formazione`,
      JSON.stringify(session.lineup),
      { ...requestParams, tags: { endpoint: "lineup_write", phase: currentPhase } },
    );
    assertResponse(
      response,
      "lineup_write",
      currentPhase,
      (body) => body?.lineup?.starters?.length === 11,
    );
  }

  response = http.get(
    `${baseUrl}/fantasy-scoring/rounds/${session.historicalRoundId}/risultati`,
    { ...requestParams, tags: { endpoint: "results_read", phase: currentPhase } },
  );
  assertResponse(
    response,
    "results_read",
    currentPhase,
    (body) => Array.isArray(body) && body.length > 0 && body[0].resultFinal === true,
  );

  response = http.get(`${baseUrl}/leagues/${session.historicalLeagueId}/classifica`, {
    ...requestParams,
    tags: { endpoint: "standings_read", phase: currentPhase },
  });
  assertResponse(
    response,
    "standings_read",
    currentPhase,
    (body) => Array.isArray(body) && body.length >= 2,
  );

  response = http.get(
    `${baseUrl}/leagues/${session.activeLeagueId}/mercato/svincolo/${session.releaseSlotIndex}/anteprima?causa=voluntary`,
    { ...requestParams, tags: { endpoint: "market_preview", phase: currentPhase } },
  );
  assertResponse(
    response,
    "market_preview",
    currentPhase,
    (body) => body?.slotIndex === session.releaseSlotIndex,
  );

  response = http.get(`${baseUrl}/leagues/${session.activeLeagueId}/mercato/storico`, {
    ...requestParams,
    tags: { endpoint: "market_history", phase: currentPhase },
  });
  assertResponse(response, "market_history", currentPhase, (body) => Array.isArray(body?.items));

  if (__ITER % 10 === 0) {
    response = http.get(`${baseUrl}/ready`, {
      tags: { endpoint: "readiness", phase: currentPhase },
    });
    assertResponse(response, "readiness", currentPhase, (body) => body?.status === "ok");
  }
  sleep(0.2);
}

function metric(data, name) {
  return data.metrics[name]?.values || {};
}

export function handleSummary(data) {
  const endpointP95Ms = Object.fromEntries(
    [
      "login",
      "league_read",
      "roster_read",
      "lineup_read",
      "lineup_write",
      "results_read",
      "standings_read",
      "market_preview",
      "market_history",
    ].map((endpoint) => [
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
    recovery:
      testType === "spike"
        ? {
            duration: metric(data, "http_req_duration{phase:recovery}"),
            failed: metric(data, "http_req_failed{phase:recovery}"),
          }
        : null,
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
