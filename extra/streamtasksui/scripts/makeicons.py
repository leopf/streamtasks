from PIL import Image

icon_base = "src/streamtasksui/resources/icon"

raw_icon = Image.open("src/streamtasksui/resources/icon.png")
raw_icon.resize((64, 64)).save(icon_base + ".icns")
raw_icon.save(icon_base + ".ico")

png_sizes = [16, 32, 64, 128, 256, 512]
for size in png_sizes: raw_icon.resize((size, size)).save(icon_base + f"-{size}.png")
