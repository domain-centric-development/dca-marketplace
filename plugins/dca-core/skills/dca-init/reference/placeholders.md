# Template placeholders

Part of the `dca-init` skill: the placeholders its templates carry, where each value comes from, and an
example.

| Placeholder | Source | Example |
|---|---|---|
| `{{basePackage}}` / `{{basePackagePath}}` | detected | `com.acme.shop` / `com/acme/shop` |
| `{{rootNamespace}}`, `{{solutionName}}` | detected | `Acme.Shop`, `AcmeShop` |
| `{{dcaJavaVersion}}`, `{{dcaDotnetVersion}}` | looked up at init time | `0.5.0` |
| `{{junitVersion}}`, `{{testSdkVersion}}`, `{{xunitVersion}}`, `{{xunitRunnerVersion}}`, `{{targetFramework}}` | looked up / detected | `5.11.4`, `net10.0` |
| `{{layoutCalls}}` | decisions B, D | `withIncomingSubpackage("in")`, `withUseCaseSuffix("ApplicationService")` |
| `{{ruleSets}}` | decision C | `cycles,layered,hexagonal,naming` |
| `{{noLayeredModuleYet}}` | detected: no `domain`/`application`/`adapter` package below the base package | `true` / `false` |
| `{{springModulithEnabled}}` | detected | `true` / `false` |
| `{{contextName}}`, `{{description}}`, `{{packageName}}` / `{{contextNamespace}}`, `{{contextClassName}}` | detected contexts | `Shopping Cart`, `com.acme.shop.cart`, `CartContext` |
| `{{productionProjects}}`, `{{assemblyAnchors}}` | detected (.NET) | `../../src/Acme.Shop.Cart/Acme.Shop.Cart.csproj`, `Cart.CartContext` |
| `{{contextMapPath}}` | decision F | `docs/architecture/context-map.md` |
| `{{verifyCommand}}` | build system | `./gradlew test-architecture` |
| `{{conventionsPath}}` | existing file or default | `.agents/dca/conventions.md` |
| `{{build}}`, `{{guard}}`, `{{glossary}}`, `{{map}}`, `{{browserTests}}`, `{{review}}`, `{{reviewSkills}}` | Phase 1 item 7 | `true`; `` `review-ddd`, `dca-audit` `` |
| `{{catalogPath}}` | decision G (`live catalog`) | `~/…/dca-knowledge-catalog/bundle` |
