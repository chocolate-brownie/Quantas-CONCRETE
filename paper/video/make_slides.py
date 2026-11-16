#!/usr/bin/env python3
"""Peer-video slides as 8 Excalidraw frames (1920 x 1080 each) in paper/video/Peer video slides.excalidraw.

Run from the repo root after make_chart.py: python3 paper/video/make_slides.py
In Obsidian (Excalidraw plugin) or excalidraw.com, each frame is one slide; export frames as PNG/PDF.
"""
import base64, json, random
from pathlib import Path

HERE = Path(__file__).resolve().parent
random.seed(42)
W, H, GAP = 1920, 1080, 240
INK, GREY, MUTED = "#1e1e1e", "#868e96", "#495057"
YELLOW, BLUE, GREEN, RED, PURPLE, ORANGE, WHITE = (
    "#fff3bf", "#d0ebff", "#d3f9d8", "#ffe3e3", "#e5dbff", "#ffe8cc", "#ffffff")
els, files = [], {}
frame_id, ox, oy = None, 0, 0


def add(kind, x, y, w, h, **kw):
    e = dict(id=f"e{len(els)}", type=kind, x=ox + x, y=oy + y, width=w, height=h, angle=0,
             strokeColor=INK, backgroundColor="transparent", fillStyle="solid", strokeWidth=2,
             strokeStyle="solid", roughness=1, opacity=100, groupIds=[], frameId=frame_id,
             index=None, roundness=None, seed=random.randint(1, 2**31), version=1,
             versionNonce=random.randint(1, 2**31), isDeleted=False, boundElements=None,
             updated=1762700000000, link=None, locked=False)
    e.update(kw)
    els.append(e)
    return e


def text(x, y, s, size=40, color=INK, align="left", width=None):
    lines = s.split("\n")
    w = width or max(map(len, lines)) * size * 0.58
    if align == "center":
        x -= w / 2
    return add("text", x, y, w, len(lines) * size * 1.25, text=s, originalText=s, fontSize=size,
               fontFamily=5, textAlign=align, verticalAlign="top", containerId=None,
               lineHeight=1.25, strokeColor=color, autoResize=width is None)


def box(x, y, w, h, fill=WHITE, label=None, size=36, dashed=False, round_=True, stroke=INK, sw=2):
    add("rectangle", x, y, w, h, backgroundColor=fill, strokeColor=stroke, strokeWidth=sw,
        roundness={"type": 3} if round_ else None, strokeStyle="dashed" if dashed else "solid")
    if label:
        n = label.count("\n") + 1
        text(x + w / 2, y + h / 2 - n * size * 0.625, label, size, align="center")


def ellipse(x, y, w, h, fill=WHITE, label=None, size=36):
    add("ellipse", x, y, w, h, backgroundColor=fill)
    if label:
        n = label.count("\n") + 1
        text(x + w / 2, y + h / 2 - n * size * 0.625, label, size, align="center")


def arrow(x1, y1, x2, y2, dashed=False, color=INK, width=3, head="arrow", mid=None):
    pts = [[0, 0]] + ([[mid[0] - x1, mid[1] - y1]] if mid else []) + [[x2 - x1, y2 - y1]]
    add("arrow", x1, y1, abs(x2 - x1), abs(y2 - y1), points=pts, strokeColor=color,
        strokeWidth=width, strokeStyle="dashed" if dashed else "solid",
        roundness={"type": 2}, startBinding=None, endBinding=None, startArrowhead=None,
        endArrowhead=head)


def line(x1, y1, x2, y2, color=GREY, width=2, dashed=False):
    add("line", x1, y1, abs(x2 - x1), abs(y2 - y1), points=[[0, 0], [x2 - x1, y2 - y1]],
        strokeColor=color, strokeWidth=width, strokeStyle="dashed" if dashed else "solid")


def image(x, y, w, path, h=None):
    """Embed a PNG (path or bytes) with width w, or height h if given."""
    import struct
    data = path if isinstance(path, bytes) else path.read_bytes()
    fid = "img" + str(len(files))
    files[fid] = {"mimeType": "image/png", "id": fid, "created": 1762700000000,
                  "dataURL": "data:image/png;base64," + base64.b64encode(data).decode()}
    pw, ph = struct.unpack(">II", data[16:24])
    if h is not None:
        w = h * pw / ph
    add("image", x, y, w, w * ph / pw, fileId=fid, status="saved", scale=[1, 1], crop=None,
        strokeColor="transparent")


