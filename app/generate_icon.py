"""Generate the Windows icon from the same brand mark used by the editor.

Run with the main Klipe Python environment (Skia and Pillow installed).
"""
from io import BytesIO
from pathlib import Path

from PIL import Image
import skia


def main():
    app = Path(__file__).resolve().parent
    source = app.parent / 'public' / 'marca' / 'klipe-mark.svg'
    dom = skia.SVGDOM.MakeFromStream(skia.MemoryStream(source.read_bytes()))
    if dom is None:
        raise RuntimeError(f'Invalid SVG: {source}')
    dom.setContainerSize(skia.Size(96, 96))
    surface = skia.Surface(1024, 1024)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    canvas.scale(1024 / 96, 1024 / 96)
    dom.render(canvas)
    encoded = surface.makeImageSnapshot().encodeToData(skia.kPNG, 100)
    image = Image.open(BytesIO(bytes(encoded))).convert('RGBA')
    if image.getchannel('A').getbbox() is None:
        raise RuntimeError('The SVG produced an empty icon.')
    sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    image.save(app / 'klipe.ico', format='ICO', sizes=sizes)
    print(f'Generated {app / "klipe.ico"}: {sizes}')


if __name__ == '__main__':
    main()
