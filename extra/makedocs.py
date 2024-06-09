import glob
import os
import re
import subprocess

for d2_file in glob.glob("docs/**/*.d2", recursive=True):
  subprocess.run(["d2", d2_file, d2_file[:-2] + "svg"], env={ "D2_THEME": "200" })

README_FILES = [
  "docs/overview.md",
  "docs/getting-started.md",
  "docs/custom-task.md",
]

README_PARTS = [
"""
# streamtasks

![](docs/screenshot.png)

Read the [Documentation](docs/overview.md).
"""
]

link_regex = re.compile("\[([^\]]*)\]\(([^\)]*)\)", re.IGNORECASE)

for docs_file in README_FILES:
  with open(docs_file, "r") as fd:
    content = fd.read()
    content = content.replace("# ", "## ")
    dirname = os.path.dirname(docs_file)

    pos = 0
    while True:
      m = link_regex.search(content, pos=pos)
      if m is None: break
      prefix = content[:m.start()]
      suffix = content[m.end():]

      content = prefix + f"[{m.group(1)}]({os.path.relpath(os.path.join(dirname, m.group(2)), './')})" + suffix
      pos = len(content) - len(suffix)

    README_PARTS.append(content)

with open("README.md", "w") as fd: fd.write("\n".join(README_PARTS))
