"""The runner's questions answered without the cli's whole command line: the same answer for the same question, and
anything else — a mistake among it — left to the whole command line."""

import contextlib
import io
import os
import unittest

from support import project, write
from dca_factory.delivery.adapter.incoming.cli import cli_command, question_command

PROFILE = """contract: 27
model.claude: opus
model.claude.plan: sonnet
carrier.build: dca-modelling
commands.test: ./gradlew test
epics: work/epics
"""

QUESTIONS = (["--stages", "--shell"], ["--stages", "--shell", "--place", "runs"], ["--get", "model.claude"],
             ["--get", "missing"], ["--command-heads"], ["--carriers"], ["--carrier-lines"],
             ["--model", "claude", "plan"], ["--place", "epics"], ["--place", "runs", "--runs", "elsewhere/runs"])


def printed(call, argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = call(argv)
    return code, out.getvalue()


class SameAnswer(unittest.TestCase):

    def test_every_question_is_answered_as_the_whole_command_line_answers_it(self):
        with project() as made:
            write(os.path.join(made.root, "dca-factory.profile.yaml"), PROFILE)
            for argv in QUESTIONS:
                with self.subTest(argv=argv):
                    asked = question_command.parse(argv)
                    self.assertIsNotNone(asked)
                    self.assertEqual(printed(lambda a: question_command.main(question_command.parse(a)), argv),
                                     printed(cli_command.main, argv))


class LeftToTheCommandLine(unittest.TestCase):

    def test_anything_else_is_not_a_question(self):
        for argv in (["--stages"], ["--shell"], ["--stages", "--shell", "--all"], ["--get"], ["--place", "nowhere"],
                     ["--get", "model", "--carriers"], ["--carriers", "--place", "epics"], ["--schedule"],
                     ["--carr"], ["--model", "claude"], []):
            with self.subTest(argv=argv):
                self.assertIsNone(question_command.parse(argv))


if __name__ == "__main__":
    unittest.main()
