// Copies the user manual from ../docs/<language>/manual/ into the site, in reading order
// (the same order as apps/ajuda/documentos.py). The copies are generated and ignored by Git.
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = dirname(dirname(fileURLToPath(import.meta.url)));
const DOCS = join(SITE, "..", "docs");
const MANUAL = ["inicio", "agenda", "pacientes", "orcamentos", "rechamadas", "financeiro", "equipe", "clinica", "privacidade"];
const DESTINOS = {
  en: join(SITE, "docs", "manual"),
  "pt-BR": join(SITE, "i18n", "pt-BR", "docusaurus-plugin-content-docs", "current", "manual"),
  es: join(SITE, "i18n", "es", "docusaurus-plugin-content-docs", "current", "manual"),
};

for (const [idioma, destino] of Object.entries(DESTINOS)) {
  rmSync(destino, { recursive: true, force: true });
  mkdirSync(destino, { recursive: true });
  MANUAL.forEach((pagina, posicao) => {
    const texto = readFileSync(join(DOCS, idioma, "manual", `${pagina}.md`), "utf8");
    writeFileSync(join(destino, `${pagina}.md`), `---\nsidebar_position: ${posicao + 1}\n---\n\n${texto}`);
  });
}
console.log(`Manual copied: ${MANUAL.length} pages × ${Object.keys(DESTINOS).length} languages.`);
