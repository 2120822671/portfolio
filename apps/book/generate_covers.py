"""
为每本书生成精美的本地封面图片（Pillow 纯本地生成，高性能版本）
"""
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np

BOOKS = [
    {"id": 1,  "title": "三体", "author": "刘慈欣", "style": "cosmic"},
    {"id": 2,  "title": "活着", "author": "余华", "style": "sepia"},
    {"id": 3,  "title": "百年孤独", "author": "加西亚·马尔克斯", "style": "magical"},
    {"id": 4,  "title": "人类简史", "author": "尤瓦尔·赫拉利", "style": "earth"},
    {"id": 5,  "title": "深度学习", "author": "Ian Goodfellow", "style": "matrix"},
    {"id": 6,  "title": "原则", "author": "瑞·达利欧", "style": "gold"},
    {"id": 7,  "title": "明朝那些事儿", "author": "当年明月", "style": "imperial"},
    {"id": 8,  "title": "小王子", "author": "圣埃克苏佩里", "style": "pastel"},
    {"id": 9,  "title": "思考，快与慢", "author": "丹尼尔·卡尼曼", "style": "split"},
    {"id": 10, "title": "红楼梦", "author": "曹雪芹", "style": "peony"},
    {"id": 11, "title": "算法导论", "author": "Thomas H. Cormen", "style": "tech"},
    {"id": 12, "title": "苏菲的世界", "author": "乔斯坦·贾德", "style": "philosophy"},
    {"id": 13, "title": "围城", "author": "钱锺书", "style": "ink"},
    {"id": 14, "title": "枪炮、病菌与钢铁", "author": "贾雷德·戴蒙德", "style": "archaeo"},
    {"id": 15, "title": "代码整洁之道", "author": "Robert C. Martin", "style": "code"},
]

STYLES = {
    "cosmic":     [(15, 8, 55),   (70, 25, 130),  (175, 95, 215)],
    "sepia":      [(135, 85, 45),  (195, 145, 95),  (225, 185, 135)],
    "magical":    [(165, 45, 75),  (225, 115, 75),  (252, 195, 145)],
    "earth":      [(55, 35, 18),   (125, 85, 45),   (185, 135, 75)],
    "matrix":     [(3, 18, 8),     (18, 75, 35),    (55, 195, 95)],
    "gold":       [(35, 25, 8),    (115, 85, 35),   (215, 175, 85)],
    "imperial":   [(75, 8, 8),     (175, 25, 25),   (235, 195, 75)],
    "pastel":     [(95, 135, 175), (175, 205, 225), (250, 225, 195)],
    "split":      [(28, 28, 55),   (95, 95, 155),   (195, 195, 215)],
    "peony":      [(95, 18, 38),   (195, 75, 95),   (250, 195, 175)],
    "tech":       [(8, 28, 55),    (38, 75, 135),   (115, 175, 225)],
    "philosophy": [(55, 45, 25),   (155, 125, 75),  (225, 205, 155)],
    "ink":        [(25, 20, 16),   (95, 80, 65),    (175, 155, 125)],
    "archaeo":    [(75, 45, 25),   (155, 95, 55),   (215, 175, 115)],
    "code":       [(12, 22, 32),   (38, 65, 95),    (95, 195, 195)],
}

ACCENT_COLORS = {
    "cosmic":     (200, 180, 255),
    "sepia":      (255, 230, 180),
    "magical":    (255, 240, 200),
    "earth":      (240, 210, 160),
    "matrix":     (180, 255, 200),
    "gold":       (240, 215, 130),
    "imperial":   (255, 230, 140),
    "pastel":     (255, 255, 240),
    "split":      (230, 225, 255),
    "peony":      (255, 235, 230),
    "tech":       (180, 230, 255),
    "philosophy": (245, 225, 175),
    "ink":        (220, 205, 175),
    "archaeo":    (245, 215, 165),
    "code":       (170, 230, 230),
}


def load_font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\STZHONGS.TTF",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\STKAITI.TTF",
        r"C:\Windows\Fonts\STSONG.TTF",
        r"C:\Windows\Fonts\STFANGSO.TTF",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\Georgia.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                continue
    return ImageFont.load_default()


def draw_gradient_fast(W, H, colors):
    """使用 numpy 快速生成渐变背景"""
    c1, c2, c3 = np.array(colors[0], dtype=np.float64), np.array(colors[1], dtype=np.float64), np.array(colors[2], dtype=np.float64)
    y = np.linspace(0, 1, H)
    row_colors = np.zeros((H, 3), dtype=np.uint8)
    mask_low = y < 0.5
    t_low = y[mask_low] * 2
    row_colors[mask_low] = (c1 + (c2 - c1) * t_low[:, None]).astype(np.uint8)
    mask_high = ~mask_low
    t_high = (y[mask_high] - 0.5) * 2
    row_colors[mask_high] = (c2 + (c3 - c2) * t_high[:, None]).astype(np.uint8)
    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[:, :, :] = row_colors[:, None, :]
    return Image.fromarray(img, "RGB")


