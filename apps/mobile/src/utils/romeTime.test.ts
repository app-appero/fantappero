import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { formatRomeDateTime } from "./romeTime.ts";

describe("formatRomeDateTime", () => {
  it("shows server times in Italian time whatever the device time zone", () => {
    // 14:24 UTC del 19/11 = 15:24 a Roma (ora solare, +1).
    const text = formatRomeDateTime("2026-11-19T14:24:00Z");
    assert.match(text, /19 nov 2026/);
    assert.match(text, /15:24/);
  });

  it("handles summer time and empty or invalid values", () => {
    assert.match(formatRomeDateTime("2026-07-01T18:00:00Z"), /20:00/);
    assert.equal(formatRomeDateTime(null), "—");
    assert.equal(formatRomeDateTime("non-una-data"), "non-una-data");
  });
});
