"""A press on the page writes its request: a button with no words box (an option of a question, an accept) as well as
one with words. The page's `press()` runs in node against stubs of what it calls; without node the case is skipped."""

import json
import shutil
import subprocess
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.adapter.incoming.web import page_core

NODE = shutil.which("node")

STUBS = r"""
const sent = [], toasts = [];
const S = {drafts: {}, handed: {}, drawer: null, detail: null};
const handed = new Map();
const ACTIONS = {pick: {label: "b", text: "", skill: "decide",
                        request: {kind: "answer", words: "option b", fields: {record: "D-1"}}}};
async function api(path, body) { sent.push([path, body]); return {id: "R-1"}; }
function toast(text, bad) { toasts.push([text, !!bad]); }
function by() { return "page"; }
function refresh() {}
async function handedData() { return []; }
"""

RUN = r"""
const button = {dataset: {press: "pick"}, closest: () => null};
press(button).then(() => console.log(JSON.stringify({sent, toasts})));
"""


def press_source() -> str:
    start = page_core.SCRIPT_CORE.index("async function press(")
    return page_core.SCRIPT_CORE[start:page_core.SCRIPT_CORE.index("\n}\n", start) + 3]


@unittest.skipUnless(NODE, "node is not installed")
class PressWithoutWordsTest(unittest.TestCase):

    def test_an_option_without_a_words_box_writes_its_request(self):
        out = subprocess.run([NODE, "-e", STUBS + press_source() + RUN], capture_output=True, text=True, timeout=30)
        self.assertEqual(0, out.returncode, out.stderr)
        seen = json.loads(out.stdout)
        self.assertEqual([], [t for t in seen["toasts"] if t[1]])
        self.assertEqual([["/api/request", {"kind": "answer", "words": "option b", "by": "page", "record": "D-1"}]],
                         seen["sent"])


if __name__ == "__main__":
    unittest.main()
