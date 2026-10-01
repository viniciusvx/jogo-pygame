"""Fuga do Banco - jogo de furtividade top-down em Pygame.

Execute com:  python main.py
Controles: WASD move, E pega o dinheiro, ENTER confirma, ESC volta ao menu.
"""
import array
import math
import random
import sys
from collections import deque

import pygame

# --------------------------------------------------------------------------
# Configuracao
# --------------------------------------------------------------------------
W, H = 1000, 700            # tamanho da janela
T = 40                      # tamanho de um tile
TOP = 60                    # altura do HUD

# '#' parede, 'D' mesa/estante, 'E' saida
MAPA = [
    "########################################",
    "#........#..........#..........#.......#",
    "#....DDD.#..........#..DDDDDD..#.DD....#",
    "#........#....DD....#..........#.......#",
    "#........#....DD....#..........#.......#",
    "#....DDD.#..........#..........#.DD....#",
    "#........#..........#..........#.......#",
    "####.#########.##########.#########.####",
    "#...............D......................#",
    "#.............................D........#",
    "######.############.############.#######",
    "#............#............#............#",
    "#............#............#............#",
    "#...DD..DD...#..D..DD.....#..DD........#",
    "#............#.....DD..D..#..DD........#",
    "#...DD..DD...#............#............#",
    "#............#............#............#",
    "######.############.############.#######",
    "#.......D..............................#",
    "#.......................D..............#",
    "#####.##########.#########.########.####",
    "#.........#...........#.......#........#",
    "#.D.....D.#..DD...DD..#.DD....#........#",
    "#.D.....D.#...........#....DD.#..DD....#",
    "#.........#...........#..D....#.......E#",
    "########################################",
]
ROWS, COLS = len(MAPA), len(MAPA[0])
MAPW, MAPH = COLS * T, ROWS * T + TOP

NS = 8                      # sacos de dinheiro no mapa
VALOR_SACO = 10000
COMECO, SAIDA = (5, 22), (38, 24)   # tiles

# Salas: (nome, col0, linha0, col1, linha1, cor do piso)
SALAS = [
    ("ARQUIVO", 1, 1, 8, 6, (58, 50, 66)),
    ("GERÊNCIA", 10, 1, 19, 6, (52, 60, 56)),
    ("SEGURANÇA", 21, 1, 30, 6, (44, 56, 80)),
    ("COFRE", 32, 1, 38, 6, (84, 72, 44)),
    ("CORREDOR", 1, 8, 38, 9, (62, 66, 84)),
    ("TESOURARIA", 1, 11, 12, 16, (66, 56, 48)),
    ("SALÃO", 14, 11, 25, 16, (50, 62, 70)),
    ("SALA DE CONTAS", 27, 11, 38, 16, (74, 66, 50)),
    ("CORREDOR", 1, 18, 38, 19, (62, 66, 84)),
    ("ENTRADA", 1, 21, 9, 24, (48, 54, 66)),
    ("COPA", 11, 21, 21, 24, (66, 54, 58)),
    ("DEPÓSITO", 23, 21, 29, 24, (58, 56, 50)),
    ("SAÍDA", 31, 21, 38, 24, (40, 70, 56)),
]

# Rotas dos guardas (tiles). Ida e volta: A -> B -> C -> B -> A
ROTAS_GUARDAS = [
    [(2, 8), (19, 9), (37, 8)],
    [(2, 19), (19, 18), (37, 19)],
    [(15, 12), (24, 12), (24, 15), (15, 15)],
    [(11, 2), (18, 2), (18, 5), (11, 5)],
    [(32, 22), (36, 22), (36, 24), (32, 24)],
]
# Cameras: (tile, angulo minimo, angulo maximo) em graus; 0 = direita, 90 = baixo
CAMERAS = [((1, 1), 10, 80), ((38, 1), 100, 170), ((1, 11), 10, 80), ((38, 11), 100, 170)]
SACOS = [(3, 3), (36, 3), (3, 14), (36, 14), (16, 23), (18, 3), (22, 5), (26, 23)]

