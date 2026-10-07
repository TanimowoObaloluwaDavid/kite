"""Generate README assets for Kite: logo, terminal GIF, phone GIF."""

import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
os.makedirs(ASSETS, exist_ok=True)

F = "C:/Windows/Fonts/"
MONO = F + "consola.ttf"
MONO_B = F + "consolab.ttf"
SANS = F + "segoeui.ttf"
SANS_B = F + "segoeuib.ttf"
SANS_SB = F + "seguisb.ttf"

BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
FG = "#c9d1d9"
DIM = "#8b949e"
GREEN = "#3fb950"
BLUE = "#58a6ff"
PURPLE = "#bc8cff"
ORANGE = "#d29922"
PINK = "#ff7b72"
CYAN = "#39c5cf"


# ---------------------------------------------------------------- logo

def make_logo():
    W = H = 512
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # soft glow background
    for r in range(240, 120, -8):
        a = int(18 * (240 - r) / 120)
        d.ellipse([W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r],
                  fill=(88, 166, 255, a))

    # kite diamond with gradient-ish layered polygons
    cx, cy = 256, 218
    top, right, bottom, left = (cx, 60), (cx + 130, cy), (cx, cy + 175), (cx - 130, cy)

    def mix(c1, c2, t):
        return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

    c_top = (88, 166, 255)
    c_bot = (188, 140, 255)
    pts_l = [top, left, bottom]
    pts_r = [top, right, bottom]
    d.polygon(pts_l, fill=mix(c_top, c_bot, 0.35) + (255,))
    d.polygon(pts_r, fill=mix(c_top, c_bot, 0.85) + (255,))

    # spine
    d.line([top, bottom], fill=(13, 17, 23, 255), width=10)
    d.line([left, right], fill=(13, 17, 23, 255), width=8)

    # highlight
    d.polygon([(cx, 78), (cx + 96, cy - 6), (cx, cy - 6)], fill=(255, 255, 255, 60))

    # tail (curve of small bows)
    tail = [(cx, cy + 175), (cx - 35, cy + 235), (cx + 25, cy + 295),
            (cx - 25, cy + 355), (cx + 15, cy + 415)]
    for i in range(len(tail) - 1):
        d.line([tail[i], tail[i + 1]], fill=(139, 148, 158, 255), width=7)
    for i, p in enumerate(tail[1:], start=1):
        col = (255, 123, 114) if i % 2 else (63, 185, 80)
        s = 22
        d.polygon([(p[0], p[1] - s), (p[0] + s, p[1]), (p[0], p[1] + s),
                   (p[0] - s, p[1])], fill=col + (255,))

    img.save(os.path.join(ASSETS, "logo.png"))
    print("logo.png")


# ------------------------------------------------------------ helpers

def font(path, size):
    return ImageFont.truetype(path, size)


def new_frame(w, h):
    img = Image.new("RGB", (w, h), BG)
    return img, ImageDraw.Draw(img)


