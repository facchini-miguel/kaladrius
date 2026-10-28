// Kaladrius documentation site. Docs-only (the introduction is the home page), in English
// with Portuguese and Spanish translations under i18n/. The user manual is copied from
// ../docs/<language>/manual/ by scripts/manual.mjs, so the system's built-in help and this
// site share one source.
import { themes as prismThemes } from "prism-react-renderer";

const REPOSITORIO = "https://github.com/facchini-miguel/medical-system";

/** @type {import('@docusaurus/types').Config} */
export default {
  title: "Kaladrius",
  tagline: "Open-source clinic management for dentists and physicians",
  favicon: "img/favicon.svg",
  url: "https://kaladrius.dev",
  baseUrl: "/",
  onBrokenLinks: "throw",
  markdown: {
    // Plain .md files are CommonMark, not MDX: the manual has text like "<" and "{".
    format: "detect",
    hooks: { onBrokenMarkdownLinks: "throw" },
  },
  i18n: {
    defaultLocale: "en",
    locales: ["en", "pt-BR", "es"],
    localeConfigs: {
      en: { label: "English", htmlLang: "en" },
      "pt-BR": { label: "Português", htmlLang: "pt-BR" },
      es: { label: "Español", htmlLang: "es" },
    },
  },
  presets: [
    [
      "classic",
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          routeBasePath: "/",
          sidebarPath: "./sidebars.js",
          editUrl: ({ locale, docPath }) =>
            docPath.startsWith("manual/")
              ? `${REPOSITORIO}/edit/main/docs/${locale}/${docPath}`
              : `${REPOSITORIO}/edit/main/website/${
                  locale === "en" ? "docs" : `i18n/${locale}/docusaurus-plugin-content-docs/current`
                }/${docPath}`,
        },
        blog: false,
        theme: { customCss: "./src/css/custom.css" },
      }),
    ],
  ],
  themes: [
    [
      "@easyops-cn/docusaurus-search-local",
      { hashed: true, docsRouteBasePath: "/", indexBlog: false, language: ["en", "pt", "es"] },
    ],
  ],
  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      colorMode: { respectPrefersColorScheme: true },
      navbar: {
        title: "Kaladrius",
        logo: { alt: "Kaladrius", src: "img/logo.svg", srcDark: "img/logo-escuro.svg" },
        items: [
          { type: "docSidebar", sidebarId: "docs", position: "left", label: "Docs" },
          { to: "/manual/inicio", position: "left", label: "User manual" },
          { type: "localeDropdown", position: "right" },
          { href: REPOSITORIO, label: "GitHub", position: "right" },
        ],
      },
      footer: {
        style: "dark",
        links: [
          {
            title: "Docs",
            items: [
              { label: "Quick start", to: "/quick-start" },
              { label: "Installation", to: "/installation/requirements" },
              { label: "User manual", to: "/manual/inicio" },
            ],
          },
          {
            title: "Community",
            items: [
              { label: "GitHub", href: REPOSITORIO },
              { label: "Issues", href: `${REPOSITORIO}/issues` },
              { label: "Contributing", to: "/contributing" },
            ],
          },
        ],
        copyright: `Kaladrius — Apache License 2.0`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
        additionalLanguages: ["bash", "ini", "yaml"],
      },
    }),
};
