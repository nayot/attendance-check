// Shared by the class screen (display.js) and the student page (live.js).
window.LiveKit = (() => {
  // Categorical palette in fixed order (validated for colour-blind separation).
  const COLORS = ["#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#008a17", "#6a4ce2", "#ec4647"];
  // Text colour that reads on each tile colour.
  const INKS = ["#fff", "#191919", "#191919", "#191919", "#191919", "#fff", "#fff", "#fff"];
  // A shape per choice, so a choice is never told apart by colour alone.
  const SHAPES = [
    '<path d="M12 3 22 20H2Z"/>',                                // triangle
    '<path d="M12 2 22 12 12 22 2 12Z"/>',                       // diamond
    '<circle cx="12" cy="12" r="10"/>',                          // circle
    '<rect x="3" y="3" width="18" height="18" rx="1.5"/>',       // square
    '<path d="m12 2 2.9 6.6 7.1.7-5.4 4.7 1.6 7L12 17.3 5.8 21l1.6-7L2 9.3l7.1-.7Z"/>', // star
    '<path d="M12 2 21.5 8.9 17.9 20H6.1L2.5 8.9Z"/>',          // pentagon
    '<path d="M9 2h6v7h7v6h-7v7H9v-7H2V9h7Z"/>',                 // cross
    '<path d="M12 2 20.7 7v10L12 22 3.3 17V7Z"/>',               // hexagon
  ];
  const shape = (i, fill = "currentColor") =>
    `<svg class="shape" viewBox="0 0 24 24" aria-hidden="true" fill="${fill}">${SHAPES[i % SHAPES.length]}</svg>`;
  const t = (key, params = {}) =>
    ((window.I18N || {})[key] ?? key).replace(/\{(\w+)\}/g, (m, name) => params[name] ?? m);
  return { COLORS, INKS, shape, t };
})();
