#!/usr/bin/env python3
"""
 Jakubinekks Gayme

Move: WASD   Shoot: arrows   P: pause   Q: quit   R: restart (after end)
"""
import time, math, random
import tkinter as tk
import tkinter.font as tkfont

# ---------------- config ----------------
W, H = 39, 15
GRID = 7
CENTER = (3, 3)
N_ROOMS = 10
TICK_MS = 33
COLS, ROWS = 64, 22

BG = "#0b0b0f"
PAL = {"white": "#e8e8ec", "gray": "#9a9aa2", "dim": "#43434d",
       "red": "#ff5555", "green": "#7dff7d", "yellow": "#ffd75e",
       "magenta": "#e070ff", "cyan": "#70e0ff", "wall": "#7a7a85"}

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

ITEMS = [
    ("Kyle Taylors Rusty Vape", "all stats up, full heal",
     dict(damage=1.2, speed=1.2, range=2.0, fire_rate=0.4, maxhp=2, full=True)),
    ("Roid Rage",      "+damage",             dict(damage=1.5)),
    ("Kyle Faircloughs Dealdough",      "+speed",              dict(speed=1.6)),
    ("Adderall",         "+fire rate",          dict(fire_rate=0.9)),
    ("Erdafitinib",      "+range, +shot speed", dict(range=4.0, shot_speed=3.0)),
    ("The Boost",   "+shot speed, +dmg",   dict(shot_speed=4.0, damage=0.5)),
    ("Oxytocin",       "+1 heart container",  dict(maxhp=2, heal=2)),
    ("Human Growth Hormone", "+speed, +damage",     dict(speed=0.8, damage=0.7)),
]

# ---------------- entities ----------------
class Tear:
    __slots__ = ("x", "y", "vx", "vy", "left", "dmg", "hostile")
    def __init__(self, x, y, vx, vy, rng, dmg, hostile):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.left, self.dmg, self.hostile = rng, dmg, hostile

class Pickup:
    def __init__(self, x, y): self.x, self.y = x, y

class Enemy:
    def __init__(self, kind, x, y, rng):
        self.kind, self.x, self.y, self.rng = kind, x, y, rng
        self.hit_t = 0.0; self.t = rng.uniform(0.5, 1.5)
        self.dx = self.dy = 1.0; self.phase = 0
        if kind == "chaser":   self.hp, self.speed, self.r = 12, 4.6, 0.45; self.ch, self.col, self.dmg = "c", "red", 1
        elif kind == "wanderer": self.hp, self.speed, self.r = 9, 3.6, 0.45; self.ch, self.col, self.dmg = "w", "yellow", 1
        elif kind == "shooter":  self.hp, self.speed, self.r = 8, 0.0, 0.45; self.ch, self.col, self.dmg = "s", "magenta", 1
        else:                    self.hp, self.speed, self.r = 95, 3.2, 0.80; self.ch, self.col, self.dmg = "B", "red", 2
        self.maxhp = self.hp

class Room:
    def __init__(self, kind):
        self.kind, self.visited = kind, False
        self.cleared = kind in ("start", "treasure")
        self.enemies, self.pickups = [], []
        self.item, self.taken = None, False

def gen_layout(rng):
    cells = {CENTER}; p = CENTER; tries = 0
    while len(cells) < N_ROOMS and tries < 400:
        tries += 1
        d = rng.choice(list(DIRS.values()))
        q = (p[0] + d[0], p[1] + d[1])
        if 0 <= q[0] < GRID and 0 <= q[1] < GRID:
            cells.add(q); p = q
    cells = list(cells)
    dist = lambda c: abs(c[0] - CENTER[0]) + abs(c[1] - CENTER[1])
    boss = max(cells, key=lambda c: (dist(c), rng.random()))
    neigh = lambda c: sum((c[0]+d[0], c[1]+d[1]) in cells for d in DIRS.values())
    ends = [c for c in cells if c not in (CENTER, boss) and neigh(c) == 1]
    treasure = rng.choice(ends) if ends else rng.choice([c for c in cells if c not in (CENTER, boss)])
    layout = {CENTER: "start", boss: "boss", treasure: "treasure"}
    for c in cells: layout.setdefault(c, "normal")
    return layout

