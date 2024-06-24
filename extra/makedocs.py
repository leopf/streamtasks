import glob
import os
import re
import subprocess

for d2_file in glob.glob("docs/**/*.d2", recursive=True):
  subprocess.run(["d2", d2_file, d2_file[:-2] + "svg"], env={ "D2_THEME": "200" })

README_FILES = [
  "docs/_readme.md",
]

README_PARTS = [
"""
# streamtasks

![](docs/screenshot.png)

Read the [Documentation](https://leopf.github.io/streamtasks).
"""
]

INDEX_PARTS = [
"""---
title: Home
nav_order: 0
---
# streamtasks

![](./screenshot.png)
"""
]

link_regex = re.compile(r"\[([^\]]*)\]\(([^\)]*)\)", re.I)

for docs_file in README_FILES:
  with open(docs_file, "r") as fd:
    content = fd.read()
    INDEX_PARTS.append(content)
    dirname = os.path.dirname(docs_file)

    pos = 0
    while True:
      m = link_regex.search(content, pos=pos)
      if m is None: break
      prefix = content[:m.start()]
      suffix = content[m.end():]
      new_path = os.path.relpath(os.path.join(dirname, m.group(2)), './')
      if os.path.exists(new_path): content = prefix + f"[{m.group(1)}]({new_path})" + suffix
      else: content = prefix + content[m.start():m.end()] + suffix

      pos = len(content) - len(suffix)

    README_PARTS.append(content)

with open("README.md", "w") as fd: fd.write("\n".join(README_PARTS))
with open("docs/index.md", "w") as fd: fd.write("\n".join(INDEX_PARTS))
