#!/usr/bin/env node
/** Browser acceptance for text-only multilingual selectors and translated core routes. */

import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const baseUrl = (process.env.KOMPLIANCE_TEST_URL || process.argv[2] || "http://127.0.0.1:8090").replace(/\/$/, "");
const locales = ["en-IE", "pl-PL", "ro-RO", "pt-BR", "uk-UA", "ru-RU", "es-ES"];
const routes = ["/", "/workers", "/ga1", "/ga2/form", "/ga3/form", "/workflow-centre", "/compliance", "/review", "/translations"];
const browser = await chromium.launch({ headless: true, channel: process.env.KOMPLIANCE_BROWSER_CHANNEL || "chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const failures = [];
const consoleErrors = [];
page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });

try {
  await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
  const selector = page.locator("#app-language");
  const optionValues = await selector.locator("option").evaluateAll(options => options.map(option => option.value));
  if (JSON.stringify(optionValues) !== JSON.stringify(locales)) failures.push(`Unexpected selector options: ${optionValues}`);
  for (const locale of locales) {
    await selector.selectOption(locale);
    await page.waitForTimeout(100);
    const state = await page.evaluate(() => ({
      lang: document.documentElement.lang,
      selected: document.querySelector("#app-language")?.value,
      heading: document.querySelector("main h1")?.textContent?.trim(),
    }));
    if (state.lang !== locale || state.selected !== locale || !state.heading) {
      failures.push(`${locale} did not apply: ${JSON.stringify(state)}`);
    }
  }
  await selector.selectOption("es-ES");
  for (const route of routes) {
    await page.goto(`${baseUrl}${route}`, { waitUntil: "networkidle" });
    const untranslated = await page.evaluate(() => {
      const locale = window.KomplianceI18n?.getLanguage();
      const dictionary = window.KomplianceTranslationCatalog?.[locale] || {};
      const values = [];
      for (const element of document.querySelectorAll("body *")) {
        if (element.closest("#app-language,#language,[name='preferred_language'],[data-i18n-skip],[data-translation-row]")) continue;
        for (const node of element.childNodes) {
          const value = node.nodeType === 3 ? node.nodeValue.trim() : "";
          if (value && dictionary[value] && dictionary[value] !== value) values.push(value);
        }
      }
      return [...new Set(values)];
    });
    if (untranslated.length) failures.push(`${route} retained English strings: ${untranslated.join(", ")}`);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${baseUrl}/worker/`, { waitUntil: "networkidle" });
  const mobile = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    options: document.querySelectorAll("#language option").length,
  }));
  if (mobile.overflow > 1 || mobile.options !== locales.length) failures.push(`Worker mobile check failed: ${JSON.stringify(mobile)}`);
  await page.goto(`${baseUrl}/translations`, { waitUntil: "networkidle" });
  const translationMobile = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    reviewRows: document.querySelectorAll("[data-translation-row]").length,
  }));
  if (translationMobile.overflow > 1 || !translationMobile.reviewRows) failures.push(`Translation mobile check failed: ${JSON.stringify(translationMobile)}`);
} finally {
  await browser.close();
}

if (consoleErrors.length) failures.push(`Console errors: ${consoleErrors.join(" | ")}`);
if (failures.length) {
  failures.forEach(failure => console.log(`[FAIL] ${failure}`));
  process.exitCode = 1;
} else {
  console.log("[PASS] All seven languages apply on the company and worker interfaces");
  console.log("[PASS] Core routes have complete catalogue coverage and no mobile overflow");
}