# ---------------- screen buffer ----------------
class Screen:
    def __init__(self):
        self.g = [[(" ", "gray", False)] * COLS for _ in range(ROWS)]
    def put(self, r, c, ch, fg, bold=False):
        if 0 <= r < ROWS and 0 <= c < COLS: self.g[r][c] = (ch, fg, bold)
    def text(self, r, c, s, fg, bold=False):
        for i, ch in enumerate(s): self.put(r, c + i, ch, fg, bold)
    def center(self, r, s, fg, bold=False):
        self.text(r, (COLS - len(s)) // 2, s, fg, bold)
        return (COLS - len(s)) // 2

# ---------------- game ----------------
class Game:
    def __init__(self, rng):
        self.rng = rng
        self.layout = gen_layout(rng)
        self.rooms = {c: Room(k) for c, k in self.layout.items()}
        self.pos = CENTER
        self.cur().visited = True
        self.enemies = self.cur().enemies
        self.px, self.py = W / 2, H / 2
        self.tears = []
        self.maxhp, self.hp = 6, 6
        self.speed, self.damage, self.range = 9.5, 3.5, 13.0
        self.shot_speed, self.fire_rate = 16.0, 2.6
        self.cd = 0.0; self.invuln = 0.0
        self.msg, self.msg_fg, self.msg_t = "", "white", 0.0
        self.kills = 0
        self.state = "play"

    def cur(self): return self.rooms[self.pos]
    def has_door(self, d): return (self.pos[0]+DIRS[d][0], self.pos[1]+DIRS[d][1]) in self.layout
    def neighbor_kind(self, d): return self.layout.get((self.pos[0]+DIRS[d][0], self.pos[1]+DIRS[d][1]))
    def say(self, t, fg="white"): self.msg, self.msg_fg, self.msg_t = t, fg, 3.5

    def populate(self, room):
        if room.kind == "normal":
            for _ in range(self.rng.randint(2, 5)):
                x = y = 0
                for _t in range(25):
                    x = self.rng.uniform(2, W - 2); y = self.rng.uniform(2, H - 2)
                    if math.hypot(x - self.px, y - self.py) > 7: break
                room.enemies.append(Enemy(self.rng.choice(["chaser", "wanderer", "shooter"]), x, y, self.rng))
        elif room.kind == "boss":
            room.enemies.append(Enemy("boss", W / 2, 3.5, self.rng))
            self.say("SPLONKKY awakens...", "red")
        elif room.kind == "treasure":
            room.item = self.rng.choice(ITEMS)

    def go(self, d):
        self.pos = (self.pos[0] + DIRS[d][0], self.pos[1] + DIRS[d][1])
        room = self.cur()
        if not room.visited:
            room.visited = True
            self.populate(room)
        self.enemies = room.enemies
        cx, cy = W / 2, H / 2
        if d == "up":    self.px, self.py = cx, H - 0.9
        if d == "down":  self.px, self.py = cx, 0.9
        if d == "left":  self.px, self.py = W - 0.9, cy
        if d == "right": self.px, self.py = 0.9, cy
        self.tears = []
        self.invuln = max(self.invuln, 0.6)

    def hurt(self, dmg):
        if self.invuln > 0: return
        self.hp -= dmg; self.invuln = 1.0
        if self.hp <= 0: self.state = "dead"

    def apply_item(self, it):
        name, desc, deltas = it
        for k, v in deltas.items():
            if k in ("heal", "full"): continue
            if k == "maxhp": self.maxhp += v; self.hp += v
            else: setattr(self, k, getattr(self, k) + v)
        if deltas.get("full"): self.hp = self.maxhp
        elif "heal" in deltas: self.hp = min(self.maxhp, self.hp + deltas["heal"])
        self.say(f"{name}: {desc}", "yellow")

    def update(self, dt, kb):
        self.cd = max(0.0, self.cd - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.msg_t = max(0.0, self.msg_t - dt)

        dx = int(kb.down("d")) - int(kb.down("a"))
        dy = int(kb.down("s")) - int(kb.down("w"))
        if dx or dy:
            l = math.hypot(dx, dy)
            self.px += dx / l * self.speed * dt
            self.py += dy / l * self.speed * dt

        r, cx, cy = 0.45, W / 2, H / 2
        cleared = self.cur().cleared
        minx, maxx, miny, maxy = r, W - r, r, H - r
        if cleared and self.has_door("up")    and abs(self.px - cx) < 1.1: miny = -1.5
        if cleared and self.has_door("down")  and abs(self.px - cx) < 1.1: maxy = H + 1.5
        if cleared and self.has_door("left")  and abs(self.py - cy) < 1.1: minx = -1.5
        if cleared and self.has_door("right") and abs(self.py - cy) < 1.1: maxx = W + 1.5
        self.px = min(max(self.px, minx), maxx)
        self.py = min(max(self.py, miny), maxy)

        if self.py < -0.8:    self.go("up");    return
        if self.py > H + 0.8: self.go("down");  return
        if self.px < -0.8:    self.go("left");  return
        if self.px > W + 0.8: self.go("right"); return

        sx = int(kb.down("right")) - int(kb.down("left"))
        sy = int(kb.down("down")) - int(kb.down("up"))
        if (sx or sy) and self.cd <= 0:
            self.cd = 1.0 / self.fire_rate
            l = math.hypot(sx, sy)
            self.tears.append(Tear(self.px, self.py, sx / l * self.shot_speed,
                                   sy / l * self.shot_speed, self.range, self.damage, False))

        alive = []
        for t in self.tears:
            t.x += t.vx * dt; t.y += t.vy * dt
            t.left -= math.hypot(t.vx, t.vy) * dt
            if t.left <= 0 or not (0.2 < t.x < W - 0.2 and 0.2 < t.y < H - 0.2): continue
            hit = False
            if t.hostile:
                if math.hypot(t.x - self.px, t.y - self.py) < 0.5:
                    self.hurt(t.dmg); hit = True
            else:
                for e in self.enemies:
                    if math.hypot(t.x - e.x, t.y - e.y) < e.r + 0.28:
                        e.hp -= t.dmg; e.hit_t = 0.12; hit = True; break
            if not hit: alive.append(t)
        self.tears = alive

        for e in list(self.enemies):
            e.hit_t = max(0.0, e.hit_t - dt)
            px, py = self.px, self.py
            if e.kind == "chaser":
                d = math.hypot(px - e.x, py - e.y) or 1
                e.x += (px - e.x) / d * e.speed * dt
                e.y += (py - e.y) / d * e.speed * dt
            elif e.kind == "wanderer":
                e.t -= dt
                if e.t <= 0:
                    a = self.rng.random() * 2 * math.pi
                    e.dx, e.dy = math.cos(a), math.sin(a)
                    e.t = self.rng.uniform(0.8, 2.0)
                nx, ny = e.x + e.dx * e.speed * dt, e.y + e.dy * e.speed * dt
                if nx < 0.6 or nx > W - 0.6: e.dx *= -1; nx = max(0.6, min(W - 0.6, nx))
                if ny < 0.6 or ny > H - 0.6: e.dy *= -1; ny = max(0.6, min(H - 0.6, ny))
                e.x, e.y = nx, ny
            elif e.kind == "shooter":
                e.t -= dt
                if e.t <= 0:
                    e.t = 1.9
                    d = math.hypot(px - e.x, py - e.y) or 1
                    self.tears.append(Tear(e.x, e.y, (px - e.x) / d * 8, (py - e.y) / d * 8, 30, 1, True))
            elif e.kind == "boss":
                enraged = e.hp < e.maxhp * 0.45
                d = math.hypot(px - e.x, py - e.y) or 1
                if d > 3:
                    sp = e.speed * (1.35 if enraged else 1.0)
                    e.x += (px - e.x) / d * sp * dt
                    e.y += (py - e.y) / d * sp * dt
                e.t -= dt
                if e.t <= 0:
                    e.t = 1.7 if enraged else 2.3
                    e.phase ^= 1
                    if e.phase == 0:
                        off = self.rng.random() * 2 * math.pi
                        for i in range(12):
                            a = off + i * math.pi / 6
                            self.tears.append(Tear(e.x, e.y, math.cos(a) * 6.5, math.sin(a) * 6.5, 26, 1, True))
                    else:
                        base = math.atan2(py - e.y, px - e.x)
                        for k in (-0.25, 0.0, 0.25):
                            self.tears.append(Tear(e.x, e.y, math.cos(base + k) * 9, math.sin(base + k) * 9, 26, 1, True))
            if e.kind in ("chaser", "boss"):
                e.x = max(0.7, min(W - 0.7, e.x)); e.y = max(0.7, min(H - 0.7, e.y))
            if math.hypot(e.x - px, e.y - py) < e.r + 0.4:
                self.hurt(e.dmg)
            if e.hp <= 0:
                self.enemies.remove(e)
                self.kills += 1
                if e.kind != "boss" and self.rng.random() < 0.22:
                    self.cur().pickups.append(Pickup(e.x, e.y))

        room = self.cur()
        if not room.cleared and not self.enemies:
            room.cleared = True
            if room.kind == "boss": self.state = "won"
            else: self.say("The doors creak open...", "gray")

        for p in list(room.pickups):
            if math.hypot(p.x - self.px, p.y - self.py) < 0.8 and self.hp < self.maxhp:
                self.hp = min(self.maxhp, self.hp + 2)
                room.pickups.remove(p)
                self.say("+\u2665\u2665", "red")
        if room.kind == "treasure" and room.item and not room.taken:
            if math.hypot(self.px - cx, self.py - cy) < 1.0:
                self.apply_item(room.item); room.taken = True

    # ---- rendering ----
    def hearts_cells(self):
        cells = []
        for i in range(self.maxhp // 2):
            if self.hp >= 2 * i + 2: cells.append(("\u2665", "red", True))
            elif self.hp == 2 * i + 1: cells.append(("\u2661", "red", False))
            else: cells.append(("\u00b7", "dim", False))
        return cells

    def minimap(self):
        rows = []
        for gy in range(GRID):
            line = []
            for gx in range(GRID):
                c = (gx, gy)
                if c in self.layout and self.rooms[c].visited:
                    kind = self.layout[c]
                    ch = {"start": "S", "treasure": "$", "boss": "B", "normal": "\u00b7"}[kind]
                    col = {"start": "green", "treasure": "yellow", "boss": "red", "normal": "gray"}[kind]
                    line.append((ch, "cyan", True) if c == self.pos else (ch, col, False))
                else:
                    line.append((" ", "gray", False))
            rows.append(line)
        return rows

    def door_cell(self, d, mid=False):
        if self.has_door(d):
            if self.cur().cleared: return (" ", "gray", False)
            nk = self.neighbor_kind(d)
            col = "red" if nk == "boss" else ("yellow" if nk == "treasure" else "magenta")
            return ("D", col, True) if mid else ("#", "wall", False)
        return ("#", "wall", False)

    def build_screen(self, overlay=None):
        s = Screen()
        s.text(0, 1, "Jakubinekks Gayme", "white", True)
        s.text(0, 23, "floor 1", "gray")
        c = 1
        for ch, fg, b in self.hearts_cells():
            s.put(1, c, ch, fg, b); c += 1
        c += 2
        for label, val in (("DMG", f"{self.damage:.1f}"), ("SPD", f"{self.speed:.1f}"),
                           ("RNG", f"{self.range:.1f}"), ("RATE", f"{self.fire_rate:.1f}"),
                           ("KILLS", str(self.kills))):
            s.text(1, c, label, "gray"); c += len(label) + 1
            s.text(1, c, val, "white"); c += len(val) + 2

        g = [[(" ", "gray", False) for _ in range(W)] for _ in range(H)]
        for y in range(H):
            for x in range(W):
                if (x * 13 + y * 7) % 23 == 0: g[y][x] = ("\u00b7", "dim", False)
        def put(x, y, cell):
            xi = max(0, min(W - 1, int(x))); yi = max(0, min(H - 1, int(y)))
            g[yi][xi] = cell
        def puttext(row, text, fg, bold=True):
            x0 = (W - len(text)) // 2
            for i, ch in enumerate(text):
                if 0 <= x0 + i < W and 0 <= row < H: g[row][x0 + i] = (ch, fg, bold)

        room = self.cur()
        for p in room.pickups: put(p.x, p.y, ("\u2665", "red", False))
        if room.kind == "treasure" and room.item and not room.taken:
            put(W / 2, H / 2, ("\u2666", "yellow", True))
            puttext(3, f"{room.item[0]} \u2014 {room.item[1]}", "yellow", False)
        for t in self.tears: put(t.x, t.y, ("*", "magenta" if t.hostile else "cyan", False))
        for e in self.enemies:
            put(e.x, e.y, (e.ch, "white" if e.hit_t > 0 else e.col, e.kind == "boss"))
        if self.invuln <= 0 or int(self.invuln * 12) % 2 == 0:
            put(self.px, self.py, ("@", "white", True))

        if overlay:
            for i, (txt, fg, b) in enumerate(overlay):
                puttext(H // 2 - 1 + i, txt, fg, b)
        if self.state == "dead":
            puttext(H // 2 - 1, "YOU DIED", "red")
            puttext(H // 2, "R: retry   Q: quit", "gray", False)
        elif self.state == "won":
            puttext(H // 2 - 1, "YOU WIN!", "green")
            puttext(H // 2, "R: new run   Q: quit", "gray", False)

        def wallrow(d):
            row = [("#", "wall", False)] * (W + 2)
            if self.has_door(d):
                cx = W // 2 + 1
                for i in (-1, 0, 1): row[cx + i] = self.door_cell(d, i == 0)
            return row

        frame = [wallrow("up")]
        for y in range(H):
            frame.append([self.door_cell("left", y == H // 2)] + g[y] +
                         [self.door_cell("right", y == H // 2)])
        frame.append(wallrow("down"))

        maps = self.minimap()
        top = 3
        for i, row in enumerate(frame):
            for ci, cell in enumerate(row): s.put(top + i, ci, *cell)
            if 1 <= i <= GRID:
                for ci, cell in enumerate(maps[i - 1]): s.put(top + i, W + 6 + ci, *cell)

        r = top + H + 2
        boss = next((e for e in self.enemies if e.kind == "boss"), None)
        if boss:
            s.text(r, 1, "BOSS", "magenta", True)
            n = max(0, int(28 * boss.hp / boss.maxhp))
            s.text(r, 6, "\u2588" * n, "red")
            s.text(r, 6 + n, "\u2591" * (28 - n), "dim")
        elif self.msg_t > 0:
            s.text(r, 1, self.msg, self.msg_fg)
        s.text(r + 1, 1, "WASD move \u00b7 arrows shoot \u00b7 P pause \u00b7 Q quit", "dim")
        return s.g

# ---------------- input ----------------
class Keys:
    MAP = {"Up": "up", "Down": "down", "Left": "left", "Right": "right",
           "Return": "enter", "Escape": "esc"}
    def __init__(self, root):
        self.down_set = set(); self.events = []
        root.bind("<KeyPress>", self._press)
        root.bind("<KeyRelease>", self._release)
    def _name(self, e):
        n = self.MAP.get(e.keysym)
        if n: return n
        if e.char and len(e.char) == 1 and e.char.isprintable():
            return e.char.lower()
        return None
    def _press(self, e):
        n = self._name(e)
        if n:
            if n not in self.down_set: self.events.append(n)
            self.down_set.add(n)
    def _release(self, e):
        n = self._name(e)
        if n: self.down_set.discard(n)
    def down(self, name): return name in self.down_set

# ---------------- window ----------------
class Window:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Jakubinekks Gayme")
        self.root.resizable(False, False)
        fam = self._pick_family()
        self.font = tkfont.Font(family=fam, size=13)
        self.bold = tkfont.Font(family=fam, size=13, weight="bold")
        self.cw = max(self.font.measure("M"), self.bold.measure("M"))
        self.ch = max(self.font.metrics("linespace"), self.bold.metrics("linespace"))
        pad = 10; self.pad = pad
        wpx = COLS * self.cw + 2 * pad
        hpx = ROWS * self.ch + 2 * pad
        self.canvas = tk.Canvas(self.root, width=wpx, height=hpx, bg=BG, highlightthickness=0)
        self.canvas.pack()
        self.items, self.state = {}, {}
        for r in range(ROWS):
            for c in range(COLS):
                x = pad + c * self.cw; y = pad + r * self.ch
                self.items[(r, c)] = self.canvas.create_text(x, y, anchor="nw", font=self.font,
                                                             fill=PAL["gray"], text=" ")
                self.state[(r, c)] = (" ", "gray", False)
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{max((sw - wpx) // 2, 0)}+{max((sh - hpx) // 2 - 30, 0)}")

    def _pick_family(self):
        fams = set(tkfont.families(self.root))
        for f in ("Consolas", "Menlo", "Monaco", "Cascadia Mono", "DejaVu Sans Mono", "Courier New"):
            if f in fams: return f
        return "Courier"

    def draw(self, screen):
        for r, line in enumerate(screen[:ROWS]):
            for c, cell in enumerate(line[:COLS]):
                if cell != self.state[(r, c)]:
                    self.state[(r, c)] = cell
                    ch, fg, bold = cell
                    self.canvas.itemconfig(self.items[(r, c)], text=ch, fill=PAL.get(fg, PAL["gray"]),
                                           font=self.bold if bold else self.font)

def draw_menu(win, now):
    s = Screen()
    s.center(4, "Jakubinekks Gayme", "white", True)
    s.center(5, "Eliminate kyle taylor", "gray")
    s.center(8,  "WASD ......... move", "white")
    s.center(9,  "ARROWS ....... shoot tears", "white")
    s.center(10, "P / Q ........ pause / quit", "white")
    x0 = s.center(12, "find the treasure $", "white")
    s.put(12, x0 + 18, "$", "yellow", True)
    s.text(12, x0 + 19, "SPLONKKY", "red", True)
    s.put(12, x0 + 48, "B", "red", True)
    if int(now * 2) % 2 == 0:
        s.center(15, "[ press ENTER to descend into Rileys basement ]", "green", True)
    win.draw(s.g)

# ---------------- main ----------------
def main():
    rng = random.Random()
    win = Window()
    keys = Keys(win.root)
    state, game, last = "menu", None, time.time()

    def loop():
        nonlocal state, game, last
        ev, keys.events = keys.events, []
        now = time.time(); dt = min(now - last, 0.05); last = now
        if state == "menu":
            draw_menu(win, now)
            if "enter" in ev: game = Game(rng); state = "play"
            if "q" in ev or "esc" in ev: win.root.destroy(); return
        elif state == "play":
            if "q" in ev: win.root.destroy(); return
            if "p" in ev: state = "pause"
            else:
                game.update(dt, keys)
                if game.state in ("dead", "won"): state = game.state
            win.draw(game.build_screen([("PAUSED", "cyan", True)] if state == "pause" else None))
        elif state == "pause":
            if "p" in ev: state = "play"
            if "q" in ev: win.root.destroy(); return
            win.draw(game.build_screen([("PAUSED", "cyan", True), ("P to resume", "gray", False)]))
        else:  # dead / won
            win.draw(game.build_screen())
            if "r" in ev: game = Game(rng); state = "play"
            if "q" in ev or "esc" in ev: win.root.destroy(); return
        win.root.after(TICK_MS, loop)

    win.root.protocol("WM_DELETE_WINDOW", win.root.destroy)
    win.root.focus_force()
    win.root.after(10, loop)
    try:
        win.root.mainloop()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()