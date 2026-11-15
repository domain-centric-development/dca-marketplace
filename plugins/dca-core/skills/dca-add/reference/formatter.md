# formatter

The procedure for `dca-add formatter`.

One formatting run over the whole code base at setup, then the two commands. **No ratchet** (no `ratchetFrom`):
after the one run the formatter only touches what the last change wrote, so a stage limited to its own files can
run the fix command.

1. **Pick with the user.** Existing config (`.editorconfig`, IDE profile, checkstyle) decides the style; a style
   the caller hands over (`dca-new` asks before the skeleton) is the answer — don't ask again.
   - Gradle: Spotless `com.diffplug.spotless` (Gradle Plugin Portal):
     `spotless { java { <style>(); removeUnusedImports(); trimTrailingWhitespace(); endWithNewline() } }`,
     style `googleJavaFormat()` / `palantirJavaFormat()` / `eclipse()`. `spotlessCheck` joins `check` itself.
   - Maven: `com.diffplug.spotless:spotless-maven-plugin`, same `<java>` steps; `check` bound to `verify` where
     the user wants the build to fail on it.
   - .NET: `dotnet format` (SDK), rules from `.editorconfig`; none → `dotnet new editorconfig`, review its
     severities with the user (they decide what `--verify-no-changes` reports).
2. **Format everything once**, before any other change: `./gradlew spotlessApply` / `./mvnw spotless:apply` /
   `dotnet format`. Build and run every suite (no behaviour change). One commit with only formatting (the person
   commits); add it to `.git-blame-ignore-revs` where that file exists.
3. **Commands**, recorded in `dca.profile.yaml` as `format:` and `formatFix:` (a pipeline profile carries the
   same keys: gate and hook run the check, code-writing stages the fix):

   | Build | Check (`format:`) | Fix (`formatFix:`) |
   |---|---|---|
   | Gradle | `./gradlew spotlessCheck` | `./gradlew spotlessApply` |
   | Maven | `./mvnw spotless:check` | `./mvnw spotless:apply` |
   | .NET | `dotnet format --verify-no-changes` | `dotnet format` |
