import { describe, expect, it } from "vitest";
import { sourceText, labels, statuses } from "./types";

describe("Quellen und Status", () => {
  it("erhält vorhandene Sprecher und Zeitmarken", () => {
    expect(
      sourceText([
        { id: 1, speaker: "Anna", timestamp: "01:20", text: "Test beginnen." },
        { id: 2, speaker: null, timestamp: null, text: "Offene Notiz." },
      ]),
    ).toBe("[01:20] Anna: Test beginnen.\nOffene Notiz.");
  });
  it("führt alle Freigabestände getrennt", () => {
    expect(statuses.draft).not.toBe(statuses.approved);
    expect(labels.tasks).toBe("Aufgaben");
  });
});
