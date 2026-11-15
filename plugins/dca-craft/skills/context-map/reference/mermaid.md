# Mermaid diagram

Read when writing or changing the map's third section, `## Diagram`.

```markdown
## Diagram

\`\`\`mermaid
graph LR
  catalogue -->|OHS| lending
  membership ==>|Conformist| lending
  lending -.->|Event: LoanOverdue| notification
  paymentProvider -->|ACL| membership

  lending:::core
  catalogue:::supporting
  membership:::supporting
  notification:::generic

  classDef core stroke-width:3px;
  classDef supporting stroke-width:1px;
  classDef generic stroke:#888,color:#666;
\`\`\`
```

**Node style (subdomain type):**

| Subdomain | Mermaid classDef | Visual |
|---|---|---|
| Core | `stroke-width:3px` | thick border |
| Supporting | default | normal border |
| Generic | `stroke:#888,color:#666` | gray |

`stroke-dasharray` is reserved for Separate-Ways nodes, so subdomain type and pattern stay distinguishable.

**Edge style (pattern):**

| Pattern | Mermaid syntax | Visual |
|---|---|---|
| OHS / Customer-Supplier | `-->` | solid arrow |
| Published Language (events) | `-.->` | dotted arrow |
| Conformist | `==>` | thick arrow |
| ACL | `-->` with `\|ACL\|` label | solid + label |
| Partnership | `<-->` | bidirectional |
| Shared Kernel | `<-.->` | dashed bidirectional |
| Separate Ways | (omit edge) | — |