def rounded(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def title_bar(d, w, title):
    d.rectangle([0, 0, w, 38], fill=PANEL)
    d.line([0, 38, w, 38], fill=BORDER, width=1)
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        d.ellipse([14 + i * 22, 13, 26 + i * 22, 25], fill=c)
    f = font(SANS, 15)
    tw = d.textlength(title, font=f)
    d.text(((w - tw) / 2, 10), title, font=f, fill=DIM)


def draw_code(d, lines, x, y, lh=26, fs=17, cursor=None):
    f = font(MONO, fs)
    for i, line in enumerate(lines):
        if line is None:
            continue
        colorize(d, line, x, y + i * lh, f)
    if cursor:
        cx, cy = cursor
        d.rectangle([cx, cy + 3, cx + 9, cy + fs - 2], fill=FG)


KEYWORDS = {"app", "state", "screen", "set", "fix", "make", "ret",
            "when", "else", "while", "each", "in", "and", "or", "not",
            "break", "continue", "true", "false", "nil", "is", "isnt"}


def colorize(d, line, x, y, f):
    """Simple syntax highlighting for Kite source."""
    i = 0
    cx = x
    while i < len(line):
        ch = line[i]
        if ch == '"':
            j = line.find('"', i + 1)
            j = len(line) if j < 0 else j + 1
            seg = line[i:j]
            d.text((cx, y), seg, font=f, fill=GREEN)
            cx += d.textlength(seg, font=f)
            i = j
            continue
        if ch == "/" and line[i:i + 2] == "//":
            seg = line[i:]
            d.text((cx, y), seg, font=f, fill=DIM)
            return
        if ch.isalpha() or ch == "_":
            j = i
            while j < len(line) and (line[j].isalnum() or line[j] == "_"):
                j += 1
            word = line[i:j]
            col = PURPLE if word in KEYWORDS else FG
            if word not in KEYWORDS and j < len(line) and line[j] == "(":
                col = BLUE
            d.text((cx, y), word, font=f, fill=col)
            cx += d.textlength(word, font=f)
            i = j
            continue
        if ch.isdigit():
            j = i
            while j < len(line) and (line[j].isdigit() or line[j] == "."):
                j += 1
            seg = line[i:j]
            d.text((cx, y), seg, font=f, fill=ORANGE)
            cx += d.textlength(seg, font=f)
            i = j
            continue
        d.text((cx, y), ch, font=f, fill=FG)
        cx += d.textlength(ch, font=f)
        i += 1


def save_gif(frames, name, duration=90):
    frames = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    path = os.path.join(ASSETS, name)
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=duration, loop=0, optimize=True)
    kb = os.path.getsize(path) // 1024
    print(f"{name} ({kb} KB, {len(frames)} frames)")


# ------------------------------------------------------- terminal GIF

TERM_W, TERM_H = 880, 500

CODE = [
    '// counter.kite — a real mobile app',
    'app Counter {',
    '  state count = 0',
    '',
    '  screen {',
    '    col {',
    '      text("You tapped {count} times")',
    '      btn("Add +1") { count += 1 }',
    '    }',
    '  }',
    '}',
]

OUTPUT = [
    ("$ kite run counter.kite", FG),
    ("--- app Counter (preview) ---", CYAN),
    ("  col {", DIM),
    ("    text: You tapped 0 times", FG),
    ("    btn: Add +1", FG),
    ("  }", DIM),
    ("--- end preview ---", CYAN),
    ("$ kite build counter.kite", FG),
    ("wrote counter.dart  →  flutter run", GREEN),
]


def terminal_frames():
    frames = []
    prompt = "$ "
    typable = "kite run counter.kite"

    def base():
        img, d = new_frame(TERM_W, TERM_H)
        title_bar(d, TERM_W, "counter.kite — Kite")
        return img, d

    # 1) show full code with blinking cursor (10 frames)
    for k in range(8):
        img, d = base()
        draw_code(d, CODE, 24, 58)
        if k % 2 == 0:
            last = CODE[9]
            f = font(MONO, 17)
            cx = 24 + d.textlength(last, font=f)
            d.rectangle([cx + 2, 58 + 9 * 26 + 4, cx + 11, 58 + 9 * 26 + 22],
                        fill=FG)
        frames.append(img)

    # 2) type the command (one frame per char)
    for n in range(1, len(typable) + 1):
        img, d = base()
        draw_code(d, CODE, 24, 58)
        f = font(MONO, 17)
        y = 58 + len(CODE) * 26 + 8
        d.text((24, y), prompt + typable[:n], font=f, fill=GREEN)
        w = d.textlength(prompt + typable[:n], font=f)
        if n < len(typable) and n % 2 == 0:
            d.rectangle([24 + w + 1, y + 3, 24 + w + 10, y + 21], fill=FG)
        frames.append(img)

    # 3) output appears line by line
    for k in range(1, len(OUTPUT) + 1):
        img, d = base()
        draw_code(d, CODE, 24, 58)
        f = font(MONO, 17)
        y0 = 58 + len(CODE) * 26 + 8
        d.text((24, y0), prompt + typable, font=f, fill=GREEN)
        for i in range(k):
            txt, col = OUTPUT[i]
            d.text((24, y0 + (i + 1) * 24), txt, font=f, fill=col)
        frames.append(img)

    # 4) hold
    img, d = base()
    draw_code(d, CODE, 24, 58)
    f = font(MONO, 17)
    y0 = 58 + len(CODE) * 26 + 8
    d.text((24, y0), prompt + typable, font=f, fill=GREEN)
    for i, (txt, col) in enumerate(OUTPUT):
        d.text((24, y0 + (i + 1) * 24), txt, font=f, fill=col)
    frames.extend(img for _ in range(14))

    return frames


