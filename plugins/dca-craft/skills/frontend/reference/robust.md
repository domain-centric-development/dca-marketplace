# Robust by construction

The detail of the skill's section 13.

- **Text goes in as text.** Never bypass the stack's escaping with data: `th:utext`, `Html.Raw`, `|safe`, `!{}`,
  `dangerouslySetInnerHTML`, `v-html`, `{@html}`, `innerHTML` are each reviewed and sanitised.
- **A strict Content-Security-Policy** where the project controls headers: scripts by nonce or hash, no `eval`;
  data never in a `style` attribute — pass it as a custom property the component reads.
- **No third party at run time** unless the project chose it: fonts and images are served by the application.
- **Progressive enhancement** on server-rendered stacks: links and forms work before the script loads; the script
  improves, it does not enable.
- **Performance basics**: images sized and lazy below the fold, fonts as `woff2` with `font-display: swap`, no
  layout shift from late content.
