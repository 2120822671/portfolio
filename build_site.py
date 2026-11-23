"""生成可静态托管的作品集站点（输出到 _site/）。

本地运行用 portfolio/main.py；本脚本只负责把门户首页与简历页
改写成相对路径 + 公开演示地址，供静态托管使用。
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"

DEMO = "https://2120822671.github.io/portfolio/demo/"

REPLACEMENTS = {
    "index.html": [
        ('href="/farm/"', f'href="{DEMO}farm/"'),
        ('href="/stardock/home.html"', f'href="{DEMO}stardock/"'),
        ('href="/secondhand/static/index.html"', f'href="{DEMO}secondhand/"'),
        ('href="/account/"', f'href="{DEMO}account/"'),
        ('href="/book/"', f'href="{DEMO}book/"'),
        ('href="/resume.html"', 'href="resume.html"'),
        ('href="/resume.docx"', 'href="resume.docx"'),
        ('href="/"', 'href="index.html"'),
    ],
    "resume.html": [
        ('href="/"', 'href="index.html"'),
        ('href="/resume.docx"', 'href="resume.docx"'),
        ('src="/resume-photo"', 'src="resume-photo.png"'),
    ],
}


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    for name, rules in REPLACEMENTS.items():
        text = (ROOT / name).read_text(encoding="utf-8")
        for old, new in rules:
            if old not in text:
                raise SystemExit(f"{name} 中未找到待替换内容: {old}")
            text = text.replace(old, new)
        (OUT / name).write_text(text, encoding="utf-8")

    shutil.copy2(ROOT / "resume" / "个人简历.docx", OUT / "resume.docx")
    shutil.copy2(ROOT / "static" / "images" / "photo.png", OUT / "resume-photo.png")
    print(f"built: {OUT}")


if __name__ == "__main__":
    main()