# ----------------------------------------------------------- phone GIF

PW, PH = 360, 720  # phone canvas


def phone_base(d, count, pressed=None, flash=False):
    d.rectangle([0, 0, PW, PH], fill="#0d1117")
    # phone body
    x0, y0, x1, y1 = 30, 20, PW - 30, PH - 20
    rounded(d, [x0, y0, x1, y1], 40, fill="#ffffff", outline="#30363d", width=4)
    # notch
    d.rounded_rectangle([PW // 2 - 55, y0 + 8, PW // 2 + 55, y0 + 32],
                        radius=12, fill="#0d1117")
    # status bar
    fs = font(SANS_SB, 14)
    d.text((x0 + 26, y0 + 14), "9:41", font=fs, fill="#1f2328")
    for i in range(4):
        d.rectangle([x1 - 70 + i * 7, y0 + 24 - i * 3, x1 - 66 + i * 7, y0 + 26],
                    fill="#1f2328")

    # app content
    f_hello = font(SANS_B, 26)
    f_num = font(SANS_B, 54)
    f_lbl = font(SANS, 18)

    txt = "Hello, friend!" if count < 3 else "Hello, Kite!"
    d.text((PW // 2, y0 + 130), txt, font=f_hello, fill="#1f2328", anchor="mm")

    num_col = GREEN if flash else "#1f2328"
    d.text((PW // 2, y0 + 230), f"You tapped", font=f_lbl, fill="#57606a",
           anchor="mm")
    d.text((PW // 2, y0 + 295), str(count), font=f_num, fill=num_col,
           anchor="mm")
    d.text((PW // 2, y0 + 345), "times", font=f_lbl, fill="#57606a",
           anchor="mm")

    # buttons
    def button(cy, label, hot=False):
        bw, bh = 210, 62
        bx0, by0 = PW // 2 - bw // 2, cy - bh // 2
        fill = "#0969da" if not hot else "#0550ae"
        if pressed == label:
            fill = "#032a64"
        rounded(d, [bx0, by0, bx0 + bw, by0 + bh], 14, fill=fill)
        f_b = font(SANS_SB, 20)
        d.text((PW // 2, cy), label, font=f_b, fill="white", anchor="mm")

    button(y0 + 440, "Add +1")
    button(y0 + 530, "Reset")

    # screen indicator
    d.rounded_rectangle([PW // 2 - 60, y1 - 26, PW // 2 + 60, y1 - 18],
                        radius=4, fill="#1f2328")


def phone_frames():
    frames = []
    count = 0

    def snap(pressed=None, flash=False):
        img = Image.new("RGB", (PW, PH), "#010409")
        d = ImageDraw.Draw(img)
        phone_base(d, count, pressed, flash)
        return img

    def hold(n, pressed=None, flash=False):
        for _ in range(n):
            frames.append(snap(pressed, flash))

    hold(10)
    for target in (1, 2, 3):
        hold(3, pressed="Add +1")
        count = target
        hold(6, flash=True)
        hold(6)
    hold(3, pressed="Reset")
    count = 0
    hold(6, flash=True)
    hold(14)
    return frames


# ------------------------------------------------------------ banner

def make_banner():
    W, H = 1200, 360
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # gradient strip
    for x in range(W):
        t = x / W
        c = tuple(int(a + (b - a) * t) for a, b in
                  zip((88, 166, 255), (188, 140, 255)))
        d.line([x, 0, x, 6], fill=c)

    logo = Image.open(os.path.join(ASSETS, "logo.png")).convert("RGBA")
    logo = logo.resize((240, 240), Image.LANCZOS)
    img.paste(logo, (80, 70), logo)

    f1 = font(F + "seguibl.ttf", 96)
    d.text((370, 105), "Kite", font=f1, fill=FG)
    f2 = font(SANS, 27)
    d.text((375, 215), "A tiny language that flies straight to your phone",
           font=f2, fill=DIM)
    f3 = font(MONO, 19)
    d.text((375, 262), "$ kite build app.kite  →  flutter run", font=f3,
           fill=GREEN)

    img.save(os.path.join(ASSETS, "banner.png"))
    print("banner.png")


# ------------------------------------------------------- quiz phone GIF

QUIZ_PURPLE = "#5E5CE6"
QUIZ_GREEN = "#35B88E"
QUIZ_INK = "#24292F"
QUIZ_GREY = "#6E6E73"
QUIZ_CARD = "#F2F2F7"


def quiz_phone(d, screen, qi=1, score=0, total=2,
               answered=None, pressed=None):
    d.rectangle([0, 0, PW, PH], fill="#0d1117")
    x0, y0, x1, y1 = 30, 20, PW - 30, PH - 20
    rounded(d, [x0, y0, x1, y1], 40, fill="#ffffff", outline="#30363d",
            width=4)
    d.rounded_rectangle([PW // 2 - 55, y0 + 8, PW // 2 + 55, y0 + 32],
                        radius=12, fill="#0d1117")
    fs = font(SANS_SB, 14)
    d.text((x0 + 26, y0 + 14), "9:41", font=fs, fill="#1f2328")
    for i in range(4):
        d.rectangle([x1 - 70 + i * 7, y0 + 24 - i * 3, x1 - 66 + i * 7,
                     y0 + 26], fill="#1f2328")

    cx = PW // 2
    f_big = font(SANS_B, 30)
    f_mid = font(SANS_B, 20)
    f_body = font(SANS, 17)
    f_small = font(SANS, 14)
    f_bar = font(MONO_B, 16)

    def option(cy, label, hot=False, correct=False, wrong=False,
               revealed=False):
        bw, bh = 250, 58
        bx0, by0 = cx - bw // 2, cy - bh // 2
        fill = "#F2F2F7"
        edge = "#1f2328"
        if hot:
            fill = "#5E5CE6"
            edge = "#5E5CE6"
        if revealed:
            fill = QUIZ_GREEN if correct else ("#FF3B30" if wrong else "#F2F2F7")
            edge = fill
        rounded(d, [bx0, by0, bx0 + bw, by0 + bh], 14, fill=fill,
                outline=edge, width=2)
        d.text((cx, cy), label, font=f_body,
               fill="white" if (hot or revealed and (correct or wrong))
               else QUIZ_INK, anchor="mm")

    if screen == "home":
        d.text((cx, y0 + 120), "KiteQuiz", font=f_big, fill=QUIZ_PURPLE,
               anchor="mm")
        d.text((cx, y0 + 165), "A multi-screen app", font=f_small,
               fill=QUIZ_GREY, anchor="mm")
        d.text((cx, y0 + 185), "written in Kite", font=f_small,
               fill=QUIZ_GREY, anchor="mm")
        bw, bh = 210, 62
        bx0, by0 = cx - bw // 2, y0 + 300 - bh // 2
        fill = QUIZ_GREEN
        if pressed == "start":
            fill = "#2a9a72"
        rounded(d, [bx0, by0, bx0 + bw, by0 + bh], 14, fill=fill)
        d.text((cx, y0 + 300), "Start the quiz", font=f_small, fill="white",
               anchor="mm")

    elif screen == "quiz":
        d.text((cx, y0 + 60), f"{qi} of {total}", font=f_small, fill=QUIZ_GREY,
               anchor="mm")
        d.rounded_rectangle([cx - 110, y0 + 82, cx + 110, y0 + 92], radius=5,
                            fill="#E5E5EA")
        d.rounded_rectangle([cx - 110, y0 + 82,
                             cx - 110 + 220 * qi // total, y0 + 92],
                            radius=5, fill=QUIZ_PURPLE)
        d.text((cx, y0 + 130), "What language originally", font=f_body,
               fill=QUIZ_INK, anchor="mm")
        d.text((cx, y0 + 155), "created the World Wide Web?",
               font=f_body, fill=QUIZ_INK, anchor="mm")

        opts = ["Python", "HTML", "C", "JavaScript"]
        correct_idx = 3
        for i, o in enumerate(opts):
            cy = y0 + 240 + i * 80
            hot = pressed == o
            correct = i == correct_idx and answered is not None
            wrong = answered == o and i != correct_idx
            option(cy, o, hot=hot, correct=correct, wrong=wrong,
                   revealed=answered is not None)

        d.text((cx, y0 + 610), "Score: {score}", font=f_small, fill=QUIZ_GREY,
               anchor="mm")

    elif screen == "result":
        d.text((cx, y0 + 120), "Quiz complete", font=f_mid, fill=QUIZ_INK,
               anchor="mm")
        score_col = QUIZ_GREEN if score >= 2 else QUIZ_PURPLE
        d.text((cx, y0 + 175), "{score} / {total} correct", font=f_big,
               fill=score_col, anchor="mm")
        d.rounded_rectangle([cx - 110, y0 + 225, cx + 110, y0 + 235], radius=5,
                            fill="#E5E5EA")
        d.rounded_rectangle([cx - 110, y0 + 225,
                             cx - 110 + 220 * score // total, y0 + 235],
                            radius=5, fill=QUIZ_GREEN)
        msg = "Excellent work!" if score >= 2 else "Keep practising!"
        d.text((cx, y0 + 275), msg, font=f_body, fill=QUIZ_INK, anchor="mm")
        bw, bh = 210, 62
        bx0, by0 = cx - bw // 2, y0 + 350 - bh // 2
        fill = QUIZ_PURPLE
        if pressed == "again":
            fill = "#4f4dbf"
        rounded(d, [bx0, by0, bx0 + bw, by0 + bh], 14, fill=fill)
        d.text((cx, y0 + 350), "Play again", font=f_small, fill="white",
               anchor="mm")

    d.rounded_rectangle([PW // 2 - 60, y1 - 26, PW // 2 + 60, y1 - 18],
                        radius=4, fill="#1f2328")


def quiz_phone_frames():
    frames = []

    def snap(screen, **kw):
        img = Image.new("RGB", (PW, PH), "#010409")
        d = ImageDraw.Draw(img)
        quiz_phone(d, screen, **kw)
        return img

    def hold(screen, n, **kw):
        for _ in range(n):
            frames.append(snap(screen, **kw))

    hold("home", 14)
    hold("home", 4, pressed="start")
    hold("quiz", 10)

    # answer Python (wrong, 3rd option is right) -> reveal
    hold("quiz", 4, pressed="Python")
    hold("quiz", 6, answered="Python", score=0)
    # tap JavaScript (right) on q2 -> correct
    hold("quiz", 8, answered="Python", score=0)
    hold("quiz", 20, qi=2, score=0)
    hold("quiz", 4, qi=2, score=0, pressed="JavaScript")
    hold("quiz", 6, qi=2, score=0, answered="JavaScript")

    # result
    hold("result", 10, qi=2, score=1)
    hold("result", 4, qi=2, score=1, pressed="again")
    hold("home", 12)
    return frames


# ---------------------------------------------- quiz terminal preview GIF

QUIZ_CODE = [
    '// quiz.kite — the KiteQuiz app (v0.2)',
    'app Quiz {',
    '  state qi = 0      state score = 0',
    '',
    '  make optionBtn(label, ok) {',
    '    ret btn(label) {',
    '      when ok { score += 1 }',
    '      when qi + 1 >= len(questions) { goto Result }',
    '    }',
    '  }',
    '',
    '  screen Home  { col { ... } }',
    '  screen Quiz  { col { each opt { optionBtn(...) } } }',
    '  screen Result{ col { bar(score / len(questions)) } }',
    '}',
]

QUIZ_OUTPUT = [
    ("$ kite run examples/quiz.kite", FG),
    ("--- app Quiz · 3 screens ---", CYAN),
    ("--- Home ---", BLUE),
    ("  col {", DIM),
    ("    text: KiteQuiz   [size 42] [color #5E5CE6]", FG),
    ("    btn: Start the quiz", FG),
    ("  }", DIM),
    ("--- Quiz ---", BLUE),
    ("  col {", DIM),
    ("    bar: [###--------------] 25%", FG),
    ("    text: What language created the WWW?", FG),
    ("  }", DIM),
    ("--- Result ---", BLUE),
    ("  col {", DIM),
    ("    text: Quiz complete  [size 32]", FG),
    ("  }", DIM),
    ("--- end preview ---", CYAN),
    ("$ kite build quiz.kite", FG),
    ("wrote quiz.dart  →  flutter run", GREEN),
]


def quiz_terminal_frames():
    frames = []
    prompt = "$ "
    typable = "kite run examples/quiz.kite"

    def base():
        img, d = new_frame(TERM_W, TERM_H)
        title_bar(d, TERM_W, "quiz.kite — multi-screen Kite app")
        return img, d

    for k in range(8):
        img, d = base()
        draw_code(d, QUIZ_CODE, 24, 56)
        if k % 2 == 0:
            d.rectangle([24 + 2, 56 + 13 * 26 + 4, 24 + 11,
                         56 + 13 * 26 + 22], fill=FG)
        frames.append(img)

    for n in range(1, len(typable) + 1):
        img, d = base()
        draw_code(d, QUIZ_CODE, 24, 56)
        f = font(MONO, 17)
        y = 56 + len(QUIZ_CODE) * 26 + 6
        d.text((24, y), prompt + typable[:n], font=f, fill=GREEN)
        w = d.textlength(prompt + typable[:n], font=f)
        if n < len(typable) and n % 2 == 0:
            d.rectangle([24 + w + 1, y + 3, 24 + w + 10, y + 21], fill=FG)
        frames.append(img)

    for k in range(1, len(QUIZ_OUTPUT) + 1):
        img, d = base()
        draw_code(d, QUIZ_CODE, 24, 56)
        f = font(MONO, 17)
        y0 = 56 + len(QUIZ_CODE) * 26 + 6
        d.text((24, y0), prompt + typable, font=f, fill=GREEN)
        for i in range(k):
            txt, col = QUIZ_OUTPUT[i]
            d.text((24, y0 + (i + 1) * 24), txt, font=f, fill=col)
        frames.append(img)

    img, d = base()
    draw_code(d, QUIZ_CODE, 24, 56)
    f = font(MONO, 17)
    y0 = 56 + len(QUIZ_CODE) * 26 + 6
    d.text((24, y0), prompt + typable, font=f, fill=GREEN)
    for i, (txt, col) in enumerate(QUIZ_OUTPUT):
        d.text((24, y0 + (i + 1) * 24), txt, font=f, fill=col)
    frames.extend(img for _ in range(16))

    return frames


if __name__ == "__main__":
    make_logo()
    make_banner()
    save_gif(terminal_frames(), "terminal.gif", duration=75)
    save_gif(phone_frames(), "counter.gif", duration=140)
    save_gif(quiz_phone_frames(), "quiz.gif", duration=150)
    save_gif(quiz_terminal_frames(), "quiz-terminal.gif", duration=80)
    print("done")
