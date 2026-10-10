# Transactions in an in-memory start

Part of the `dca-init` skill (Phase 3, Java step 1): what a Spring project without a data starter needs so
that `@Transactional` and after-commit listeners work, and where the placeholder bean lives.

**Transactions in an in-memory start:** without a data starter there is no `PlatformTransactionManager` and
not even Boot's `TransactionAutoConfiguration` (`spring-boot-transaction`); `@Transactional` is then
silently inert and after-commit listeners never fire while every rule stays green. Add
`org.springframework.boot:spring-boot-transaction`, a small `PlatformTransactionManager` bean **in the
project** (a visible placeholder until a database arrives — `dca-spring` publishes none on purpose) and,
with Modulith, `spring-modulith-events-api` for `@ApplicationModuleListener`. Say so in the summary. The
bean comes from `templates/java/InMemoryTransactionManagerConfiguration.java.tmpl` →
`src/main/java/{{basePackagePath}}/infrastructure/config/InMemoryTransactionManagerConfiguration.java`. The
package is not a style choice: `DCA-LAY-004` allows transaction-manager wiring in the global infrastructure
package and below it (`<base>.infrastructure..`, `infrastructure/config/` included, where the conventions
put `@Configuration` classes) and in `<base>.sharedkernel.infrastructure..` — a top-level `<base>.config`
package or a context's own package fails the rule. The template steps aside by itself once `spring-jdbc` is
on the class path (`@ConditionalOnMissingClass`), so adding a data starter cannot leave the placeholder in
charge of real writes — verified: with `spring-boot-starter-jdbc` Boot's `JdbcTransactionManager` is the
one bean, without it the placeholder. Delete the class then anyway.