def add_radial_halo(img, intensity=30):
    """叠加中心光晕"""
    W, H = img.size
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(halo)
    cx, cy = W // 2, H // 2 - 30
    max_r = max(W, H) * 0.55
    for r in range(int(max_r), 0, -8):
        alpha = int(intensity * (1 - r / max_r) ** 1.5)
        hdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, alpha))
    return Image.alpha_composite(img.convert("RGBA"), halo).convert("RGB")


def add_book_spine(img, width=18):
    """左侧书脊阴影"""
    arr = np.array(img, dtype=np.float64)
    for x in range(width):
        darkness = 45 * (1 - x / width)
        arr[:, x, :] = np.clip(arr[:, x, :] - darkness, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def wrap_chinese(text, font, max_width):
    lines = []
    current = ""
    for char in text:
        test = current + char
        if font.getlength(test) > max_width:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def generate_cover(book, output_path):
    W, H = 600, 800
    colors = STYLES[book["style"]]
    accent = ACCENT_COLORS[book["style"]]

    # 1. 渐变背景 (numpy)
    img = draw_gradient_fast(W, H, colors)

    # 2. 中心光晕
    img = add_radial_halo(img, intensity=25)

    # 3. 书脊阴影
    img = add_book_spine(img, width=15)

    draw = ImageDraw.Draw(img)

    # 4. 顶部装饰
    draw.rectangle([55, 100, W - 55, 101], fill=accent)
    draw.rectangle([75, 108, W - 75, 109], fill=accent)

    font_tag = load_font(14)
    draw.text((55, 72), f"NO. {book['id']:02d}", fill=accent, font=font_tag)
    en_tag = "INK & FRAGRANCE"
    bbox = draw.textbbox((0, 0), en_tag, font=font_tag)
    draw.text((W - 55 - (bbox[2] - bbox[0]), 72), en_tag, fill=accent, font=font_tag)

    # 5. 书名
    title_len = len(book["title"])
    title_font_size = 54 if title_len <= 3 else (44 if title_len <= 5 else 36)
    title_font = load_font(title_font_size)
    lines = wrap_chinese(book["title"], title_font, W - 90)

    total_h = len(lines) * (title_font_size + 16)
    start_y = 210
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=title_font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        y = start_y + i * (title_font_size + 16)
        # 阴影
        draw.text((x + 3, y + 3), line, fill=(0, 0, 0), font=title_font)
        # 主字
        draw.text((x, y), line, fill=(255, 255, 255), font=title_font)

    # 6. 菱形装饰
    deco_y = start_y + total_h + 20
    cx_d = W // 2
    draw.polygon([(cx_d, deco_y - 10), (cx_d + 12, deco_y),
                  (cx_d, deco_y + 10), (cx_d - 12, deco_y)], fill=accent)
    draw.rectangle([cx_d - 70, deco_y + 14, cx_d + 70, deco_y + 15], fill=accent)
    draw.rectangle([cx_d - 40, deco_y + 20, cx_d + 40, deco_y + 21], fill=accent)

    # 7. 作者
    author_font = load_font(24)
    author_text = f"— {book['author']} —"
    bbox = draw.textbbox((0, 0), author_text, font=author_font)
    aw = bbox[2] - bbox[0]
    draw.text(((W - aw) // 2, deco_y + 40), author_text, fill=(255, 255, 255), font=author_font)

    # 8. 底部装饰框
    by = H - 70
    draw.rectangle([55, by, W - 55, by + 1], fill=accent)
    draw.rectangle([55, by + 35, W - 55, by + 36], fill=accent)
    draw.rectangle([55, by, 56, by + 36], fill=accent)
    draw.rectangle([W - 56, by, W - 55, by + 36], fill=accent)

    font_brand = load_font(15)
    brand = "墨 香 书 阁"
    bbox = draw.textbbox((0, 0), brand, font=font_brand)
    bw = bbox[2] - bbox[0]
    draw.text(((W - bw) // 2, by + 12), brand, fill=accent, font=font_brand)

    img.save(output_path, "JPEG", quality=92)
    print(f"  ✓ {os.path.basename(output_path)} ({os.path.getsize(output_path)//1024}KB)")


def main():
    covers_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "covers")
    os.makedirs(covers_dir, exist_ok=True)
    print(f"🎨 开始生成 {len(BOOKS)} 张精美本地封面 (使用 Pillow + NumPy)...\n")
    for book in BOOKS:
        path = os.path.join(covers_dir, f"book_{book['id']:02d}.jpg")
        generate_cover(book, path)
    print(f"\n✅ 全部完成！")


if __name__ == "__main__":
    main()
