from PIL import Image
import toml

# make icons
icon_base = "src/streamtasksui/resources/icon"

raw_icon = Image.open("src/streamtasksui/resources/icon.png")
raw_icon.resize((64, 64)).save(icon_base + ".icns")
raw_icon.save(icon_base + ".ico")

png_sizes = [16, 32, 64, 128, 256, 512]
for size in png_sizes: raw_icon.resize((size, size)).save(icon_base + f"-{size}.png")

# fix version
ui_pp = toml.load("pyproject-template.toml")
core_pp = toml.load("../../pyproject.toml")
ui_pp["tool"]["briefcase"]["version"] = core_pp["project"]["version"]
toml.dump(ui_pp, open("pyproject.toml", "w"))
