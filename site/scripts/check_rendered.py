"""Verify every rendered copy block and execute file creation in a fresh directory."""

import os
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]


class CopyBlocks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sections = []
        self.files = []
        self.count = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section":
            self.sections.append(attrs)
        if tag == "pre":
            assert any(s.get("class") == "command-panel" for s in self.sections), "Code block lacks shared Command"
            self.count += 1
        if tag == "button" and "data-code" in attrs:
            code = attrs["data-code"].replace("\x7f", "\n")
            path = next((s["data-file-path"] for s in self.sections if "data-file-path" in s), None)
            if path and "<<'WORKSHOP_FILE'" in code:
                self.files.append((path, code))

    def handle_endtag(self, tag):
        if tag == "section":
            self.sections.pop()


def main():
    copies = []
    total = 0
    for page in sorted((SITE / "dist").rglob("*.html")):
        parser = CopyBlocks()
        parser.feed(page.read_text())
        copies.extend(parser.files)
        total += parser.count
    assert len(copies) >= 15, "Missing rendered file instructions"
    with tempfile.TemporaryDirectory() as directory:
        env = dict(os.environ, PATH=f"{Path(sys.executable).parent}:{os.environ['PATH']}")
        for path, code in copies:
            result = subprocess.run(["bash", "-eu"], input=code, text=True, cwd=directory, env=env, capture_output=True)
            assert result.returncode == 0, f"{path}: {result.stderr}"
            actual = (Path(directory) / path).read_text()
            source = SITE / "src/snippets" / path.removeprefix("workshop/manual/")
            assert actual == source.read_text().rstrip() + "\n", path
    print(f"Verified {total} shared code panels and {len(copies)} exact copy-to-file commands")


if __name__ == "__main__":
    main()
