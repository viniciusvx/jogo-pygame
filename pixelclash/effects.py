"""Efeitos visuais: brilho (glow), particulas, aneis, textos de dano, tremor e flash."""
import math
import random

import pygame

from . import config as C

_cache_glow = {}


def glow(raio, cor):
    """Surface preta com gradiente radial para usar com BLEND_ADD (cacheada)."""
    raio = max(1, int(raio))
    cor = (int(cor[0]), int(cor[1]), int(cor[2]))
    chave = (raio, cor)
    surf = _cache_glow.get(chave)
    if surf is None:
        surf = pygame.Surface((raio * 2, raio * 2))
        surf.fill((0, 0, 0))
        passos = min(raio, 24)
        for i in range(passos):
            r = raio - i * raio / passos
            k = ((i + 1) / passos) ** 2.2   # centro bem mais forte que a borda
            c = (int(cor[0] * k), int(cor[1] * k), int(cor[2] * k))
            pygame.draw.circle(surf, c, (raio, raio), max(1, int(r)))
        _cache_glow[chave] = surf
    return surf


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "cor", "vida", "vida_max", "tam", "grav", "faisca")

    def __init__(self, x, y, vx, vy, cor, vida, tam, grav=0.0, faisca=False):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.cor = cor
        self.vida = vida
        self.vida_max = max(1, vida)
        self.tam = tam
        self.grav = grav
        self.faisca = faisca


class Efeitos:
    def __init__(self, fonte):
        self.fonte = fonte
        self.particulas = []
        self.aneis = []     # [x, y, cor, r0, r1, vida, t, largura]
        self.textos = []    # [x, y, surf, t]
        self._tremor = 0.0
        self._off = (0, 0)
        self._flash_alpha = 0.0
        self._flash_surf = pygame.Surface((C.LARGURA, C.ALTURA))
        self._flash_cor = None
        self._cache_texto = {}

    # --- emissao -------------------------------------------------------------
    def particula(self, x, y, vx, vy, cor, vida, tam, grav=0.0, faisca=False):
        if len(self.particulas) >= C.MAX_PARTICULAS:
            return
        self.particulas.append(Particle(x, y, vx, vy, cor, int(vida), tam, grav, faisca))

    def burst(self, x, y, cor, n=10, vel=5, vida=(15, 30), tam=(2, 5), grav=0.2,
              faiscas=False, angulo=None, abertura=6.283):
        rnd = random.random
        for _ in range(n):
            if len(self.particulas) >= C.MAX_PARTICULAS:
                break
            if angulo is None:
                a = rnd() * 6.283
            else:
                a = angulo + (rnd() - 0.5) * abertura
            v = vel * (0.35 + 0.65 * rnd())
            self.particulas.append(Particle(
                x, y, math.cos(a) * v, math.sin(a) * v, cor,
                random.randint(int(vida[0]), int(vida[1])),
                random.uniform(tam[0], tam[1]), grav, faiscas))

    def anel(self, x, y, cor, r0=8, r1=60, vida=14, largura=3):
        self.aneis.append([x, y, cor, r0, r1, max(1, vida), 0, largura])

    def texto(self, x, y, txt, cor):
        chave = (txt, cor)
        surf = self._cache_texto.get(chave)
        if surf is None:
            base = self.fonte.render(str(txt), True, cor)
            sombra = self.fonte.render(str(txt), True, (0, 0, 0))
            surf = pygame.Surface((base.get_width() + 4, base.get_height() + 4), pygame.SRCALPHA)
            for dx, dy in ((0, 2), (4, 2), (2, 0), (2, 4), (0, 0), (4, 4), (0, 4), (4, 0)):
                surf.blit(sombra, (dx, dy))
            surf.blit(base, (2, 2))
            if len(self._cache_texto) > 64:
                self._cache_texto.clear()
            self._cache_texto[chave] = surf
        self.textos.append([x, y, surf, 0])

    def tremer(self, v):
        if v > self._tremor:
            self._tremor = float(v)

    def flashar(self, alpha, cor=(255, 255, 255)):
        if alpha > self._flash_alpha:
            self._flash_alpha = float(alpha)
            if cor != self._flash_cor:
                self._flash_cor = cor
                self._flash_surf.fill(cor)

    # --- atualizacao ---------------------------------------------------------
    def update_tremor(self):
        if self._tremor > 0.3:
            m = int(self._tremor + 0.5)
            self._off = (random.randint(-m, m), random.randint(-m, m))
            self._tremor *= 0.82
        else:
            self._tremor = 0.0
            self._off = (0, 0)
        if self._flash_alpha > 0:
            self._flash_alpha = max(0.0, self._flash_alpha - 14)

    @property
    def offset(self):
        return self._off

    def update(self):
        self.update_tremor()
        vivas = []
        for p in self.particulas:
            p.vida -= 1
            if p.vida <= 0:
                continue
            p.vy += p.grav
            p.vx *= 0.985
            p.x += p.vx
            p.y += p.vy
            vivas.append(p)
        self.particulas = vivas
        for a in self.aneis:
            a[6] += 1
        self.aneis = [a for a in self.aneis if a[6] < a[5]]
        for t in self.textos:
            t[3] += 1
            t[1] -= 1.1 if t[3] < 20 else 0.5
        self.textos = [t for t in self.textos if t[3] < 45]

    # --- desenho -------------------------------------------------------------
    def draw(self, surf):
        for p in self.particulas:
            k = p.vida / p.vida_max
            cor = p.cor
            if p.faisca:
                px = p.x - p.vx * 1.6
                py = p.y - p.vy * 1.6
                c = (int(cor[0] * (0.4 + 0.6 * k)), int(cor[1] * (0.4 + 0.6 * k)),
                     int(cor[2] * (0.4 + 0.6 * k)))
                pygame.draw.line(surf, c, (px, py), (p.x, p.y), max(1, int(p.tam * k * 0.7)))
            else:
                r = p.tam * (0.35 + 0.65 * k)
                if r >= 3:
                    g = glow(int(r * 2.6), cor)
                    surf.blit(g, (p.x - g.get_width() // 2, p.y - g.get_height() // 2),
                              special_flags=pygame.BLEND_ADD)
                pygame.draw.circle(surf, cor, (int(p.x), int(p.y)), max(1, int(r)))
        for x, y, cor, r0, r1, vida, t, larg in self.aneis:
            k = t / vida
            r = r0 + (r1 - r0) * (1 - (1 - k) ** 2)
            w = max(1, int(larg * (1 - k)))
            f = 1 - k * 0.6
            c = (int(cor[0] * f), int(cor[1] * f), int(cor[2] * f))
            pygame.draw.circle(surf, c, (int(x), int(y)), int(r), w)
        for x, y, s, t in self.textos:
            s.set_alpha(255 if t < 28 else int(255 * (45 - t) / 17))
            surf.blit(s, (x - s.get_width() // 2, y - s.get_height() // 2))

    def draw_flash(self, surf):
        if self._flash_alpha > 0:
            self._flash_surf.set_alpha(int(self._flash_alpha))
            surf.blit(self._flash_surf, (0, 0))

    def limpar(self):
        self.particulas.clear()
        self.aneis.clear()
        self.textos.clear()
        self._tremor = 0.0
        self._off = (0, 0)
        self._flash_alpha = 0.0
