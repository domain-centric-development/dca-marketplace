#!/usr/bin/env python3
"""Every skill folder carries a SKILL.md with a name and a description in its front matter.

Two reasons this is a check and not a convention. A skill whose front matter a tool cannot read is
not a broken skill, it is an *absent* one — the tool lists everything else and says nothing. And the
`name` has to match its directory, because that is the name a project writes into a stack profile
(`carrier.build:`, `review.<perspective>:`) and the one a slash command resolves.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def front_matter(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if not text.startswith("---"):
        return {}
    block = text.split("---", 2)[1]
    data = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


def main():
    problems, counted = [], 0
    for plugin in sorted(os.listdir(os.path.join(ROOT, "plugins"))):
        skills = os.path.join(ROOT, "plugins", plugin, "skills")
        if not os.path.isdir(skills):
            continue
        for name in sorted(os.listdir(skills)):
            folder = os.path.join(skills, name)
            if not os.path.isdir(folder):
                continue
            path = os.path.join(folder, "SKILL.md")
            where = f"{plugin}/skills/{name}"
            if not os.path.isfile(path):
                problems.append(f"{where}: no SKILL.md")
                continue
            counted += 1
            front = front_matter(path)
            if not front.get("name"):
                problems.append(f"{where}: front matter has no `name`")
            elif front["name"] != name:
                problems.append(f"{where}: front matter says name `{front['name']}`")
            if not front.get("description"):
                problems.append(f"{where}: front matter has no `description`")
    for problem in problems:
        print(f"check-skills: {problem}", file=sys.stderr)
    print(f"check-skills: {counted - len(problems)}/{counted} skills carry a name and a description")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
