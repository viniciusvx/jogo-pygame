"""Cenario neon/futurista. O fundo estatico e cacheado; so o que anima e desenhado por frame."""
import math
import random

import pygame

from . import config as C
from .effects import glow

W, H = C.LARGURA, C.ALTURA
NIVEIS_LINHA = 8


def _lerp(a, b, k):
    return (int(a[0] + (b[0] - a[0]) * k), int(a[1] + (b[1] - a[1]) * k),
            int(a[2] + (b[2] - a[2]) * k))


class Arena:
    def __init__(self):
        rnd = random.Random(11)
        self.t = 0
        self.fundo = self._montar_fundo(rnd)
        # estrelas: x, y, fase, velocidade, brilho
        self.estrelas = [(rnd.randint(0, W - 1), rnd.randint(0, C.CHAO_Y - 190),
                          rnd.random() * 6.28, rnd.uniform(0.02, 0.07), rnd.choice((1, 1, 2)))
                         for _ in range(70)]
        # poeira subindo: [x, y, vy, deriva, fase]
        self.poeira = [[rnd.uniform(0, W), rnd.uniform(0, C.CHAO_Y), rnd.uniform(0.2, 0.7),
                        rnd.uniform(-0.15, 0.15), rnd.random() * 6.28] for _ in range(36)]
        self.brilho_linha = self._montar_linhas_chao()
        self.scan = pygame.Surface((W, 14))
        for i in range(14):
            v = int(60 * (1 - abs(i - 6.5) / 7) ** 2)
            pygame.draw.line(self.scan, (v // 2, v, v), (0, i), (W, i))
        self.ponto = glow(5, (150, 120, 255))

    # --- fundo estatico --------------------------------------------------------
    def _montar_fundo(self, rnd):
        s = pygame.Surface((W, H))
        horizonte = C.CHAO_Y
        # ceu degrade: azul-noite -> roxo escuro no horizonte
        topo, meio, base = (6, 6, 24), (22, 12, 54), (52, 20, 82)
        for y in range(horizonte):
            k = y / horizonte
            cor = _lerp(topo, meio, k / 0.6) if k < 0.6 else _lerp(meio, base, (k - 0.6) / 0.4)
            pygame.draw.line(s, cor, (0, y), (W, y))
        # sol synthwave suave, com fendas horizontais
        cx, cy, raio = W // 2, horizonte - 175, 105
        sol = pygame.Surface((raio * 2, raio * 2))
        for y in range(raio * 2):
            k = y / (raio * 2)
            cor = _lerp((140, 50, 120), (150, 90, 70), k)
            pygame.draw.line(sol, cor, (0, y), (raio * 2, y))
        mascara = pygame.Surface((raio * 2, raio * 2), pygame.SRCALPHA)
        pygame.draw.circle(mascara, (255, 255, 255, 255), (raio, raio), raio)
        for i in range(7):   # fendas mais grossas perto da base
            y = int(raio * 1.0 + i * raio * 0.145)
            pygame.draw.rect(mascara, (0, 0, 0, 0), (0, y, raio * 2, 2 + i))
        sol.blit(mascara, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        sol.set_colorkey((0, 0, 0))
        halo = glow(raio * 2, (40, 14, 46))
        s.blit(halo, (cx - raio * 2, cy - raio * 2), special_flags=pygame.BLEND_ADD)
        s.blit(sol, (cx - raio, cy - raio))
        # skyline em duas camadas
        self._skyline(s, rnd, (20, 16, 50), (12, 10, 34), 90, 230, 0.0, 38)
        self._skyline(s, rnd, (12, 10, 34), (8, 8, 26), 50, 150, 1.0, 62)
        # faixa escura atras dos lutadores (base do cenario)
        pygame.draw.rect(s, (8, 6, 22), (0, horizonte - 22, W, 22))
        # pilares neon nas laterais
        for x, cor in ((46, (255, 60, 150)), (W - 46, (60, 200, 255))):
            self._pilar(s, x, cor)
        # chao
        self._chao(s)
        try:
            return s.convert()
        except pygame.error:
            return s

    def _skyline(self, s, rnd, cor, cor_topo, hmin, hmax, camada, largura_media):
        horizonte = C.CHAO_Y
        x = -10
        while x < W:
            w = rnd.randint(largura_media - 14, largura_media + 24)
            h = rnd.randint(hmin, hmax)
            y = horizonte - h
            pygame.draw.rect(s, cor, (x, y, w, h))
            pygame.draw.rect(s, cor_topo, (x, y, w, 3))
            if rnd.random() < 0.35:   # antena
                pygame.draw.line(s, cor, (x + w // 2, y), (x + w // 2, y - rnd.randint(8, 22)), 2)
            # janelas apagadas, algumas acesas em tons frios/foscos
            for wy in range(y + 8, horizonte - 24, 9):
                for wx in range(x + 5, x + w - 5, 8):
                    r = rnd.random()
                    if r < 0.14:
                        c = rnd.choice(((50, 90, 130), (80, 60, 130), (40, 110, 120)))
                    elif r < 0.18:
                        c = (110, 80, 50)
                    else:
                        continue
                    if camada:
                        c = (c[0] * 2 // 3, c[1] * 2 // 3, c[2] * 2 // 3)
                    pygame.draw.rect(s, c, (wx, wy, 3, 4))
            x += w + rnd.randint(0, 6)

    def _pilar(self, s, x, cor):
        horizonte = C.CHAO_Y
        escuro = (cor[0] // 14, cor[1] // 14, cor[2] // 14)
        pygame.draw.rect(s, (10, 8, 26), (x - 16, 40, 32, horizonte - 40))
        pygame.draw.rect(s, escuro, (x - 16, 40, 32, horizonte - 40), 2)
        suave = (cor[0] // 3, cor[1] // 3, cor[2] // 3)
        g = glow(48, suave)
        for y in range(70, horizonte, 90):
            s.blit(g, (x - 48, y - 48), special_flags=pygame.BLEND_ADD)
        pygame.draw.line(s, suave, (x, 48), (x, horizonte - 8), 2)   # tubo central
        for y in range(70, horizonte - 20, 90):
            pygame.draw.rect(s, (cor[0] // 2, cor[1] // 2, cor[2] // 2), (x - 11, y - 2, 22, 4))
        g = glow(40, suave)
        s.blit(g, (x - 40, 40 - 40), special_flags=pygame.BLEND_ADD)

    def _chao(self, s):
        y0 = C.CHAO_Y
        pygame.draw.rect(s, (7, 5, 20), (0, y0, W, H - y0))
        for i in range(H - y0):   # leve degrade para o fundo da tela
            k = i / (H - y0)
            pygame.draw.line(s, _lerp((16, 8, 40), (4, 3, 14), k), (0, y0 + i), (W, y0 + i))
        grid = (46, 34, 110)
        fuga = (W / 2, y0 - 150)
        # verticais convergindo para o ponto de fuga
        for i in range(-16, 17):
            xb = W / 2 + i * 84
            pygame.draw.line(s, grid, (fuga[0] + (xb - fuga[0]) * (y0 - fuga[1]) / (H - fuga[1]) * 1.0, y0),
                             (xb, H), 1)
        # horizontais com espacamento crescente
        k = 0
        y = y0
        while y < H:
            y = y0 + 4 + (k ** 1.7) * 3.2
            pygame.draw.line(s, grid, (0, int(y)), (W, int(y)), 1)
            k += 1

    def _montar_linhas_chao(self):
        """Linha do chao neon em NIVEIS_LINHA intensidades (para pulsar sem alocar)."""
        niveis = []
        for n in range(NIVEIS_LINHA):
            k = 0.45 + 0.55 * n / (NIVEIS_LINHA - 1)
            sf = pygame.Surface((W, 30))
            for i in range(30):
                v = (1 - abs(i - 6) / 24) if i >= 6 else (i / 6)
                v = max(0.0, v) ** 2.4 * k
                pygame.draw.line(sf, (int(70 * v), int(40 * v), int(150 * v)), (0, i), (W, i))
            niveis.append(sf)
        return niveis

    # --- animacao --------------------------------------------------------------
    def update(self):
        self.t += 1
        for p in self.poeira:
            p[1] -= p[2]
            p[0] += p[3] + math.sin(self.t * 0.02 + p[4]) * 0.15
            if p[1] < -4:
                p[1] = C.CHAO_Y + 40
                p[0] = random.uniform(0, W)

    def draw(self, surf):
        t = self.t
        surf.blit(self.fundo, (0, 0))
        for x, y, fase, vel, tam in self.estrelas:
            v = 0.5 + 0.5 * math.sin(fase + t * vel)
            b = int(70 + 150 * v * v)
            c = (b * 3 // 4, b * 3 // 4, b)
            if tam == 1:
                surf.set_at((x, y), c)
            else:
                surf.fill(c, (x, y, 2, 2))
        for x, y, vy, dx, fase in self.poeira:
            b = 0.5 + 0.5 * math.sin(fase + t * 0.05)
            if y < C.CHAO_Y - 4:
                c = (int(40 + 40 * b), int(30 + 40 * b), int(80 + 70 * b))
                surf.fill(c, (int(x), int(y), 2, 2))
        # scanline que varre o chao e linha do chao pulsando
        ciclo = 150
        k = (t % ciclo) / ciclo
        ys = C.CHAO_Y + 2 + int(k * k * (C.ALTURA - C.CHAO_Y - 16))
        surf.blit(self.scan, (0, ys), special_flags=pygame.BLEND_ADD)
        pulso = 0.5 + 0.5 * math.sin(t * 0.06)
        nivel = int(pulso * (NIVEIS_LINHA - 1))
        surf.blit(self.brilho_linha[nivel], (0, C.CHAO_Y - 6), special_flags=pygame.BLEND_ADD)
        cor = (int(110 + 60 * pulso), int(70 + 50 * pulso), int(230 + 25 * pulso))
        pygame.draw.line(surf, cor, (0, C.CHAO_Y), (W, C.CHAO_Y), 2)
