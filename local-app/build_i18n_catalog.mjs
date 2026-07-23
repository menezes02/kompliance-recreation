import fs from "node:fs/promises";
import vm from "node:vm";

const sourcePath = new URL("./static/i18n.js", import.meta.url);
const outputPath = new URL("./static/i18n-catalog.js", import.meta.url);
const source = await fs.readFile(sourcePath, "utf8");
const entriesMatch = source.match(/const entries = (\{[\s\S]*?\});\s*const generatedCatalog/);

if (!entriesMatch) {
  throw new Error("Unable to locate the English source catalogue in i18n.js");
}

const entries = vm.runInNewContext(`(${entriesMatch[1]})`);
const uiSourcePaths = [
  new URL("./static/app.js", import.meta.url),
  new URL("./static/worker.js", import.meta.url),
  new URL("./static/index.html", import.meta.url),
  new URL("./static/worker.html", import.meta.url),
];
const uiSource = (await Promise.all(uiSourcePaths.map(path => fs.readFile(path, "utf8")))).join("\n");
const rawCandidates = [];
for (const match of uiSource.matchAll(/>([^<>{}$]+)</g)) rawCandidates.push(match[1]);
for (const match of uiSource.matchAll(/"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)'/g)) {
  rawCandidates.push((match[1] ?? match[2]).replaceAll("\\n", " "));
}
for (const match of uiSource.matchAll(/"([^"\\\r\n]{2,180})"/g)) rawCandidates.push(match[1]);
for (const match of uiSource.matchAll(/'([^'\\\r\n]{2,180})'/g)) rawCandidates.push(match[1]);
const neverTranslate = new Set([
  "Kompliance", "Kompliance Local", "Kompliance Worker", "Kingscroft", "Kingscroft Developments",
  "English", "Polski", "Română", "Português (Brasil)", "Українська", "Русский", "Español",
  "BarcodeDetector", "GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "IMG",
]);
const isUiCandidate = value => {
  const text = value.replace(/\s+/g, " ").trim();
  if (neverTranslate.has(text) || text.length < 2 || text.length > 180 || !/[A-Za-z]/.test(text)) return false;
  if (/[<>{}=;$]/.test(text) || /^[/#.\[]/.test(text)) return false;
  if (/^(Content-Type|application\/|[a-z_][a-z0-9_-]*)$/.test(text)) return false;
  if (/^https?:|^api\/|\.pdf$|\.json$|\.html$/.test(text)) return false;
  return /[ A-Z.!?&/():+-]/.test(text);
};
const english = [...new Set([
  ...Object.keys(entries),
  ...rawCandidates.map(value => value.replace(/\s+/g, " ").trim()).filter(isUiCandidate),
])].sort((left, right) => left.localeCompare(right, "en"));
const targets = {
  "pl-PL": "pl",
  "ro-RO": "ro",
  "pt-BR": "pt",
  "uk-UA": "uk",
  "ru-RU": "ru",
  "es-ES": "es",
};
const batchSize = 18;

async function translateBatch(strings, target) {
  const body = strings.map((value, index) => `[[K${String(index).padStart(3, "0")}]] ${value}`).join("\n");
  const url = new URL("https://translate.googleapis.com/translate_a/single");
  url.searchParams.set("client", "gtx");
  url.searchParams.set("sl", "en");
  url.searchParams.set("tl", target);
  url.searchParams.set("dt", "t");
  url.searchParams.set("q", body);
  const response = await fetch(url, { headers: { "User-Agent": "Kompliance localisation build/1.0" } });
  if (!response.ok) throw new Error(`Translation request failed: ${response.status}`);
  const payload = await response.json();
  const translated = payload[0].map((part) => part[0]).join("");
  const matches = [...translated.matchAll(/\[\[K(\d{3})\]\]\s*([\s\S]*?)(?=\n\[\[K\d{3}\]\]|$)/g)];
  if (matches.length !== strings.length) {
    if (strings.length > 1) {
      const middle = Math.ceil(strings.length / 2);
      return [
        ...(await translateBatch(strings.slice(0, middle), target)),
        ...(await translateBatch(strings.slice(middle), target)),
      ];
    }
    if (strings.length === 1) {
      url.searchParams.set("q", strings[0]);
      const singleResponse = await fetch(url, { headers: { "User-Agent": "Kompliance localisation build/1.0" } });
      if (!singleResponse.ok) throw new Error(`Single translation request failed: ${singleResponse.status}`);
      const singlePayload = await singleResponse.json();
      return [singlePayload[0].map((part) => part[0]).join("").trim()];
    }
    throw new Error(`Expected ${strings.length} translated strings for ${target}, received ${matches.length}`);
  }
  return matches.map((match) => match[2].trim());
}

let existingCatalog = {};
try {
  const existingSource = await fs.readFile(outputPath, "utf8");
  const context = { window: {} };
  vm.runInNewContext(existingSource, context);
  existingCatalog = context.window.KomplianceTranslationCatalog || {};
} catch {}
const catalog = {};
for (const [locale, target] of Object.entries(targets)) {
  const dictionary = { ...(existingCatalog[locale] || {}) };
  const missing = english.filter(key => !dictionary[key]);
  const waveSize = batchSize * 6;
  for (let index = 0; index < missing.length; index += waveSize) {
    const wave = missing.slice(index, index + waveSize);
    const batches = [];
    for (let offset = 0; offset < wave.length; offset += batchSize) {
      batches.push(wave.slice(offset, offset + batchSize));
    }
    const translatedBatches = await Promise.all(batches.map(batch => translateBatch(batch, target)));
    batches.forEach((batch, batchIndex) => {
      batch.forEach((key, itemIndex) => { dictionary[key] = translatedBatches[batchIndex][itemIndex]; });
    });
    process.stdout.write(`\r${locale}: ${Math.min(index + wave.length, missing.length)}/${missing.length} new`);
  }
  process.stdout.write("\n");
  catalog[locale] = Object.fromEntries(english.map(key => [key, dictionary[key]]));
}

const header = `/* Generated static UI catalogue. English source remains authoritative; safety-critical wording requires native-speaker review. */\n`;
const output = `${header}window.KomplianceTranslationCatalog = Object.freeze(${JSON.stringify(catalog, null, 2)});\n`;
await fs.writeFile(outputPath, output, "utf8");
console.log(`Wrote ${outputPath.pathname} with ${english.length} strings in ${Object.keys(catalog).length} languages.`);
