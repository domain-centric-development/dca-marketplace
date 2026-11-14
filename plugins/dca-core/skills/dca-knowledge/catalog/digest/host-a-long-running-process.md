# Host a long-running process — digest

Node: `/recipe/host-a-long-running-process.md` — cite it by that path; read it in full only for a decision this digest leaves open.

A process that runs for minutes or hours — a worker, a command-line run over many steps, a job — has state that belongs to the process, not to the domain: the claim on a resource, a lock, the working directory, the child processes it started, the signal that it should stop.

## Steps (first sentence each)

1. **Separate process state from domain state.** Progress a person or the business cares about — which step a run is in, what it decided — is the domain's: an aggregate or a store, behind a port.
2. **Put the host in `infrastructure/`.** One object, created by the composition root before anything else: it acquires what the process needs (the claim, the lock), installs the signal handlers, and releases everything on the way out, in reverse order.
3. **Give the use case a port for what it needs from the host.** A use case that must hold a claim, ask whether it should continue, or start a child process declares an output port in its own words (`CheckoutClaim`, `StepRunner`); the composition root implements it with the host.
4. **Let a stop pass through.** The host turns a signal into a stop: a cancelled token (.NET), an interrupt (Java), an exception of the application's own stop type (no platform model).
5. **Keep incoming adapters off the host.** A command-line handler or a worker loop reaches the host only through the composition root's wiring, never by import: an incoming adapter uses no infrastructure (`DCA-HEX-004`), and another context's infrastructure is private (`DCA-HEX-005`).
6. **Test the use case without the host.** Fake ports for the claim and the steps; one integration test starts the real host, sends the stop signal mid-run and asserts the exit code and that the claim is released.
