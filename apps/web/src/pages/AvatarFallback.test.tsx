import { AvatarWithFallback, MatchCard, StandingsTable, type StandingsRow } from "@fantappero/ui";
import { act, createElement, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

const BROKEN = "https://cdn.example.test/avatars/404.png";

const ROW: StandingsRow = {
  id: "row-1",
  position: 1,
  teamName: "Inter Mia",
  played: 3,
  points: 7,
  goalsFor: 5,
  goalsAgainst: 2,
  managerUserId: "user-1",
  managerDisplayName: "Giulia Rossi",
  managerAvatarUrl: BROKEN,
};

describe("Avatar con iniziali di riserva (immagine che non si carica)", () => {
  let container: HTMLDivElement;
  let root: Root;

  async function render(element: ReactElement) {
    await act(async () => {
      root.render(element);
    });
  }

  async function failAllImages() {
    const images = [...container.querySelectorAll("img")];
    expect(images.length).toBeGreaterThan(0);
    await act(async () => {
      for (const image of images) {
        image.dispatchEvent(new Event("error"));
      }
    });
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("classifica: se l'avatar va in 404 restano le iniziali, in tabella e nelle schede", async () => {
    await render(
      createElement(StandingsTable, {
        caption: "Classifica",
        positionLabel: "Pos",
        teamLabel: "Squadra",
        playedLabel: "G",
        pointsLabel: "Pt",
        goalsLabel: "Gol",
        rows: [ROW],
      }),
    );
    expect(container.querySelectorAll(`img[src="${BROKEN}"]`)).toHaveLength(2);

    await failAllImages();

    expect(container.querySelector("img")).toBeNull();
    const initials = [...container.querySelectorAll(".fa-standings-row__avatar--initials")].map(
      (node) => node.textContent,
    );
    expect(initials).toEqual(["G", "G"]);
  });

  it("sfida H2H: se l'avatar del fantallenatore va in 404 restano le iniziali", async () => {
    await render(
      createElement(MatchCard, {
        homeTeam: "Giulia Rossi",
        awayTeam: "Marco Bianchi",
        kickoffLabel: "Giornata 3",
        status: "scheduled",
        statusLabel: "In programma",
        homeAvatarUrl: BROKEN,
        awayAvatarUrl: BROKEN,
      }),
    );
    expect(container.querySelectorAll(".fa-match-card__person-avatar")).toHaveLength(2);

    await failAllImages();

    expect(container.querySelector("img")).toBeNull();
    const initials = [...container.querySelectorAll(".fa-match-card__avatar")].map((node) => node.textContent);
    expect(initials).toEqual(["GR", "MB"]);
  });

  it("un nome che inizia con un'emoji dà iniziali intere, non «�Ü» (QA 19-20/11)", async () => {
    await render(
      createElement("div", null, [
        createElement(StandingsTable, {
          key: "standings",
          caption: "Classifica",
          positionLabel: "Pos",
          teamLabel: "Squadra",
          playedLabel: "G",
          pointsLabel: "Pt",
          goalsLabel: "Gol",
          rows: [{ ...ROW, managerDisplayName: "😀 Ümit Kaya", managerAvatarUrl: null }],
        }),
        createElement(MatchCard, {
          key: "match",
          homeTeam: "😀 Ümit Kaya",
          awayTeam: "👩‍💻Ada Lovelace",
          kickoffLabel: "Giornata 3",
          status: "scheduled",
          statusLabel: "In programma",
        }),
      ]),
    );
    const standings = [...container.querySelectorAll(".fa-standings-row__avatar--initials")].map(
      (node) => node.textContent,
    );
    expect(standings).toEqual(["😀", "😀"]);
    const match = [...container.querySelectorAll(".fa-match-card__avatar")].map((node) => node.textContent);
    expect(match).toEqual(["😀Ü", "👩‍💻L"]);
  });

  it("riprova con un indirizzo nuovo dopo un errore", async () => {
    const fallback = createElement("span", { className: "initials" }, "GR");
    await render(createElement(AvatarWithFallback, { src: BROKEN, className: "avatar", fallback }));
    await failAllImages();
    expect(container.querySelector(".initials")).not.toBeNull();

    await render(createElement(AvatarWithFallback, { src: "https://cdn.example.test/ok.png", className: "avatar", fallback }));
    expect(container.querySelector("img.avatar")?.getAttribute("src")).toBe("https://cdn.example.test/ok.png");
    expect(container.querySelector(".initials")).toBeNull();
  });

  it("senza indirizzo mostra subito le iniziali", async () => {
    const fallback = createElement("span", { className: "initials" }, "GR");
    await render(createElement(AvatarWithFallback, { src: null, className: "avatar", fallback }));
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector(".initials")?.textContent).toBe("GR");
  });
});
