"""Fuga do Banco - furtividade top-down em Pygame.  Execute: python main.py"""
import array, math, random, sys, pygame
from collections import deque
W, H, T, TOP = 1000, 700, 40, 60              # tela, tile e altura do HUD
MAPA = ["#########################",            # # parede, D mesa, E saida
        "#.....DD#.......#.......#",
        "#.......#.......#...DD..#",
        "#.......#...D...#.......#",
        "#.......#.......#.......#",
        "#.......#.......#.......#",
        "###.#######.#######.#####",
        "#................D......#",
        "#.....D.................#",
        "###.#######.#######.#####",
        "#.......#.......#.......#",
        "#....DD.#.......#.......#",
        "#.......#.......#.......#",
        "#.......#.....DD#.......#",
        "#.......#.......#......E#",
        "#########################"]
ROWS, COLS = len(MAPA), len(MAPA[0])
VEL_JOGADOR, VEL_PATRULHA, VEL_PERSEGUICAO = 200, 95, 175
TEMPO_BASE, FOV_GUARDA, ALCANCE_GUARDA, FOV_CAM, ALCANCE_CAM = 150, math.radians(70), 230, math.radians(50), 240
def centro(c, r): return (c * T + T / 2, r * T + T / 2 + TOP)
def tile(p): return int(p[0] // T), int((p[1] - TOP) // T)
def solido(c, r): return not (0 <= c < COLS and 0 <= r < ROWS) or MAPA[r][c] in "#D"
def mover(pos, dx, dy, meio=10):   # move por eixo: desliza nas paredes
    for novo in ((pos[0] + dx, pos[1]), (pos[0], pos[1] + dy)):
        if not any(solido(*tile((novo[0] + sx * meio, novo[1] + sy * meio))) for sx in (-1, 1) for sy in (-1, 1)):
            pos = list(novo)
    return pos
def linha_livre(a, b):
    n = int(math.dist(a, b) // 8) + 1
    return not any(solido(*tile((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n))) for i in range(n + 1))
def enxerga(o, ang, fov, alcance, p):   # alcance + campo de visao + sem parede no caminho
    if math.dist(o, p) > alcance: return False
    dif = (math.atan2(p[1] - o[1], p[0] - o[0]) - ang + math.pi) % (2 * math.pi) - math.pi
    return abs(dif) < fov / 2 and linha_livre(o, p)
def cone(o, ang, fov, alcance, raios=14):   # poligono do cone, cortado pelas paredes
    pts = [o]
    for i in range(raios + 1):
        a, r = ang - fov / 2 + fov * i / raios, 0
        while r < alcance and not solido(*tile((o[0] + math.cos(a) * r, o[1] + math.sin(a) * r))): r += 6
        pts.append((o[0] + math.cos(a) * r, o[1] + math.sin(a) * r))
    return pts
def proximo_passo(src, dst):   # BFS no grid: proximo tile do caminho src -> dst
    prev, fila = {src: None}, deque([src])
    while fila and dst not in prev:
        c = fila.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dy)
            if n not in prev and not solido(*n): prev[n] = c; fila.append(n)
    if dst not in prev or dst == src: return src
    while prev[dst] != src: dst = prev[dst]
    return dst
def beep(*freqs, ms=90):
    n, buf = int(22050 * ms / 1000), array.array("h")
    for f in freqs: buf.extend(int(8000 * math.sin(6.283 * f * i / 22050) * (1 - i / n)) for i in range(n))
    try: pygame.mixer.Sound(buffer=buf.tobytes()).play()
    except Exception: pass
class Player:
    def __init__(self, pos): self.pos, self.anim, self.dir = list(pos), 0, (1, 0)
    def update(self, dt, keys):
        dx, dy = keys[pygame.K_d] - keys[pygame.K_a], keys[pygame.K_s] - keys[pygame.K_w]
        if dx or dy:
            n = math.hypot(dx, dy); self.dir = (dx / n, dy / n); self.anim += dt * 12
            self.pos = mover(self.pos, self.dir[0] * VEL_JOGADOR * dt, self.dir[1] * VEL_JOGADOR * dt)
    def draw(self, s):
        x, y = self.pos; b = math.sin(self.anim) * 3
        pygame.draw.ellipse(s, (20, 20, 26), (x - 11, y + 5, 22, 10))
        pygame.draw.circle(s, (35, 35, 45), (x, y + b), 12)                       # corpo
        pygame.draw.circle(s, (225, 190, 150), (x + self.dir[0] * 4, y + self.dir[1] * 4 + b), 7)
        pygame.draw.rect(s, (15, 15, 20), (x + self.dir[0] * 4 - 7, y + self.dir[1] * 4 + b - 3, 14, 5))  # mascara
        pygame.draw.circle(s, (230, 230, 240), (x, y + b), 12, 2)
class Guard:
    def __init__(self, rota, mult):
        self.rota, self.i, self.passo = [centro(*t) for t in rota], 0, 1
        self.pos, self.ang, self.estado, self.t, self.mult, self.visto, self.ultimo = list(self.rota[0]), 0, "PATROL", 0, mult, False, None
    def ir_para(self, alvo, vel, dt):
        s, t = tile(self.pos), tile(alvo)
        meta = alvo if s == t else centro(*proximo_passo(s, t))
        d = math.dist(self.pos, meta)
        if d > 1:
            self.ang, k = math.atan2(meta[1] - self.pos[1], meta[0] - self.pos[0]), min(vel * dt, d) / d
            self.pos = [self.pos[0] + (meta[0] - self.pos[0]) * k, self.pos[1] + (meta[1] - self.pos[1]) * k]
        return math.dist(self.pos, alvo)
    def update(self, dt, alvo, forcado):
        self.visto = enxerga(self.pos, self.ang, FOV_GUARDA, ALCANCE_GUARDA, alvo)
        if self.estado == "PATROL":
            if self.ir_para(self.rota[self.i], VEL_PATRULHA * self.mult, dt) < 6:
                if not 0 <= self.i + self.passo < len(self.rota): self.passo *= -1   # A->B->C->B->A
                self.i += self.passo
            if self.visto: self.estado, self.t = "DETECT", 0
            elif forcado: self.estado, self.t = "CHASE", 0
        elif self.estado == "DETECT":                                  # para e encara por 0,5s
            self.t += dt; self.ang = math.atan2(alvo[1] - self.pos[1], alvo[0] - self.pos[0])
            if self.t > .5: self.estado, self.t = ("CHASE" if self.visto else "PATROL"), 0
        else:
            if self.visto: self.t, self.ultimo = 0, list(alvo)
            else: self.t += dt
            if self.ultimo is None: self.ultimo = list(alvo)
            self.ir_para(self.ultimo, VEL_PERSEGUICAO * self.mult, dt)
            if self.t > 3: self.estado, self.ultimo = "PATROL", None   # perdeu o jogador
    def draw(self, s):
        x, y = self.pos; cor = (200, 40, 40) if self.estado == "CHASE" else (50, 90, 180)
        pygame.draw.circle(s, cor, (x, y), 13); pygame.draw.circle(s, (240, 240, 250), (x, y), 13, 2)
        pygame.draw.line(s, (255, 255, 255), (x, y), (x + math.cos(self.ang) * 16, y + math.sin(self.ang) * 16), 3)
        pygame.draw.rect(s, (20, 25, 50), (x - 9, y - 16, 18, 5))       # bone
class Camera:
    def __init__(self, t, a0, a1, mult):
        self.pos, self.mid, self.amp, self.mult = centro(*t), math.radians((a0 + a1) / 2), math.radians(abs(a1 - a0) / 2), mult
    def angulo(self, t): return self.mid + self.amp * math.sin(t * .8 * self.mult)
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Fuga do Banco")
        try: pygame.mixer.init(22050, -16, 1)
        except pygame.error: pass
        self.tela, self.clock, self.fontes = pygame.display.set_mode((W, H)), pygame.time.Clock(), {}
        self.fog, self.estado, self.sel, self.nivel, self.bg = pygame.Surface((W, H), pygame.SRCALPHA), "menu", 0, 0, self.montar_fundo()
    def texto(self, s, tam, cor, pos, ancora="c", alvo=None):
        f = self.fontes.setdefault(tam, pygame.font.SysFont("consolas,dejavusansmono,arial", tam, bold=True))
        img = f.render(s, True, cor); r = img.get_rect()
        setattr(r, {"c": "center", "l": "midleft", "r": "midright"}[ancora], pos); (alvo or self.tela).blit(img, r)
    def montar_fundo(self):
        s = pygame.Surface((W, H)); s.fill((18, 20, 28))
        for r in range(ROWS):
            for c in range(COLS):
                ch, rect = MAPA[r][c], (c * T, r * T + TOP, T, T)
                cofre, corr = c >= 17 and r <= 5, 7 <= r <= 8
                base = (84, 72, 44) if cofre else (62, 66, 84) if corr else (48, 54, 66)
                if ch == "#": s.fill((52, 58, 78), rect); s.fill((88, 96, 124), rect[:3] + (6,))
                else: s.fill(tuple(v + 6 * ((r + c) % 2) for v in base), rect)
                if ch == "D": s.fill((110, 74, 44), (rect[0] + 3, rect[1] + 5, T - 6, T - 10)); s.fill((140, 98, 60), (rect[0] + 3, rect[1] + 5, T - 6, 6))
        for nome, pos in (("COFRE", (20, 5)), ("ENTRADA", (4, 14)), ("SAIDA", (23, 13))): self.texto(nome, 14, (230, 220, 180), centro(*pos), alvo=s)
        return s
    def novo_jogo(self):
        m = 1 + .12 * self.nivel
        self.p = Player(centro(2, 13))
        self.guardas = [Guard([(2, 7), (12, 8), (22, 7)], m), Guard([(10, 1), (14, 1), (14, 5), (10, 5)], m),
                        Guard([(18, 12), (22, 12), (22, 10), (18, 10)], m)]
        self.cams = [Camera((1, 1), 10, 80, m), Camera((23, 1), 100, 170, m)]
        self.sacos = [centro(3, 3), centro(20, 4), centro(11, 12)]
        self.dinheiro, self.alerta, self.alertas, self.armado = 0, 0, 0, True
        self.tempo, self.t, self.fx, self.pops, self.aviso, self.estado = TEMPO_BASE + 10 * self.nivel, 0, [], [], "", "jogo"
    def fim(self, estado, motivo=""):
        self.estado, self.motivo = estado, motivo
        if estado == "derrota": beep(300, 200, 120, ms=160)
        else: beep(520, 660, 880, ms=120); self.fx += [[500, 300, random.uniform(-200, 200), random.uniform(-300, 0), 1.6, random.choice([(255, 215, 0), (255, 255, 255), (80, 220, 120)])] for _ in range(120)]
    def update(self, dt):
        p = self.p; self.t += dt; self.tempo -= dt; p.update(dt, pygame.key.get_pressed())
        for g in self.guardas:
            g.update(dt, p.pos, self.alerta >= 100 and math.dist(g.pos, p.pos) < 450)
            if math.dist(g.pos, p.pos) < 26:
                if g.estado == "CHASE": return self.fim("derrota", "VOCE FOI PEGO!")
                g.estado = "CHASE"
        olhado = 60 if any(g.visto for g in self.guardas) else 35 if any(enxerga(c.pos, c.angulo(self.t), FOV_CAM, ALCANCE_CAM, p.pos) for c in self.cams) else 0
        self.alerta = max(0, min(100, self.alerta + (olhado or -12) * dt))
        if self.alerta >= 100 and self.armado: self.armado, self.alertas = False, self.alertas + 1; beep(880, 660, 880)
        self.armado = self.armado or self.alerta < 40
        self.aviso = "Pressione E para pegar" if any(math.dist(s, p.pos) < 48 for s in self.sacos) else ""
        if math.dist(p.pos, centro(23, 14)) < 34:
            if self.dinheiro == 3: return self.fim("vitoria")
            self.aviso = "Pegue todo o dinheiro antes de sair!"
        if self.tempo <= 0: return self.fim("derrota", "TEMPO ESGOTADO!")
    def coletar(self):
        for s in [s for s in self.sacos if math.dist(s, self.p.pos) < 48][:1]:
            self.sacos.remove(s); self.dinheiro += 1; beep(990, 1320, ms=70); self.pops.append([s[0], s[1], 1.2])
            self.fx += [[s[0], s[1], random.uniform(-90, 90), random.uniform(-120, 20), .7, (255, 215, 0)] for _ in range(14)]
    def desenhar_jogo(self):
        sc = self.tela; sc.blit(self.bg, (0, 0)); self.fog.fill((0, 0, 0, 0))
        for g in self.guardas: pygame.draw.polygon(self.fog, (255, 60, 60, 95) if g.estado == "CHASE" else (255, 230, 90, 70), cone(g.pos, g.ang, FOV_GUARDA, ALCANCE_GUARDA))
        for c in self.cams: pygame.draw.polygon(self.fog, (255, 60, 60, 70) if self.alerta > 0 else (90, 220, 255, 60), cone(c.pos, c.angulo(self.t), FOV_CAM, ALCANCE_CAM))
        sc.blit(self.fog, (0, 0))
        pygame.draw.rect(sc, (30, int(180 + 60 * math.sin(self.t * 5)), 60), (23 * T + 3, 14 * T + TOP + 3, T - 6, T - 6), 0 if self.dinheiro == 3 else 3)
        for c in self.cams:
            pygame.draw.circle(sc, (30, 30, 36), c.pos, 10); a = c.angulo(self.t)
            pygame.draw.line(sc, (200, 60, 60), c.pos, (c.pos[0] + math.cos(a) * 14, c.pos[1] + math.sin(a) * 14), 5)
        for s in self.sacos:
            y = s[1] + math.sin(self.t * 4) * 2
            pygame.draw.circle(sc, (200, 160, 30), (s[0], y), 15); pygame.draw.circle(sc, (255, 220, 70), (s[0], y), 15, 2); self.texto("$", 20, (90, 60, 0), (s[0], y))
        self.p.draw(sc)
        for g in self.guardas:
            g.draw(sc)
            if g.estado != "PATROL": self.texto("!" if g.estado == "CHASE" else "?", 26, (255, 70, 70) if g.estado == "CHASE" else (255, 230, 90), (g.pos[0], g.pos[1] - 28))
        if self.alerta > 0: self.fog.fill((255, 0, 0, int(self.alerta * .55))); sc.blit(self.fog, (0, 0))
        self.hud()
    def hud(self):
        sc = self.tela; pygame.draw.rect(sc, (12, 14, 22), (0, 0, W, TOP))
        self.texto(f"DINHEIRO: {self.dinheiro}/3", 22, (255, 215, 70), (20, 18), "l")
        self.texto("OBJETIVO ATUAL: ESCAPE DO BANCO" if self.dinheiro == 3 else "OBJETIVO: roube os 3 sacos de dinheiro", 15, (120, 255, 150) if self.dinheiro == 3 else (190, 190, 210), (20, 44), "l")
        t = max(0, int(self.tempo)); self.texto(f"TEMPO: {t // 60:02d}:{t % 60:02d}", 22, (255, 90, 90) if t < 20 else (240, 240, 250), (500, 30))
        self.texto("ALERTA", 22, (255, 60, 60) if self.alerta >= 70 and int(self.t * 6) % 2 else (240, 240, 250), (690, 30), "r")
        for i in range(10):
            cor = (255 - i * 8, 230 - i * 20, 60) if i < int(self.alerta / 10 + .99) else (45, 48, 62)
            pygame.draw.rect(sc, cor, (700 + i * 28, 16, 24, 28))
        if self.alerta >= 100: self.texto("PERSEGUICAO!", 20, (255, 70, 70), (500, 90))
        if self.aviso: self.texto(self.aviso, 20, (255, 255, 255), (max(150, min(850, self.p.pos[0])), self.p.pos[1] - 34))
    def efeitos(self, dt):
        for f in self.fx: f[0] += f[2] * dt; f[1] += f[3] * dt; f[3] += 300 * dt; f[4] -= dt; pygame.draw.circle(self.tela, f[5], (f[0], f[1]), 3)
        self.fx = [f for f in self.fx if f[4] > 0]
        for q in self.pops: q[1] -= 40 * dt; q[2] -= dt; self.texto("+$10.000", 20, (255, 230, 90), (q[0], q[1]))
        self.pops = [q for q in self.pops if q[2] > 0]
    def veu(self, alfa): self.fog.fill((8, 10, 20, alfa)); self.tela.blit(self.fog, (0, 0))
    def telas(self):
        sc = self.tela
        if self.estado in ("vitoria", "derrota"):
            self.veu(170); ok = self.estado == "vitoria"
            self.texto("VOCE ESCAPOU!" if ok else self.motivo, 56, (120, 255, 150) if ok else (255, 80, 80), (500, 200))
            if ok:
                t = int(self.t); pts = max(0, self.dinheiro * 300 + int(self.tempo) * 3 - self.alertas * 50)
                for i, l in enumerate((f"DINHEIRO ROUBADO: ${self.dinheiro * 10000:,}".replace(",", "."), f"TEMPO: {t // 60:02d}:{t % 60:02d}", f"ALERTAS: {self.alertas}", f"PONTUACAO: {pts}")):
                    self.texto(l, 28, (255, 230, 120), (500, 290 + i * 44))
            self.texto("ENTER -> " + ("Jogar novamente (mais dificil)" if ok else "Tentar novamente") + "     ESC -> Menu", 22, (230, 230, 240), (500, 520))
        elif self.estado == "menu":
            sc.blit(self.bg, (0, 0)); self.veu(215)
            self.texto("FUGA DO BANCO", 72, (255, 215, 70), (500, 150))
            self.texto("roube 3 sacos, evite guardas e cameras, escape", 18, (180, 185, 210), (500, 215))
            for i, o in enumerate(("JOGAR", "COMO JOGAR", "SAIR")):
                self.texto(f"[ {o} ]" if i == self.sel else o, 34, (255, 255, 255) if i == self.sel else (130, 135, 160), (500, 320 + i * 70))
            self.texto("W/S ou setas + ENTER", 16, (130, 135, 160), (500, 640))
        elif self.estado == "ajuda":
            sc.blit(self.bg, (0, 0)); self.veu(225)
            self.texto("COMO JOGAR", 48, (255, 215, 70), (500, 120))
            for i, l in enumerate(("WASD - mover", "E - pegar o saco de dinheiro (fique perto)", "Fuja dos cones de visao de guardas e cameras",
                                   "A barra ALERTA enche quando voce e visto", "Alerta cheio = guardas por perto te perseguem",
                                   "Pegue os 3 sacos e va ate a SAIDA verde", "ESC - voltar ao menu")): self.texto(l, 24, (225, 225, 240), (500, 220 + i * 50))
    def eventos(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            if e.type != pygame.KEYDOWN: continue
            if e.key == pygame.K_ESCAPE:
                if self.estado == "menu": pygame.quit(); sys.exit()
                self.estado = "menu"
            elif self.estado == "menu":
                self.sel = (self.sel + (e.key in (pygame.K_s, pygame.K_DOWN)) - (e.key in (pygame.K_w, pygame.K_UP))) % 3
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.sel == 0: self.nivel = 0; self.novo_jogo()
                    elif self.sel == 1: self.estado = "ajuda"
                    else: pygame.quit(); sys.exit()
            elif self.estado == "jogo" and e.key == pygame.K_e: self.coletar()
            elif self.estado in ("vitoria", "derrota") and e.key == pygame.K_RETURN:
                self.nivel = self.nivel + 1 if self.estado == "vitoria" else self.nivel; self.novo_jogo()
    def run(self):
        while True:
            dt = min(self.clock.tick(60) / 1000, .05); self.eventos()
            if self.estado == "jogo": self.update(dt)
            if self.estado in ("jogo", "vitoria", "derrota"): self.desenhar_jogo(); self.efeitos(dt)
            self.telas(); pygame.display.flip()
if __name__ == "__main__": Game().run()