VEL_JOGADOR, VEL_PATRULHA, VEL_PERSEGUICAO = 200, 95, 175
TEMPO_BASE = 240
FOV_GUARDA, ALCANCE_GUARDA = math.radians(70), 230
FOV_CAM, ALCANCE_CAM = math.radians(50), 240


# --------------------------------------------------------------------------
# Funcoes do mapa e da visao
# --------------------------------------------------------------------------
def centro(c, r):
    """Centro (em pixels do mundo) do tile (c, r)."""
    return (c * T + T / 2, r * T + T / 2 + TOP)


def tile(p):
    return int(p[0] // T), int((p[1] - TOP) // T)


def solido(c, r):
    return not (0 <= c < COLS and 0 <= r < ROWS) or MAPA[r][c] in "#D"


def solido_em(p):
    return solido(*tile(p))


def mover(pos, dx, dy, meio=10):
    """Move um eixo por vez, assim o jogador desliza nas paredes."""
    for ddx, ddy in ((dx, 0), (0, dy)):
        novo = (pos[0] + ddx, pos[1] + ddy)
        if not any(solido_em((novo[0] + sx * meio, novo[1] + sy * meio)) for sx in (-1, 1) for sy in (-1, 1)):
            pos = list(novo)
    return pos


def linha_livre(a, b):
    """True se nao ha parede entre a e b."""
    n = int(math.dist(a, b) // 8) + 1
    return not any(
        solido_em((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)) for i in range(n + 1)
    )


def enxerga(origem, ang, fov, alcance, alvo):
    """Deteccao: dentro do alcance, dentro do campo de visao e sem parede no caminho."""
    if math.dist(origem, alvo) > alcance:
        return False
    dif = (math.atan2(alvo[1] - origem[1], alvo[0] - origem[0]) - ang + math.pi) % (2 * math.pi) - math.pi
    return abs(dif) < fov / 2 and linha_livre(origem, alvo)


def cone(origem, ang, fov, alcance, raios=14):
    """Poligono do cone de visao, cortado pelas paredes."""
    pontos = [origem]
    for i in range(raios + 1):
        a = ang - fov / 2 + fov * i / raios
        r = 0
        while r < alcance and not solido_em((origem[0] + math.cos(a) * r, origem[1] + math.sin(a) * r)):
            r += 6
        pontos.append((origem[0] + math.cos(a) * r, origem[1] + math.sin(a) * r))
    return pontos


def proximo_passo(origem, destino):
    """BFS no grid: proximo tile do caminho origem -> destino."""
    anterior, fila = {origem: None}, deque([origem])
    while fila and destino not in anterior:
        c = fila.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dy)
            if n not in anterior and not solido(*n):
                anterior[n] = c
                fila.append(n)
    if destino not in anterior or destino == origem:
        return origem
    while anterior[destino] != origem:
        destino = anterior[destino]
    return destino


def beep(*freqs, ms=90):
    """Efeito sonoro simples gerado na hora; sem audio o jogo segue normalmente."""
    n, buf = int(22050 * ms / 1000), array.array("h")
    for f in freqs:
        buf.extend(int(8000 * math.sin(6.283 * f * i / 22050) * (1 - i / n)) for i in range(n))
    try:
        pygame.mixer.Sound(buffer=buf.tobytes()).play()
    except Exception:
        pass


# --------------------------------------------------------------------------
# Personagens
# --------------------------------------------------------------------------
class Player:
    def __init__(self, pos):
        self.pos = list(pos)
        self.anim = 0.0
        self.dir = (1, 0)

    def update(self, dt, teclas):
        dx = teclas[pygame.K_d] - teclas[pygame.K_a]
        dy = teclas[pygame.K_s] - teclas[pygame.K_w]
        if dx or dy:
            n = math.hypot(dx, dy)
            self.dir = (dx / n, dy / n)
            self.anim += dt * 12
            self.pos = mover(self.pos, self.dir[0] * VEL_JOGADOR * dt, self.dir[1] * VEL_JOGADOR * dt)

    def draw(self, s, ox, oy):
        x, y = self.pos[0] + ox, self.pos[1] + oy
        bob = math.sin(self.anim) * 3
        hx, hy = x + self.dir[0] * 4, y + self.dir[1] * 4 + bob
        pygame.draw.ellipse(s, (20, 20, 26), (x - 11, y + 5, 22, 10))
        pygame.draw.circle(s, (35, 35, 45), (x, y + bob), 12)
        pygame.draw.circle(s, (225, 190, 150), (hx, hy), 7)
        pygame.draw.rect(s, (15, 15, 20), (hx - 7, hy - 3, 14, 5))          # mascara
        pygame.draw.circle(s, (230, 230, 240), (x, y + bob), 12, 2)


class Guard:
    """Maquina de estados: PATROL -> DETECT -> CHASE -> PATROL."""

    def __init__(self, rota, mult):
        self.rota = [centro(*t) for t in rota]
        self.i, self.passo = 0, 1
        self.pos = list(self.rota[0])
        self.ang = 0.0
        self.estado = "PATROL"
        self.t = 0.0
        self.mult = mult
        self.visto = False
        self.ultimo = None          # ultima posicao conhecida do jogador

    def ir_para(self, alvo, vel, dt):
        """Anda ate o alvo contornando paredes (BFS). Devolve a distancia restante."""
        s, t = tile(self.pos), tile(alvo)
        meta = alvo if s == t else centro(*proximo_passo(s, t))
        d = math.dist(self.pos, meta)
        if d > 1:
            self.ang = math.atan2(meta[1] - self.pos[1], meta[0] - self.pos[0])
            k = min(vel * dt, d) / d
            self.pos = [self.pos[0] + (meta[0] - self.pos[0]) * k, self.pos[1] + (meta[1] - self.pos[1]) * k]
        return math.dist(self.pos, alvo)

    def update(self, dt, alvo, forcado):
        self.visto = enxerga(self.pos, self.ang, FOV_GUARDA, ALCANCE_GUARDA, alvo)
        if self.estado == "PATROL":
            if self.ir_para(self.rota[self.i], VEL_PATRULHA * self.mult, dt) < 6:
                if not 0 <= self.i + self.passo < len(self.rota):
                    self.passo *= -1
                self.i += self.passo
            if self.visto:
                self.estado, self.t = "DETECT", 0
            elif forcado:
                self.estado, self.t = "CHASE", 0
        elif self.estado == "DETECT":               # para e encara o jogador por 0,5 s
            self.t += dt
            self.ang = math.atan2(alvo[1] - self.pos[1], alvo[0] - self.pos[0])
            if self.t > 0.5:
                self.estado, self.t = ("CHASE" if self.visto else "PATROL"), 0
        else:                                       # CHASE
            if self.visto:
                self.t, self.ultimo = 0, list(alvo)
            else:
                self.t += dt
            if self.ultimo is None:
                self.ultimo = list(alvo)
            self.ir_para(self.ultimo, VEL_PERSEGUICAO * self.mult, dt)
            if self.t > 3:                          # perdeu o jogador de vista
                self.estado, self.ultimo = "PATROL", None

    def draw(self, s, ox, oy, texto):
        x, y = self.pos[0] + ox, self.pos[1] + oy
        perseguindo = self.estado == "CHASE"
        pygame.draw.circle(s, (200, 40, 40) if perseguindo else (50, 90, 180), (x, y), 13)
        pygame.draw.circle(s, (240, 240, 250), (x, y), 13, 2)
        pygame.draw.line(s, (255, 255, 255), (x, y), (x + math.cos(self.ang) * 16, y + math.sin(self.ang) * 16), 3)
        pygame.draw.rect(s, (20, 25, 50), (x - 9, y - 16, 18, 5))           # bone
        if self.estado != "PATROL":
            texto("!" if perseguindo else "?", 26, (255, 70, 70) if perseguindo else (255, 230, 90), x, y - 28)


class Camera:
    """Camera de seguranca que gira lentamente entre dois angulos."""

    def __init__(self, tile_, a0, a1, mult):
        self.pos = centro(*tile_)
        self.meio = math.radians((a0 + a1) / 2)
        self.amp = math.radians(abs(a1 - a0) / 2)
        self.mult = mult

    def angulo(self, t):
        return self.meio + self.amp * math.sin(t * 0.8 * self.mult)


# --------------------------------------------------------------------------
# Jogo
# --------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Fuga do Banco")
        try:
            pygame.mixer.init(22050, -16, 1)
        except pygame.error:
            pass
        self.tela = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.fontes = {}
        self.fog = pygame.Surface((W, H), pygame.SRCALPHA)      # cones de visao e filtros translucidos
        self.bg = self.montar_fundo()
        self.mini = self.montar_minimapa()
        self.estado, self.sel, self.nivel = "menu", 0, 0
        self.motivo = ""
        self.t = self.tempo = 0.0
        self.cx = self.cy = 0.0
        self.dt = 0.0

    # ----- texto e desenho auxiliar -----
    def texto(self, s, tam, cor, x, y, ancora="c", alvo=None):
        fonte = self.fontes.setdefault(tam, pygame.font.SysFont("consolas,dejavusansmono,arial", tam, bold=True))
        img = fonte.render(s, True, cor)
        r = img.get_rect()
        setattr(r, {"c": "center", "l": "midleft", "r": "midright"}[ancora], (x, y))
        (alvo or self.tela).blit(img, r)

    def poligono(self, pontos, cor, ox, oy):
        pygame.draw.polygon(self.fog, cor, [(x + ox, y + oy) for x, y in pontos])

    def veu(self, alfa):
        self.fog.fill((8, 10, 20, alfa))
        self.tela.blit(self.fog, (0, 0))

    # ----- fundo e minimapa (desenhados uma vez) -----
    def montar_fundo(self):
        s = pygame.Surface((MAPW, MAPH))
        s.fill((18, 20, 28))
        for r in range(ROWS):
            for c in range(COLS):
                ch, x, y = MAPA[r][c], c * T, r * T + TOP
                sala = next((sl for sl in SALAS if sl[1] <= c <= sl[3] and sl[2] <= r <= sl[4]), None)
                base = sala[5] if sala else (48, 54, 66)
                if ch == "#":
                    s.fill((52, 58, 78), (x, y, T, T))
                    s.fill((88, 96, 124), (x, y, T, 6))
                else:
                    s.fill(tuple(v + 6 * ((r + c) % 2) for v in base), (x, y, T, T))
                if ch == "D":
                    s.fill((110, 74, 44), (x + 3, y + 5, T - 6, T - 10))
                    s.fill((140, 98, 60), (x + 3, y + 5, T - 6, 6))
        for nome, c0, r0, c1, _, _ in SALAS:
            if nome != "CORREDOR" or c0 == 1:       # um rotulo por corredor
                pos = centro((c0 + c1) / 2 - 0.5, r0 + (0 if nome == "CORREDOR" else 0.5))
                self.texto(nome, 14, (230, 220, 180), pos[0], pos[1], alvo=s)
        return s

    def montar_minimapa(self):
        m = pygame.Surface((COLS * 4, ROWS * 4), pygame.SRCALPHA)
        m.fill((8, 10, 20, 204))
        for r in range(ROWS):
            for c in range(COLS):
                if MAPA[r][c] in "#D":
                    m.fill((90, 98, 130) if MAPA[r][c] == "#" else (110, 74, 44), (c * 4, r * 4, 4, 4))
        return m

    # ----- partida -----
    def novo_jogo(self):
        mult = 1 + 0.12 * self.nivel               # cada vitoria deixa o jogo um pouco mais dificil
        self.p = Player(centro(*COMECO))
        self.guardas = [Guard(rota, mult) for rota in ROTAS_GUARDAS]
        self.cams = [Camera(t, a0, a1, mult) for t, a0, a1 in CAMERAS]
        self.sacos = [centro(*t) for t in SACOS]
        self.dinheiro, self.alerta, self.alertas, self.armado = 0, 0.0, 0, True
        self.tempo = TEMPO_BASE + 10 * self.nivel
        self.t = 0.0
        self.fx, self.pops, self.aviso = [], [], ""
        self.estado = "jogo"

    def fim(self, estado, motivo=""):
        self.estado, self.motivo = estado, motivo
        if estado == "derrota":
            beep(300, 200, 120, ms=160)
        else:
            beep(520, 660, 880, ms=120)
            cores = [(255, 215, 0), (255, 255, 255), (80, 220, 120)]
            self.fx += [[self.cx + 500, self.cy + 300, random.uniform(-200, 200), random.uniform(-300, 0), 1.6, cores[i % 3]]
                        for i in range(120)]

    def update(self, dt):
        p = self.p
        self.t += dt
        self.tempo -= dt
        p.update(dt, pygame.key.get_pressed())

        for g in self.guardas:
            g.update(dt, p.pos, self.alerta >= 100 and math.dist(g.pos, p.pos) < 450)
            if math.dist(g.pos, p.pos) < 26:
                if g.estado == "CHASE":
                    return self.fim("derrota", "VOCÊ FOI PEGO!")
                g.estado = "CHASE"

        # Alerta: sobe quando algum guarda ou camera enxerga o jogador, desce aos poucos quando nao.
        if any(g.visto for g in self.guardas):
            olhado = 60
        elif any(enxerga(c.pos, c.angulo(self.t), FOV_CAM, ALCANCE_CAM, p.pos) for c in self.cams):
            olhado = 35
        else:
            olhado = 0
        self.alerta = max(0, min(100, self.alerta + (olhado or -12) * dt))
        if self.alerta >= 100 and self.armado:
            self.armado, self.alertas = False, self.alertas + 1
            beep(880, 660, 880)
        self.armado = self.armado or self.alerta < 40

        self.aviso = "Pressione E para pegar" if any(math.dist(s, p.pos) < 48 for s in self.sacos) else ""
        if math.dist(p.pos, centro(*SAIDA)) < 34:
            if self.dinheiro == NS:
                return self.fim("vitoria")
            self.aviso = "Pegue todo o dinheiro antes de sair!"
        if self.tempo <= 0:
            return self.fim("derrota", "TEMPO ESGOTADO!")

    def coletar(self):
        perto = [s for s in self.sacos if math.dist(s, self.p.pos) < 48]
        if not perto:
            return
        s = perto[0]
        self.sacos.remove(s)
        self.dinheiro += 1
        beep(990, 1320, ms=70)
        self.pops.append([s[0], s[1], 1.2])
        self.fx += [[s[0], s[1], random.uniform(-90, 90), random.uniform(-120, 20), 0.7, (255, 215, 0)] for _ in range(14)]

    # ----- desenho -----
    def desenhar_jogo(self):
        sc, p = self.tela, self.p
        self.cx = max(0, min(MAPW - W, p.pos[0] - W / 2))
        self.cy = max(0, min(MAPH - H, p.pos[1] - H / 2))
        ox, oy = -round(self.cx), -round(self.cy)             # deslocamento da camera

        sc.blit(self.bg, (ox, oy))
        self.fog.fill((0, 0, 0, 0))
        for g in self.guardas:
            cor = (255, 60, 60, 95) if g.estado == "CHASE" else (255, 230, 90, 70)
            self.poligono(cone(g.pos, g.ang, FOV_GUARDA, ALCANCE_GUARDA), cor, ox, oy)
        for c in self.cams:
            cor = (255, 60, 60, 70) if self.alerta > 0 else (90, 220, 255, 60)
            self.poligono(cone(c.pos, c.angulo(self.t), FOV_CAM, ALCANCE_CAM), cor, ox, oy)
        sc.blit(self.fog, (0, 0))

        # saida
        ex, ey = SAIDA[0] * T + 3 + ox, SAIDA[1] * T + TOP + 3 + oy
        pulso = (30, int(180 + 60 * math.sin(self.t * 5)), 60)
        pygame.draw.rect(sc, pulso, (ex, ey, T - 6, T - 6), 0 if self.dinheiro == NS else 3)

        for c in self.cams:
            a = c.angulo(self.t)
            cx, cy = c.pos[0] + ox, c.pos[1] + oy
            pygame.draw.circle(sc, (30, 30, 36), (cx, cy), 10)
            pygame.draw.line(sc, (200, 60, 60), (cx, cy), (cx + math.cos(a) * 14, cy + math.sin(a) * 14), 5)
        for s in self.sacos:
            x, y = s[0] + ox, s[1] + oy + math.sin(self.t * 4) * 2
            pygame.draw.circle(sc, (200, 160, 30), (x, y), 15)
            pygame.draw.circle(sc, (255, 220, 70), (x, y), 15, 2)
            self.texto("$", 20, (90, 60, 0), x, y)

        p.draw(sc, ox, oy)
        for g in self.guardas:
            g.draw(sc, ox, oy, self.texto)
        self.efeitos(ox, oy)

        if self.alerta > 0:                                    # a tela fica avermelhada quando ha alerta
            self.fog.fill((255, 0, 0, int(self.alerta * 0.55)))
            sc.blit(self.fog, (0, 0))
        self.hud(ox, oy)
        self.minimapa()

    def efeitos(self, ox, oy):
        dt = self.dt
        for f in self.fx:
            f[0] += f[2] * dt
            f[1] += f[3] * dt
            f[3] += 300 * dt
            f[4] -= dt
            pygame.draw.circle(self.tela, f[5], (f[0] + ox, f[1] + oy), 3)
        self.fx = [f for f in self.fx if f[4] > 0]
        for q in self.pops:
            q[1] -= 40 * dt
            q[2] -= dt
            self.texto(f"+${VALOR_SACO:,}".replace(",", "."), 20, (255, 230, 90), q[0] + ox, q[1] + oy)
        self.pops = [q for q in self.pops if q[2] > 0]

    def minimapa(self):
        x, y = W - self.mini.get_width() - 10, H - self.mini.get_height() - 10
        self.tela.blit(self.mini, (x, y))

        def ponto(pos, cor, r):
            pygame.draw.rect(self.tela, cor, (x + pos[0] / T * 4 - r, y + (pos[1] - TOP) / T * 4 - r, r * 2, r * 2))

        ponto(centro(*SAIDA), (60, 255, 120), 2)
        for s in self.sacos:
            ponto(s, (255, 215, 70), 2)
        ponto(self.p.pos, (255, 255, 255), 3)

    def hud(self, ox, oy):
        pygame.draw.rect(self.tela, (12, 14, 22), (0, 0, W, TOP))
        pronto = self.dinheiro == NS
        self.texto(f"DINHEIRO: {self.dinheiro}/{NS}", 22, (255, 215, 70), 20, 18, "l")
        objetivo = "OBJETIVO ATUAL: ESCAPE DO BANCO" if pronto else f"OBJETIVO: roube os {NS} sacos de dinheiro"
        self.texto(objetivo, 15, (120, 255, 150) if pronto else (190, 190, 210), 20, 44, "l")
        seg = max(0, int(self.tempo))
        self.texto(f"TEMPO: {seg // 60:02d}:{seg % 60:02d}", 22, (255, 90, 90) if seg < 20 else (240, 240, 250), 500, 30)
        piscando = self.alerta >= 70 and int(self.t * 6) % 2
        self.texto("ALERTA", 22, (255, 60, 60) if piscando else (240, 240, 250), 690, 30, "r")
        cheios = int(self.alerta / 10 + 0.99)
        for i in range(10):
            cor = (255 - i * 8, 230 - i * 20, 60) if i < cheios else (45, 48, 62)
            pygame.draw.rect(self.tela, cor, (700 + i * 28, 16, 24, 28))
        if self.alerta >= 100:
            self.texto("PERSEGUIÇÃO!", 20, (255, 70, 70), 500, 90)
        if self.aviso:
            x = max(150, min(850, self.p.pos[0] + ox))
            self.texto(self.aviso, 20, (255, 255, 255), x, self.p.pos[1] + oy - 34)

    def telas(self):
        sc = self.tela
        if self.estado in ("vitoria", "derrota"):
            self.veu(170)
            ok = self.estado == "vitoria"
            self.texto("VOCÊ ESCAPOU!" if ok else self.motivo, 56, (120, 255, 150) if ok else (255, 80, 80), 500, 200)
            if ok:
                dur = int(self.t)
                pontos = max(0, self.dinheiro * 300 + int(self.tempo) * 3 - self.alertas * 50)
                linhas = (f"DINHEIRO ROUBADO: ${self.dinheiro * VALOR_SACO:,}".replace(",", "."),
                          f"TEMPO: {dur // 60:02d}:{dur % 60:02d}",
                          f"ALERTAS: {self.alertas}",
                          f"PONTUAÇÃO: {pontos}")
                for i, linha in enumerate(linhas):
                    self.texto(linha, 28, (255, 230, 120), 500, 290 + i * 44)
            acao = "Jogar novamente (mais difícil)" if ok else "Tentar novamente"
            self.texto(f"ENTER → {acao}     ESC → Menu", 22, (230, 230, 240), 500, 520)
        elif self.estado == "menu":
            sc.blit(self.bg, (0, 0))
            self.veu(215)
            self.texto("FUGA DO BANCO", 72, (255, 215, 70), 500, 150)
            self.texto("roube os sacos, evite guardas e câmeras, escape", 18, (180, 185, 210), 500, 215)
            for i, nome in enumerate(("JOGAR", "COMO JOGAR", "SAIR")):
                sel = i == self.sel
                self.texto(f"[ {nome} ]" if sel else nome, 34, (255, 255, 255) if sel else (130, 135, 160), 500, 320 + i * 70)
            self.texto("W/S ou setas + ENTER", 16, (130, 135, 160), 500, 640)
        elif self.estado == "ajuda":
            sc.blit(self.bg, (0, 0))
            self.veu(225)
            self.texto("COMO JOGAR", 48, (255, 215, 70), 500, 120)
            linhas = ("WASD - mover", "E - pegar o saco de dinheiro (fique perto)",
                      "Fuja dos cones de visão de guardas e câmeras",
                      "A barra ALERTA enche quando você é visto",
                      "Alerta cheio = guardas por perto te perseguem",
                      "Pegue todos os sacos e vá até a SAÍDA verde (veja o minimapa)",
                      "ESC - voltar ao menu")
            for i, linha in enumerate(linhas):
                self.texto(linha, 24, (225, 225, 240), 500, 220 + i * 50)

    # ----- entrada -----
    def sair(self):
        pygame.quit()
        sys.exit()

    def eventos(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.sair()
            if e.type != pygame.KEYDOWN:
                continue
            if e.key == pygame.K_ESCAPE:
                if self.estado == "menu":
                    self.sair()
                self.estado = "menu"
            elif self.estado == "menu":
                self.sel = (self.sel + (e.key in (pygame.K_s, pygame.K_DOWN)) - (e.key in (pygame.K_w, pygame.K_UP))) % 3
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.sel == 0:
                        self.nivel = 0
                        self.novo_jogo()
                    elif self.sel == 1:
                        self.estado = "ajuda"
                    else:
                        self.sair()
            elif self.estado == "jogo" and e.key == pygame.K_e:
                self.coletar()
            elif self.estado in ("vitoria", "derrota") and e.key == pygame.K_RETURN:
                if self.estado == "vitoria":
                    self.nivel += 1
                self.novo_jogo()

    def frame(self, dt):
        """Um quadro do jogo: entrada, logica e desenho."""
        self.eventos()
        self.dt = dt
        if self.estado == "jogo":
            self.update(dt)
        if self.estado in ("jogo", "vitoria", "derrota"):
            self.desenhar_jogo()
        self.telas()

    def run(self):
        while True:
            self.frame(min(self.clock.tick(60) / 1000, 0.05))
            pygame.display.flip()


if __name__ == "__main__":
    Game().run()
