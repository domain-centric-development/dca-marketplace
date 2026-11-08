"""The page's two file routes (WP-184): a person hands a file over beside their words, and a record, a report or a
story shows a picture it names — each guarded like every other answer, neither reaching past what it is for."""

import http.client
import os
import shutil
import tempfile
import threading
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.adapter.incoming.web import service

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


class PageFilesTest(unittest.TestCase):

    def serve(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        os.makedirs(os.path.join(root, ".dca-factory", "theme"))
        server = service.Server(("127.0.0.1", 0), service.Handler)
        server.project, server.token, server.port = root, "t" * 40, server.server_address[1]
        server.theme, server.fixture = os.path.join(root, ".dca-factory", "theme"), None
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server, root

    def call(self, server, method, path, body=b"", headers=None, token=True, origin=True):
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        sent = {"Host": f"127.0.0.1:{server.port}", "Content-Length": str(len(body))}
        if token:
            sent["X-Factory-Token"] = server.token
        if origin:
            sent["Origin"] = f"http://127.0.0.1:{server.port}"
        sent.update(headers or {})
        connection.request(method, path, body=body or None, headers=sent)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, dict(response.getheaders()), data

    def test_a_request_carries_its_files_and_is_refused_without_the_page(self):
        import base64
        import json
        server, root = self.serve()
        body = json.dumps({"kind": "wish", "words": "the desk sees the queue", "by": "Ann",
                           "files": [{"name": "screen shot.png", "data": base64.b64encode(PNG).decode()}]}).encode()
        json_kind = {"Content-Type": "application/json"}
        status, _h, answer = self.call(server, "POST", "/api/request", body, json_kind)
        self.assertEqual(201, status, answer)
        self.assertTrue(os.listdir(os.path.join(root, ".dca-factory", "requests", "files")))
        svg = json.dumps({"kind": "wish", "words": "w", "files": [{"name": "x.svg",
                          "data": base64.b64encode(b"<svg><script/></svg>").decode()}]}).encode()
        refused = [self.call(server, "POST", "/api/request", body, json_kind, token=False)[0],
                   self.call(server, "POST", "/api/request", body, dict(json_kind, Origin="http://evil.example"))[0],
                   self.call(server, "POST", "/api/request", svg, json_kind)[0],
                   self.call(server, "POST", "/api/request/file", PNG, {"Content-Type": "image/png"})[0]]
        self.assertEqual([403, 403, 400, 415], refused)        # the separate upload is gone: a write sends JSON

    def test_a_picture_beneath_product_is_shown_under_a_policy_that_runs_nothing(self):
        server, root = self.serve()
        folder = os.path.join(root, "product", "epics", "e", "s", "decisions", "01")
        os.makedirs(folder)
        with open(os.path.join(folder, "a.png"), "wb") as out:
            out.write(PNG)
        path = f"/api/file?path=product/epics/e/s/decisions/01/a.png&t={server.token}"
        status, headers, body = self.call(server, "GET", path, token=False, origin=False)
        self.assertEqual((200, "image/png", PNG), (status, headers["Content-Type"], body))
        self.assertIn("sandbox", headers["Content-Security-Policy"])
        self.assertEqual("nosniff", headers["X-Content-Type-Options"])

    def test_nothing_outside_product_and_the_factorys_folder_and_no_way_out_of_them(self):
        server, root = self.serve()
        with open(os.path.join(root, "build.gradle"), "w") as out:
            out.write("plugins {}\n")
        os.makedirs(os.path.join(root, "product"))
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, True)
        with open(os.path.join(outside, "secret.png"), "wb") as out:
            out.write(PNG)
        os.symlink(outside, os.path.join(root, "product", "away"))
        with open(os.path.join(root, "product", "page.html"), "w") as out:
            out.write("<html><script>alert(1)</script></html>")
        t = server.token
        codes = [self.call(server, "GET", f"/api/file?path={p}&t={t}", token=False, origin=False)[0] for p in
                 ("build.gradle", "product/../build.gradle", "/etc/hosts", "product/away/secret.png", "product/page.html")]
        self.assertEqual([404, 400, 400, 404, 415], codes)
        self.assertEqual(403, self.call(server, "GET", "/api/file?path=product/x.png", token=False, origin=False)[0])

    def test_a_mockup_beside_a_record_or_a_report_is_drawn_in_a_frame_that_runs_no_script(self):
        server, root = self.serve()
        page = b"<!doctype html><style>b{color:teal}</style><b>cards</b><script>alert(1)</script>"
        for folder in (("product", "epics", "e", "s", "decisions", "01"), ("product", "discovery", "t", "mockups")):
            os.makedirs(os.path.join(root, *folder))
            with open(os.path.join(root, *folder, "a-cards.html"), "wb") as out:
                out.write(page)
        for path in ("product/epics/e/s/decisions/01/a-cards.html", "product/discovery/t/mockups/a-cards.html"):
            status, headers, body = self.call(server, "GET", f"/api/file?path={path}&t={server.token}", token=False, origin=False)
            self.assertEqual((200, "text/html; charset=utf-8", page), (status, headers["Content-Type"], body), path)
            policy = headers["Content-Security-Policy"]
            self.assertIn("sandbox", policy)
            self.assertNotIn("script-src", policy)                 # default-src 'none': no script runs
            self.assertEqual("SAMEORIGIN", headers["X-Frame-Options"])

    def test_the_page_lets_frames_come_from_itself_alone(self):
        server, _root = self.serve()
        _status, headers, _body = self.call(server, "GET", f"/?t={server.token}", token=False, origin=False)
        self.assertIn("frame-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual("DENY", headers["X-Frame-Options"])


if __name__ == "__main__":
    unittest.main()
