"""What a run may reach (WP-184): the shell it may use beside its file tools, the network, the web, and the folders of
the home it never reads. A stage builds and tests, so its shell runs the project's commands and reads with the common
verbs; a request's skill only reads and records — its shell takes no path and no build, and it stays offline unless
its skill researches the web. A person's words widen none of it. How a tool is told is the adapters'."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value


class ShellHead(Value):
    """The first words of a command a run's shell may start, with any arguments after them."""

    value: str


class HomeFolder(Value):
    """A folder in a person's home, named from the home."""

    value: str


#: The shell a stage may use without asking, beside the gate, the cli and the profile's commands: the ordinary
#: reading and text tools, the git verbs that look without changing anything (`git apply --check` is how a stage
#: tries a break patch), and `git rm` — how a stage removes a file its plan says `removed`; it takes tracked files
#: only, which git still holds, and the pipeline's own files are watched by the run (WP-102). What writes or runs
#: anything else stays out — `rm`, `sed -i`, `xargs`, `find -exec`, a redirect of `echo`/`printf`, `mkdir`: each
#: allowed head is allowed with every argument (WP-94). Measured on the bench: without the reading tools a stage hit
#: the allow-list about three times per story, each a wasted turn; without a delete the build left a planned removal.
STAGE_SHELL_HEADS = tuple(ShellHead(word) for word in (
    "cd", "ls", "cat", "head", "tail", "wc", "sort", "grep", "diff", "pwd",
    "git status", "git diff", "git log", "git ls-files", "git apply --check", "git rm"))

#: What else a request's shell may run: the date the backlog skill writes, and git's reading of the project itself —
#: no verb that takes any path (`cat`, `cd`, `ls`, `grep`, `diff`): a skill reads with its reading tools, which stay
#: inside the project.
REQUEST_SHELL_HEADS = tuple(ShellHead(word) for word in ("date", "pwd", "git status", "git log", "git ls-files"))

#: The cli flags a request's skill may call (WP-91): what the dialog skills read and record with — never one that
#: starts a run, a request, the factory or its page (`--run`, `--work-request`, `--request`, `--up`, `--serve`).
REQUEST_CLI_FLAGS = tuple(ShellHead(word) for word in (
    "--contract", "--free-id", "--window-start", "--window-end", "--list-decisions", "--spec-delta", "--spec-check",
    "--findings", "--reopen", "--owned-confirm", "--status", "--discover-list", "--help-view", "--journal-line"))

#: The factory's verbs a request's skill may call: its readings, none that starts anything.
REQUEST_VERBS = tuple(ShellHead(word) for word in ("backlog", "status", "decisions", "discover", "spec-delta", "help"))

#: Where a home folder keeps what a run must never read — keys, tokens, credentials. Not `~/.config` whole: git and
#: the build tools read their own settings there — only the folders in it that hold tokens.
SECRET_FOLDERS = tuple(HomeFolder(word) for word in (
    ".ssh", ".aws", ".azure", ".gnupg", ".kube", ".docker", ".password-store", ".netrc", ".git-credentials", ".npmrc",
    ".pypirc", ".m2/settings.xml", ".gradle/gradle.properties", ".config/gh", ".config/gcloud", "Library/Keychains"))


class VariableName(Value):
    """The name of a variable in a run's environment."""

    value: str


#: What a variable's name says it holds when a run must not have it: a run of a story whose text came from outside
#: (a tracker, an import) gets no variable whose name contains one of these words — its text may carry instructions
#: nobody here wrote.
SECRET_WORDS = ("TOKEN", "SECRET", "KEY", "PASSWORD")


class Network(enum.Enum):
    """What of the network a run has."""

    OPEN = "open"            # the network as the tool has it, no tool to research with: a stage
    RESEARCH = "research"    # the network and the tools that search and fetch the web: a request that researches
    NONE = "none"            # no network: any other request


class RunKind(enum.Enum):
    STAGE = "stage"
    UNTRUSTED_STAGE = "untrusted-stage"   # a stage of a story whose text a person did not write (WP-190 E)
    REQUEST = "request"


class Reach(Value):
    """What one run may reach."""

    kind: RunKind
    network: Network

    @staticmethod
    def stage() -> "Reach":
        return Reach(RunKind.STAGE, Network.OPEN)

    @staticmethod
    def untrusted_stage() -> "Reach":
        """A stage of a story whose text came from a tracker or an import: it builds as a stage does, but offline —
        no grant overrides it —, without the web, and without a variable that names a secret."""
        return Reach(RunKind.UNTRUSTED_STAGE, Network.NONE)

    @staticmethod
    def request(network: Network) -> "Reach":
        """A request's run: offline, or researching the web — never the open network of a stage."""
        return Reach(RunKind.REQUEST, Network.RESEARCH if network is Network.RESEARCH else Network.NONE)

    @property
    def builds(self) -> bool:
        """Whether its shell runs the project's own commands — a build runs whatever its script says."""
        return self.kind is not RunKind.REQUEST

    @property
    def shell_heads(self) -> typing.Tuple[ShellHead, ...]:
        return STAGE_SHELL_HEADS if self.builds else REQUEST_SHELL_HEADS

    @property
    def cli_flags(self) -> typing.Optional[typing.Tuple[ShellHead, ...]]:
        """The cli flags it may call — None: the whole cli, as a stage has it."""
        return None if self.builds else REQUEST_CLI_FLAGS

    @property
    def verbs(self) -> typing.Tuple[ShellHead, ...]:
        return () if self.builds else REQUEST_VERBS

    def keeps(self, variable: VariableName) -> bool:
        """Whether the run is started with <variable>: an untrusted stage gets none whose name says it holds a
        secret; every other run all of them."""
        return self.kind is not RunKind.UNTRUSTED_STAGE \
            or not any(word in variable.value.upper() for word in SECRET_WORDS)

    @property
    def offline(self) -> bool:
        return self.network is Network.NONE

    @property
    def researches(self) -> bool:
        return self.network is Network.RESEARCH

    @property
    def secret_folders(self) -> typing.Tuple[HomeFolder, ...]:
        """The home's folders it never reads — every run's."""
        return SECRET_FOLDERS
