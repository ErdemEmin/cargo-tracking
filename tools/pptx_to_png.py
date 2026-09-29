"""PPTX -> PNG, Windows PowerPoint COM ile (LibreOffice gerektirmez)."""
import sys
from pathlib import Path

import win32com.client

BASE = Path(__file__).resolve().parent.parent
PPTX = (BASE / "Kargo_Takip_Sistemi_Sunum.pptx").resolve()
OUT = BASE / "render"


def main():
    OUT.mkdir(exist_ok=True)
    app = win32com.client.Dispatch("PowerPoint.Application")
    pres = None
    try:
        pres = app.Presentations.Open(str(PPTX), ReadOnly=True, WithWindow=False)
        # 1 = ppSaveAsPNG
        for i, slide in enumerate(pres.Slides, 1):
            out = OUT / f"slayt{i:02d}.png"
            if out.exists():
                out.unlink()
            slide.Export(str(out), "PNG", 1600, 900)
            print(f"slayt {i} -> {out.name}")
        print(f"TOPLAM: {pres.Slides.Count} slayt")
    finally:
        if pres is not None:
            pres.Close()
        app.Quit()


if __name__ == "__main__":
    sys.exit(main())