def round_face(path, size=256):
    """A photo cropped to a centred circle, as PNG bytes with a transparent background."""
    import io
    from PIL import Image, ImageDraw, ImageOps
    photo = ImageOps.fit(Image.open(path).convert("RGB"), (size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(photo, (0, 0), mask)
    buffer = io.BytesIO()
    out.save(buffer, "PNG")
    return buffer.getvalue()


def stick_person(cx, top, name, colour=INK):
    """A stick figure whose head is faces/<name>.jpg|png if present, else a drawn smiley."""
    r = 55
    face = next((HERE / "faces" / f"{name}.{ext}" for ext in ("jpg", "jpeg", "png")
                 if (HERE / "faces" / f"{name}.{ext}").exists()), None)
    if face:
        image(cx - r, top, 2 * r, round_face(face))
        add("ellipse", cx - r, top, 2 * r, 2 * r, strokeColor=colour, strokeWidth=3)
    else:
        add("ellipse", cx - r, top, 2 * r, 2 * r, backgroundColor=WHITE, strokeColor=colour,
            strokeWidth=3)
        for dx in (-20, 20):
            add("ellipse", cx + dx - 6, top + 35, 12, 12, backgroundColor=colour, strokeColor=colour)
        add("line", cx - 25, top + 68, 50, 14, points=[[0, 0], [25, 14], [50, 0]],
            strokeColor=colour, strokeWidth=3, roundness={"type": 2})
    neck, hip = top + 2 * r, top + 2 * r + 120
    line(cx, neck, cx, hip, colour, 4)
    line(cx, neck + 30, cx - 60, neck + 85, colour, 4)
    line(cx, neck + 30, cx + 60, neck + 85, colour, 4)
    line(cx, hip, cx - 45, hip + 95, colour, 4)
    line(cx, hip, cx + 45, hip + 95, colour, 4)


def bubble(cx, y, w, h, words, size=24, fill=WHITE):
    """A speech bubble centred on cx, with its tail pointing down."""
    box(cx - w / 2, y, w, h, fill)
    text(cx, y + h / 2 - (words.count("\n") + 1) * size * 0.625, words, size, align="center")
    line(cx - 15, y + h, cx, y + h + 35, INK, 2)
    line(cx + 15, y + h, cx, y + h + 35, INK, 2)


LIBRARIES = Path.home() / "Documents/mgodawat-playground/Obsidian/Excalidraw/Libraries"


def icon(library, name, x, y, height):
    """Copy a named item of a vault Excalidraw library, scaled to `height`, with its top-left at x, y."""
    data = json.loads((LIBRARIES / f"{library}.excalidrawlib").read_text())
    items = data.get("libraryItems") or data.get("library")
    item = next(i for i in items if isinstance(i, dict) and i.get("name") == name)
    src = [e for e in item["elements"] if not e.get("isDeleted")]
    x0, y0 = min(e["x"] for e in src), min(e["y"] for e in src)
    k = height / (max(e["y"] + e["height"] for e in src) - y0)
    group = f"icon{len(els)}"
    for e in src:
        e = json.loads(json.dumps(e))
        e.update(id=f"e{len(els)}", x=ox + x + (e["x"] - x0) * k, y=oy + y + (e["y"] - y0) * k,
                 width=e["width"] * k, height=e["height"] * k, frameId=frame_id, index=None,
                 groupIds=[group], boundElements=None, containerId=None)
        if "points" in e:
            e["points"] = [[px * k, py * k] for px, py in e["points"]]
        if "fontSize" in e:
            e["fontSize"] *= k
        for key in ("startBinding", "endBinding"):
            if key in e:
                e[key] = None
        els.append(e)
    return (max(q["x"] + q["width"] for q in src) - x0) * k


def slide(number, title, colour):
    """Start a slide: frame position, header band, title and page number."""
    global frame_id, ox, oy
    frame_id = f"frame{number}"
    r, c = number - 1, 0  # one column, slide 1 at the top
    ox, oy = c * (W + GAP), r * (H + GAP)
    add("rectangle", 0, 0, W, 22, backgroundColor=colour, strokeColor="transparent")
    if title:
        text(100, 70, title, 76)
    text(W - 150, H - 80, f"{number} / 8", 30, GREY)
    image(40, H - 72, 0, HERE / "assets/lip6.png", h=56)
    image(118, H - 72, 0, HERE / "assets/cnrs.png", h=56)


def end_slide(number, name):
    global frame_id
    frame_id = None
    add("frame", 0, 0, W, H, name=f"{number}. {name}", strokeColor="#bbb", roughness=0)


# 1. Title -----------------------------------------------------------------------------------
slide(1, None, YELLOW)
text(W / 2, 150, "From simulation to real machines", 100, align="center")
text(W / 2, 290, "Making research algorithms run on real computers", 46, MUTED, align="center")
text(W / 2, 365, "Milan Godawatta  ·  Internship at LIP6 (Sorbonne Université / CNRS)", 36,
     GREY, align="center")
box(330, 470, 420, 330, BLUE)
text(540, 485, "1 program", 34, align="center")
for i in range(9):
    r, c = divmod(i, 3)
    ellipse(415 + c * 95, 550 + r * 80, 55, 55, WHITE)
arrow(800, 640, 1100, 640, width=5)
text(950, 575, "my work", 34, "#c92a2a", align="center")
for i in range(9):
    r, c = divmod(i, 3)
    icon("network-topology-icons", "Computer (3D)", 1180 + c * 150, 470 + r * 105, 85)
text(1385, 790, "many real processes", 30, MUTED, align="center")
icon("stick-people", "Stick man talking", 140, 560, 230)
box(100, 850, 1720, 150, YELLOW)
text(140, 870, "QUANTAS is a research tool that simulates distributed algorithms inside one program. During my internship I built\n"
     "Concrete QUANTAS: it runs the very same algorithm code as real operating-system processes, on one machine or on\n"
     "a cluster of machines, so researchers can check that results found in simulation still hold in reality.", 29)
end_slide(1, "Title")

# 2. Where I worked -----------------------------------------------------------------------------
slide(2, "Where I worked", BLUE)
box(100, 200, 820, 280, BLUE)
text(140, 225, "LIP6", 64)
text(140, 315, "Laboratoire d'Informatique de Paris 6\nJoint research lab of Sorbonne Université and CNRS\nJussieu campus, Paris", 30)
box(100, 510, 820, 470, WHITE)
text(140, 530, "Three words to know", 36)
text(140, 595, "Distributed system: several computers that\nwork together by sending messages.\n\n"
     "Byzantine fault: a computer that behaves\narbitrarily, or even lies on purpose.\n\n"
     "Reliable broadcast: every honest computer gets\nthe right message, despite the liars.", 28)
people = [(1110, "supervisor", "Rule number one:\nnever edit the\nalgorithm code!", "My supervisor", "sets the goals,\nreviews the work", WHITE),
          (1420, "phd", "Do my results\nhold on real\nmachines?", "PhD student", "author of MT-CPA\nand its simulator", WHITE),
          (1730, "me", "Let's find out:\n12,000\nexperiments!", "Me", "built the tool,\nran every test", YELLOW)]
for i, (cx, name, says, role, job, fill) in enumerate(people):
    bubble(cx, 195 + (i % 2) * 40, 280, 150, says, 25, YELLOW if name == "me" else WHITE)
    stick_person(cx, 440, name, "#1971c2" if name == "me" else INK)
    box(cx - 145, 790, 290, 190, fill, sw=4 if name == "me" else 2)
    text(cx, 805, role, 34, align="center")
    text(cx, 865, job, 26, MUTED, align="center")
end_slide(2, "Where I worked")

# 3. The problem --------------------------------------------------------------------------------
slide(3, "The problem", BLUE)
text(380, 190, "In the simulator", 44, align="center")
box(130, 260, 500, 360, BLUE)
for i in range(9):
    r, c = divmod(i, 3)
    ellipse(230 + c * 110, 300 + r * 105, 75, 75, WHITE)
text(130, 640, "- all peers live inside ONE program\n- time advances in rounds\n- message delays are random numbers", 28)
text(1540, 190, "In reality", 44, align="center")
spots = [(1290, 270), (1480, 255), (1680, 290), (1260, 425), (1470, 415), (1700, 440),
         (1300, 560), (1500, 550), (1700, 575)]
links = [(0, 1), (1, 2), (0, 3), (1, 4), (2, 5), (3, 4), (4, 5), (3, 6), (4, 7), (5, 8), (6, 7),
         (7, 8), (0, 4), (4, 8)]
for (a, b), (c_, d) in [(spots[i], spots[j]) for i, j in links]:
    line(a + 55, b + 40, c_ + 55, d + 40)
for x, y in spots:
    icon("network-topology-icons", "Computer (3D)", x + 25, y, 80)
text(1290, 690, "- every peer is its own process\n- messages go through the operating\n  system or the network\n- delays come from real hardware", 28)
ellipse(790, 290, 340, 240, YELLOW, "Same\nresults?", 54)
icon("stick-people", "Stick man thinking", 925, 555, 180)
box(100, 860, 1720, 140, WHITE)
text(140, 878, "Example studied: MT-CPA. A sender broadcasts a value while up to f peers lie. Liveness = % of honest peers that\n"
     "deliver a value; safety = % of them that agree on the same value. The PhD paper measured both only in the simulator.", 28)
end_slide(3, "The problem")

# 4. My mission ---------------------------------------------------------------------------------
slide(4, "My mission: write once, run on both", GREEN)
box(710, 190, 500, 240, WHITE)
text(960, 210, "Algorithm code", 44, align="center")
for i in range(3):
    line(780, 300 + i * 40, 1140 - (i % 2) * 120, 300 + i * 40, GREY, 4)
box(1100, 160, 210, 64, RED, "never edited", 30)
arrow(700, 400, 470, 515, width=4)
arrow(1220, 400, 1450, 515, width=4)
box(150, 520, 560, 150, "#e9ecef", "Simulator\n(already existed)", 40)
box(1210, 520, 560, 150, GREEN, "Real processes\n(what I built)", 40, sw=4)
box(100, 720, 900, 280, WHITE)
text(130, 735, "Requirements", 34)
text(130, 790, "1. Run the algorithm files unchanged (supervisor's rule)\n2. Read the same JSON input files as the simulator\n"
     "3. Real processes: one machine, and across a cluster\n4. Report the same metrics, so results compare directly\n"
     "5. Never lose a message silently: fail loudly instead", 27)
box(1040, 720, 780, 280, GREEN)
text(1070, 735, "What I delivered", 34)
text(1070, 790, "- Concrete runtime in C++ (leader + peers)\n- 2 message backends: BoostMq and ZeroMQ\n"
     "- Scripts for 12,000-experiment campaigns\n- A tool paper that describes it all", 27)
end_slide(4, "My mission")

# 5. What I built -------------------------------------------------------------------------------
slide(5, "What I built", GREEN)
box(405, 180, 360, 100, ORANGE, "Leader process", 40)
text(585, 290, "checks the input, starts and stops each test, writes the report", 24, MUTED, align="center")
peers = [(110 + i * 200, 470) for i in range(5)]
for x, y in peers:
    arrow(585, 280, x + 75, y - 5, dashed=True, color=GREY, width=2)
for (x1, _), (x2, _) in zip(peers, peers[1:]):
    arrow(x1 + 150, 525, x2, 525, width=3)
for i, (x, y) in enumerate(peers):
    box(x, y, 150, 110, GREEN, f"peer {i}", 32)
text(100, 600, "- - -  control messages (start / stop)     ——  algorithm messages between peers", 26, MUTED)
text(100, 665, "Each test, step by step:", 30)
for i, step in enumerate(["READY", "ASSIGN", "START", "RUN", "DELIVERED", "STOP", "DONE"]):
    box(100 + i * 142, 715, 124, 70, PURPLE if step in ("RUN", "DELIVERED") else WHITE, step,
        17 if len(step) > 6 else 22)
    if i:
        arrow(100 + i * 142 - 17, 750, 100 + i * 142 - 3, 750, width=2)
box(100, 830, 1000, 160, YELLOW)
text(130, 845, "Adapter (one small file per algorithm, 21 lines for MT-CPA)\ntells the runtime 'is this peer finished?' and 'which values\n"
     "to report', by reading the algorithm's state. No edits needed.", 27)
box(1180, 180, 640, 380, BLUE)
text(1215, 200, "BoostMq", 46)
icon("network-topology-icons", "Server", 1720, 200, 100)
text(1215, 300, "Boost.Interprocess message queues\nin shared memory (/dev/shm)\n\n- one inbox queue per peer\n- very fast, one machine only", 28)
box(1180, 600, 640, 390, PURPLE)
text(1215, 620, "ZeroMQ", 46)
icon("racks-and-servers-components", "8U Rack", 1690, 615, 105)
text(1215, 740, "network sockets\n- data: PUSH to each neighbour's PULL inbox\n- control: ROUTER (leader) / DEALER (peers)\n"
     "- ipc:// on one machine, tcp:// on a cluster\n- only addresses in the input change", 26)
end_slide(5, "What I built")

# 6. Challenges ---------------------------------------------------------------------------------
slide(6, "Challenges I solved", RED)
icon("stick-figures", "Shrug", 1730, 30, 120)
cols = [("Problem", RED, "#c92a2a"), ("Why", "#f1f3f5", MUTED), ("My fix", GREEN, "#2b8a3e"),
        ("Result", PURPLE, "#5f3dc4")]
for j, (head, _, colour) in enumerate(cols):
    text(120 + j * 440, 175, head, 36, colour)
rows = [("Message queues\noverflowed",
         "the Dolev algorithm sends\nthousands of messages;\nan inbox held only 1,000",
         "inbox raised to 20,000;\na full inbox now fails\nthe test loudly",
         "heavy tests pass;\nno message is ever\nlost silently"),
        ("One process froze\nits CPU for 15-30 s",
         "a path search ran past\nthe 2 s time limit,\nchecked only between\nloop steps",
         "check the time limit\ninside the search itself",
         "tests stop on time\nagain"),
        ("6 of 10 cluster\nmachines refused\nto log in",
         "SSH key rejected; seen\nonly after 30 min idle:\n45 min of cluster time\nlost",
         "check every machine\nbefore the idle time:\nfail in seconds",
         "rerun: all 10 machines\nOK, 3,000 experiments,\n0 failures")]
for i, row in enumerate(rows):
    y = 235 + i * 235
    for j, cell in enumerate(row):
        x = 100 + j * 440
        box(x, y, 400, 205, cols[j][1], cell, 27 if j else 30)
        if j:
            arrow(x - 36, y + 102, x - 4, y + 102, width=3)
text(W / 2, 950, "Lesson: make failures loud and early. A clear error beats a silent wrong result.", 32,
     align="center")
end_slide(6, "Challenges")

# 7. Results ------------------------------------------------------------------------------------
slide(7, "Results", PURPLE)
for i, (big, small) in enumerate([("12,000", "experiments"), ("0", "failures"),
                                  ("11", "machines on a cluster")]):
    x = 100 + i * 590
    box(x, 175, 540, 150, PURPLE)
    text(x + 270, 180, big, 72, align="center")
    text(x + 270, 275, small, 30, MUTED, align="center")
text(100, 350, "Setup: MT-CPA · 50 peers · 3 network families × 20 networks · 1 to 5 lying peers  ->  300 experiments,\n"
     "each repeated 10 times on every system: simulator, BoostMq, ZeroMQ (1 machine), ZeroMQ (11 machines)", 27, MUTED)
image(100, 470, 1000, HERE / "results_chart.png")
text(100, 890, "Bars: mean over the 10 repetitions. The full figures, with 95% confidence\nintervals for every network family, are in the paper.", 24, MUTED)
box(1150, 470, 670, 520, WHITE)
text(1180, 485, "What we found", 36)
text(1180, 545, "- Liveness: same everywhere (99.6-99.7%)\n- Messages: identical, 8.35 per peer\n"
     "- Safety: 100% within the algorithm's\n  guarantee (f = 1 lying peer)\n"
     "- Beyond it, real timing matters. f = 4:\n  77% simulator, 73% ZeroMQ on one\n  machine, 66% ZeroMQ on the cluster\n"
     "- One machine: ZeroMQ runs a campaign\n  as fast as the simulator (2.3 vs 2.5 min)\n"
     "- Cluster: 20.8 min, which includes\n  starting peers on 10 remote machines", 25)
end_slide(7, "Results")

# 8. What I learned -----------------------------------------------------------------------------
slide(8, "What I learned", YELLOW)
icon("stick-people", "Stick man standard", 1660, 20, 160)
box(100, 190, 820, 580, BLUE)
text(140, 215, "Technical", 48)
text(140, 300, "- C++ and operating-system processes\n- Inter-process communication: shared\n  memory (Boost) and sockets (ZeroMQ)\n"
     "- Running jobs on a cluster (OAR, SSH)\n- Experiment design: repetitions, idle\n  periods, 95% confidence intervals\n"
     "- Debugging distributed failures from logs", 29)
box(1000, 190, 820, 580, GREEN)
text(1040, 215, "Working with people", 48)
text(1040, 300, "- Turning a supervisor's rule into a\n  design: 'never edit algorithm code'\n"
     "- Working on a PhD student's code and\n  checking every claim against it\n"
     "- Explaining results to researchers\n- Writing a research tool paper", 29)
box(100, 810, 1720, 180, YELLOW, sw=3)
text(W / 2, 830, "Next: submit the tool paper  ·  simulate crash faults inside peers\n·  scale to 100 peers, as in the original paper", 34, align="center")
text(W / 2, 935, "Thank you!", 40, align="center")
end_slide(8, "What I learned")

out = HERE / "Peer video slides.excalidraw"
out.write_text(json.dumps({"type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
                           "elements": els, "appState": {"viewBackgroundColor": "#ffffff",
                                                         "gridSize": 20}, "files": files}))
print(f"Saved {out}: {len(els)} elements, {sum(e['type'] == 'frame' for e in els)} frames")
