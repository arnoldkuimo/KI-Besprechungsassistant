import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const base = process.env.APP_URL || "http://localhost:8030";
const directory = path.resolve("../docs/screenshots");
await fs.mkdir(directory, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
async function widthCheck() {
  assert.equal(
    await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1),
    false,
    "Horizontaler Überlauf",
  );
}
async function shot(name) {
  await widthCheck();
  await page.screenshot({ path: path.join(directory, name), fullPage: true });
}
try {
  assert.equal((await (await page.request.get(`${base}/api/meta`)).json()).provider, "demo");
  await page.goto(base);
  await page.getByRole("button", { name: /Anna Weber/ }).click();
  await page.getByRole("button", { name: "Besprechung erfassen", exact: true }).last().click();
  const form = page.getByRole("dialog", { name: "Besprechung erfassen" });
  await form.getByRole("button", { name: "Beispiel", exact: true }).click();
  await shot("01-erfassung-desktop.png");
  await form.getByRole("button", { name: "Entwurf erstellen", exact: true }).click();
  await form.waitFor({ state: "hidden" });
  await page.getByRole("button", { name: "Zur Prüfung", exact: true }).waitFor({ timeout: 25000 });
  await shot("02-entwurf-desktop.png");
  await page.locator(".citation").first().click();
  await page.locator(".transcript .highlight").waitFor();
  await shot("03-quellenbeleg-desktop.png");
  await page.getByRole("button", { name: "Protokoll", exact: true }).click();
  await page.getByRole("button", { name: "Bearbeiten", exact: true }).click();
  const edit = page.getByRole("dialog");
  await edit.getByLabel("Inhalt", { exact: true }).first().fill("Vorbereitung des Kundentests im Team besprochen.");
  await edit.getByRole("button", { name: "Neue Version speichern" }).click();
  await edit.waitFor({ state: "hidden" });
  await page
    .getByText("Vorbereitung des Kundentests im Team besprochen.", {
      exact: true,
    })
    .waitFor();
  await page.getByRole("button", { name: "Zur Prüfung", exact: true }).click();
  await page.getByRole("button", { name: "Zur Prüfung", exact: true }).waitFor({ state: "hidden" });
  const title = "Vorbereitung des Kundentests";
  await page.getByLabel("Konto wechseln").selectOption("2");
  await page
    .getByRole("button")
    .filter({ has: page.getByText(title, { exact: true }) })
    .first()
    .click();
  await page.getByRole("button", { name: "Freigeben", exact: true }).click();
  const approval = page.getByRole("dialog");
  await approval.getByRole("checkbox").check();
  await approval.getByRole("button", { name: "Verbindlich freigeben" }).click();
  await approval.waitFor({ state: "hidden" });
  await page.locator(".approval").waitFor();
  const href = await page.getByRole("link", { name: "Protokoll", exact: true }).getAttribute("href");
  const exported = await page.request.get(new URL(href, base).href);
  assert.equal(exported.status(), 200);
  assert.match(await exported.text(), /Freigegeben von: Malik Brandt/);
  await shot("04-freigabe-desktop.png");
  await page.getByRole("button", { name: /^Aufgaben/ }).click();
  await page.getByLabel("Status A1", { exact: true }).selectOption("done");
  await page.waitForFunction(() => document.querySelector('select[aria-label="Status A1"]')?.value === "done");
  assert.equal(await page.getByLabel("Status A1", { exact: true }).inputValue(), "done");
  await shot("05-aufgaben-desktop.png");
  await page.setViewportSize({ width: 390, height: 844 });
  await shot("06-aufgaben-mobil.png");
  await page.getByRole("button", { name: "Protokoll", exact: true }).click();
  await shot("07-protokoll-mobil.png");
  await page.getByRole("button", { name: "Zur Übersicht" }).click();
  await shot("08-uebersicht-mobil.png");
  await page.getByLabel("Konto wechseln").selectOption("3");
  await page.getByText("Noch keine Besprechungen.", { exact: true }).waitFor();
  assert.equal(errors.length, 0, errors.join("\n"));
  console.log(
    "Browserprüfung erfolgreich: Erfassung, Bearbeitung, Quellen, Prüfung, Freigabe, Export, Aufgaben, Kontentrennung und mobile Ansicht.",
  );
} catch (error) {
  await page.screenshot({
    path: path.resolve("../.cache/browser-error.png"),
    fullPage: true,
  });
  console.error("Browserfehler:", errors);
  console.error("Dialoge:", await page.getByRole("dialog").allTextContents());
  throw error;
} finally {
  await browser.close();
}
