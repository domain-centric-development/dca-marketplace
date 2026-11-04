"""A project gives the page its own look, and the page shows every state without a running factory (WP-180).

The theme is the project's `.dca-factory/theme/`: its stylesheet linked after the page's own, the images it names, a
favicon of its own — served without the token, like the fonts, a flat name of four kinds and nothing else, an image
under a policy that runs nothing. A fixture answers the page's views from canned ones and refuses every press.
"""

import http.client
import json
import os
import shutil
import tempfile
import threading
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.adapter.outgoing.files.story_record import ignore_journals_in, journal_ignore_lines
from dca_factory.web import fixtures, service


class PageThemeTest(unittest.TestCase):

    def serve(self, fixture=None):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        theme = os.path.join(root, ".dca-factory", "theme")
        os.makedirs(theme)
        server = service.Server(("127.0.0.1", 0), service.Handler)
        server.project, server.token, server.port = root, "t" * 40, server.server_address[1]
        server.theme, server.fixture = theme, fixture
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server, theme

    def get(self, server, path, token=False):
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        headers = {"Host": f"127.0.0.1:{server.port}"}
        if token:
            headers["X-Factory-Token"] = server.token
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        body = response.read()
        connection.close()
        return response.status, dict(response.getheaders()), body

    def post(self, server, path, body):
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        data = json.dumps(body).encode("utf-8")
        connection.request("POST", path, body=data, headers={
            "Host": f"127.0.0.1:{server.port}", "X-Factory-Token": server.token, "Origin": f"http://127.0.0.1:{server.port}",
            "Content-Type": "application/json", "Content-Length": str(len(data))})
        response = connection.getresponse()
        answer = json.loads(response.read() or b"{}")
        connection.close()
        return response.status, answer

    def test_without_a_theme_the_page_links_an_empty_stylesheet_and_keeps_its_own_icon(self):
        server, _theme = self.serve()
        status, headers, body = self.get(server, "/theme/theme.css")
        self.assertEqual((200, "text/css; charset=utf-8"), (status, headers["Content-Type"]))
        self.assertNotIn(b"{", body)
        status, _h, icon = self.get(server, "/favicon.svg")
        self.assertEqual(200, status)
        self.assertIn(b"#148f96", icon)

    def test_a_theme_reaches_the_page_with_its_images_and_its_icon(self):
        server, theme = self.serve()
        with open(os.path.join(theme, "theme.css"), "w", encoding="utf-8") as handle:
            handle.write(":root { --brand: #c8102e; --logo: url(/theme/logo.svg); }\n")
        with open(os.path.join(theme, "logo.svg"), "w", encoding="utf-8") as handle:
            handle.write('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        with open(os.path.join(theme, "favicon.svg"), "w", encoding="utf-8") as handle:
            handle.write('<svg xmlns="http://www.w3.org/2000/svg" data-own="1"></svg>')
        self.assertIn(b"--brand: #c8102e", self.get(server, "/theme/theme.css")[2])
        status, headers, _b = self.get(server, "/theme/logo.svg")
        self.assertEqual((200, "image/svg+xml"), (status, headers["Content-Type"]))
        self.assertIn("sandbox", headers["Content-Security-Policy"])
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertIn(b'data-own="1"', self.get(server, "/favicon.svg")[2])
        with open(os.path.join(theme, "acme-sans.woff2"), "wb") as handle:
            handle.write(b"wOF2-a-font")
        status, headers, body = self.get(server, "/theme/acme-sans.woff2")
        self.assertEqual((200, "font/woff2", b"wOF2-a-font"), (status, headers["Content-Type"], body))

    def test_a_theme_file_is_a_flat_name_of_four_kinds(self):
        server, theme = self.serve()
        with open(os.path.join(theme, "run.js"), "w", encoding="utf-8") as handle:
            handle.write("alert(1)")
        outside = os.path.join(os.path.dirname(theme), "secret.css")
        with open(outside, "w", encoding="utf-8") as handle:
            handle.write("secret")
        for path in ("/theme/run.js", "/theme/..%2Fsecret.css", "/theme/a/b.css", "/theme/.hidden.css", "/theme/missing.png"):
            status, _h, body = self.get(server, path)
            self.assertEqual(404, status, path)
            self.assertNotIn(b"secret", body)

    def test_the_page_may_load_its_theme_and_no_other_style(self):
        server, _theme = self.serve()
        status, headers, page = self.get(server, "/?t=" + server.token)
        self.assertEqual(200, status)
        self.assertIn("style-src 'self' 'unsafe-inline'", headers["Content-Security-Policy"])
        self.assertIn(b'href="/theme/theme.css"', page)

    def test_a_fixture_answers_from_its_canned_views_and_refuses_every_press(self):
        server, _theme = self.serve(fixture="all-states")
        status, _h, body = self.get(server, "/api/view/status", token=True)
        self.assertEqual(200, status)
        self.assertEqual(fixtures.FIXTURES["all-states"]["status"]["project"], json.loads(body)["project"])
        meta = json.loads(self.get(server, "/api/meta", token=True)[2])
        self.assertEqual("all-states", meta["fixture"])
        status, answer = self.post(server, "/api/request", {"kind": "wish", "words": "x"})
        self.assertEqual(409, status)
        self.assertIn("canned", answer["error"])
        self.assertFalse(os.path.isdir(os.path.join(server.project, ".dca-factory", "requests")))

    def test_every_fixture_holds_the_views_the_page_reads(self):
        for name, views in fixtures.FIXTURES.items():
            for view in ("status", "requests", "decisions", "discover", "spec", "story", "part"):
                self.assertIn(view, views, f"{name}: {view}")
        states = {r["lane"] for r in fixtures.FIXTURES["all-states"]["status"]["rows"]}
        self.assertEqual({"draft", "approved", "running", "delivered", "superseded"}, states)
        self.assertEqual({"wait", "ask", "ok", "bad"}, {w["tone"] for w in fixtures.FIXTURES["all-states"]["requests"]["wishes"]})


    def test_the_run_page_follows_the_factorys_own_log_as_it_is_written(self):
        # WP-183: the worker's log, its last lines and then each new one, as the run page's output
        server, _theme = self.serve()
        log = os.path.join(server.project, ".dca-factory", "factory.log")
        with open(log, "w", encoding="utf-8") as handle:
            handle.write("factory: up\nfactory: a-story · plan\n")
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        connection.request("GET", "/api/follow?log=factory", headers={"Host": f"127.0.0.1:{server.port}", "X-Factory-Token": server.token})
        response = connection.getresponse()
        self.assertEqual(200, response.status)
        self.assertIn("text/event-stream", response.getheader("Content-Type"))

        def until(word):
            seen = []
            while not any(word in line for line in seen):
                line = response.fp.readline().decode("utf-8")
                self.assertTrue(line, f"the stream ended before {word!r}; seen {seen}")
                if line.startswith("data: "):
                    seen.append(json.loads(line[6:]))
            return seen

        self.assertEqual(["factory: up", "factory: a-story · plan"], until("plan"))
        with open(log, "a", encoding="utf-8") as handle:
            handle.write("factory: a-story · test\n")
        self.assertEqual(["factory: a-story · test"], until("test"))
        connection.close()

    def test_the_theme_is_let_into_git_beside_the_journals_once(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        before = [line for line in journal_ignore_lines(".dca-factory/evidence") if "theme" not in line]
        with open(os.path.join(root, ".gitignore"), "w", encoding="utf-8") as handle:
            handle.write("build/\n" + "\n".join(before) + "\n")          # a project that let the journals in before
        self.assertTrue(ignore_journals_in(root, ".dca-factory/evidence"))
        self.assertFalse(ignore_journals_in(root, ".dca-factory/evidence"))
        with open(os.path.join(root, ".gitignore"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        self.assertEqual(["build/"] + journal_ignore_lines(".dca-factory/evidence"), lines)
        self.assertEqual(1, lines.count("!/.dca-factory/theme/"))


if __name__ == "__main__":
    unittest.main()
