// app/legacy.css (the landing, national and briefing pages) is scoped under `.legacy` so its element and class rules
// (`.card`, `h1`, `a`, ...) cannot leak into the Tailwind-styled pages. Root-level selectors map onto `.legacy`.
const isLegacy = (filePath) => !!filePath && filePath.replace(/\\/g, "/").endsWith("app/legacy.css");

export default {
  plugins: {
    tailwindcss: {},
    "postcss-prefix-selector": {
      prefix: ".legacy",
      transform(prefix, selector, prefixed, filePath) {
        if (!isLegacy(filePath)) return selector;
        const sel = selector.trim();
        // ":root[data-theme=dark] .x" and ":root:where(...) .x": keep the theme condition, put .legacy after it
        const root = sel.match(/^(:root(?:\[[^\]]+\]|:where\(.*\))?)\s+(.+)$/);
        if (root) return `${root[1]} ${prefix} ${root[2]}`;
        if (/^(html|body|:root)(\s*,\s*(html|body|:root))*$/.test(sel)) return prefix;
        if (sel === "*") return `${prefix}, ${prefix} *`;
        return prefixed;
      },
    },
    autoprefixer: {},
  },
};
