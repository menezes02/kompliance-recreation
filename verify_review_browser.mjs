#!/usr/bin/env node
/**
 * Read-only browser acceptance for the Review & Acceptance Centre.
 *
 * Run against an authentication-disabled local validation server, or set:
 * KOMPLIANCE_TEST_EMAIL and KOMPLIANCE_TEST_PASSWORD for an authorised test admin.
 */

import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const baseUrl = (process.env.KOMPLIANCE_TEST_URL || process.argv[2] || "http://127.0.0.1:8090").replace(/\/$/, "");
const browser = await chromium.launch({
  headless: true,
  channel: process.env.KOMPLIANCE_BROWSER_CHANNEL || "chrome",
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const consoleErrors = [];
const pageErrors = [];
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => pageErrors.push(error.message));

const checks = [];
const check = (name, passed, detail = "") => checks.push({ name, passed: Boolean(passed), detail });

try {
  const response = await page.goto(`${baseUrl}/review`, { waitUntil: "networkidle" });
  check("review_route_http_success", response?.ok(), `HTTP ${response?.status()}`);

  const loginForm = page.locator("#auth-form");
  if (await loginForm.isVisible().catch(() => false)) {
    const email = process.env.KOMPLIANCE_TEST_EMAIL || "";
    const password = process.env.KOMPLIANCE_TEST_PASSWORD || "";
    if (!email || !password) {
      throw new Error("The target requires login. Set KOMPLIANCE_TEST_EMAIL and KOMPLIANCE_TEST_PASSWORD for an authorised test administrator.");
    }
    await loginForm.locator('input[name="email"]').fill(email);
    await loginForm.locator('input[name="password"]').fill(password);
    await Promise.all([
      page.waitForLoadState("networkidle"),
      loginForm.getByRole("button", { name: /sign in/i }).click(),
    ]);
    await page.goto(`${baseUrl}/review`, { waitUntil: "networkidle" });
  }

  const heading = page.getByRole("heading", { name: "Review & acceptance", level: 1 });
  check("review_heading_visible", await heading.isVisible());
  check("readiness_checks_rendered", (await page.locator(".review-check").count()) >= 10);
  check("acceptance_form_visible", await page.locator("#review-acceptance-form").isVisible());
  check("email_diagnostic_form_visible", await page.locator("#review-email-test-form").isVisible());
  check("evidence_export_available", await page.locator("#review-export").isVisible());
  check("print_review_available", await page.locator("#review-print").isVisible());

  const originalProtectedCopy = await page.locator(".sidebar-footer").innerText();
  check("read_only_boundary_visible", /read-only|isolated/i.test(originalProtectedCopy), originalProtectedCopy);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: "networkidle" });
  const mobileMetrics = await page.evaluate(() => ({
    viewport: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  check(
    "mobile_layout_has_no_page_overflow",
    mobileMetrics.scrollWidth <= mobileMetrics.viewport + 1,
    JSON.stringify(mobileMetrics),
  );
  check("mobile_review_heading_visible", await page.getByRole("heading", { name: "Review & acceptance", level: 1 }).isVisible());
  check("no_console_errors", consoleErrors.length === 0, consoleErrors.join(" | "));
  check("no_page_errors", pageErrors.length === 0, pageErrors.join(" | "));

  if (process.env.KOMPLIANCE_BROWSER_SCREENSHOT) {
    await page.screenshot({ path: process.env.KOMPLIANCE_BROWSER_SCREENSHOT, fullPage: true });
  }
} finally {
  await browser.close();
}

for (const item of checks) {
  console.log(`[${item.passed ? "PASS" : "FAIL"}] ${item.name}${item.detail ? ` — ${item.detail}` : ""}`);
}
if (!checks.length || checks.some((item) => !item.passed)) process.exitCode = 1;
