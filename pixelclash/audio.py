"""Sons sintetizados (sem arquivos). Se existir assets/sons/<nome>.wav|ogg, ele tem prioridade."""
import math
import os
import random
from array import array

import pygame

from . import config as C

NOMES = ("soco", "golpe_forte", "bloqueio", "whoosh", "especial_carga", "especial_disparo",
         "impacto_especial", "pulo", "pouso", "ko", "selecionar", "confirmar", "round",
         "fight", "vitoria", "erro")

PASTA_SONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "assets", "sons")
TAU = 2 * math.pi


class _Sintese:
    """Pequeno sintetizador: cada metodo devolve uma lista de floats em [-1, 1]."""

    def __init__(self, freq):
        self.freq = freq

    def n(self, dur):
        return max(1, int(self.freq * dur))

    def tom(self, f0, f1, dur, onda="sin", vol=1.0, decaimento=3.0, vibrato=0.0):
        n = self.n(dur)
        fase = 0.0
        out = [0.0] * n
        for i in range(n):
            k = i / n
            f = f0 + (f1 - f0) * k
            if vibrato:
                f *= 1 + 0.04 * math.sin(TAU * vibrato * i / self.freq)
            fase += f / self.freq
            fr = fase % 1.0
            if onda == "sin":
                s = math.sin(TAU * fr)
            elif onda == "quad":
                s = 1.0 if fr < 0.5 else -1.0
            elif onda == "serra":
                s = 2 * fr - 1
            else:  # triangulo
                s = 4 * abs(fr - 0.5) - 1
            ataque = min(1.0, i / 40)
            out[i] = s * vol * ataque * math.exp(-decaimento * k)
        return out

    def ruido(self, dur, vol=1.0, decaimento=4.0, filtro=1.0, filtro_fim=None, subida=0.0):
        """Ruido branco com passa-baixa de um polo (filtro 1.0 = sem filtro)."""
        n = self.n(dur)
        y = 0.0
        out = [0.0] * n
        if filtro_fim is None:
            filtro_fim = filtro
        for i in range(n):
            k = i / n
            a = filtro + (filtro_fim - filtro) * k
            y += a * (random.uniform(-1, 1) - y)
            if subida > 0:   # sobe e desce (whoosh)
                env = math.sin(math.pi * min(1.0, k / (1 - subida * 0.5)) ** (1 + subida)) if k < 1 else 0
            else:
                env = math.exp(-decaimento * k)
            out[i] = y * vol * env * min(1.0, i / 20)
        return out

    def misturar(self, *camadas):
        n = max(len(c[0] if isinstance(c, tuple) else c) for c in camadas)
        out = [0.0] * n
        for c in camadas:
            atraso = 0
            if isinstance(c, tuple):
                c, atraso = c[0], int(c[1] * self.freq)
            n = len(c)
            if atraso + n > len(out):
                out.extend([0.0] * (atraso + n - len(out)))
            for i, v in enumerate(c):
                out[atraso + i] += v
        return out


def _receitas(s):
    t, r, m = s.tom, s.ruido, s.misturar
    return {
        "soco": lambda: m(t(220, 80, 0.10, vol=0.7, decaimento=5), r(0.07, 0.6, 6, 0.5)),
        "golpe_forte": lambda: m(t(150, 40, 0.28, vol=0.9, decaimento=4),
                                 r(0.18, 0.7, 5, 0.45), t(90, 50, 0.2, "triangulo", 0.5)),
        "bloqueio": lambda: m(t(520, 380, 0.12, "quad", 0.35, 6), t(1040, 760, 0.08, "sin", 0.3, 8),
                              r(0.05, 0.4, 8, 0.8)),
        "whoosh": lambda: r(0.22, 0.55, 0, 0.12, 0.7, subida=1.0),
        "especial_carga": lambda: m(t(180, 900, 0.30, "serra", 0.28, 0.4, vibrato=14),
                                    t(360, 1500, 0.30, "sin", 0.22, 0.5)),
        "especial_disparo": lambda: m(t(900, 120, 0.38, "serra", 0.4, 3), r(0.30, 0.5, 3, 0.7, 0.2),
                                      t(60, 40, 0.3, "sin", 0.6, 3)),
        "impacto_especial": lambda: m(t(100, 28, 0.55, "sin", 1.0, 3.5), r(0.45, 0.8, 3.5, 0.35),
                                      t(220, 60, 0.25, "quad", 0.25, 6)),
        "pulo": lambda: t(260, 560, 0.13, "sin", 0.55, 3),
        "pouso": lambda: m(r(0.09, 0.6, 6, 0.3), t(100, 55, 0.12, "sin", 0.7, 5)),
        "ko": lambda: m(t(420, 55, 0.9, "serra", 0.4, 2.5), r(0.6, 0.6, 3, 0.4),
                        t(70, 35, 0.7, "sin", 0.8, 2.5)),
        "selecionar": lambda: t(880, 880, 0.05, "quad", 0.22, 4),
        "confirmar": lambda: m(t(660, 660, 0.09, "quad", 0.25, 3), (t(990, 990, 0.16, "quad", 0.25, 4), 0.07)),
        "round": lambda: m(t(330, 330, 0.28, "triangulo", 0.55, 2), t(660, 660, 0.28, "sin", 0.25, 2)),
        "fight": lambda: m(t(220, 330, 0.45, "serra", 0.35, 2.2), t(110, 165, 0.45, "quad", 0.2, 2.2),
                           r(0.12, 0.35, 6, 0.6)),
        "vitoria": lambda: m(*[(t(f, f, 0.22, "quad", 0.22, 3), i * 0.12)
                               for i, f in enumerate((523, 659, 784, 1047))],
                             (t(1047, 1047, 0.5, "triangulo", 0.35, 2.5), 0.48)),
        "erro": lambda: m(t(150, 120, 0.2, "quad", 0.3, 3), t(110, 90, 0.2, "quad", 0.25, 3)),
    }


class Audio:
    def __init__(self):
        self.sons = {}
        self.ativo = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 1, 512)
            info = pygame.mixer.get_init()
        except pygame.error:
            info = None
        if not info:
            return
        freq, formato, canais = info
        try:
            pygame.mixer.set_num_channels(16)
        except pygame.error:
            pass
        self.ativo = True
        sintese = _Sintese(freq)
        receitas = _receitas(sintese)
        for nome in NOMES:
            som = self._carregar_arquivo(nome)
            if som is None and abs(formato) == 16:
                try:
                    som = self._sintetizar(receitas[nome](), canais, formato < 0)
                except (pygame.error, ValueError, TypeError):
                    som = None
            if som is not None:
                self.sons[nome] = som

    @staticmethod
    def _carregar_arquivo(nome):
        for ext in ("wav", "ogg"):
            caminho = os.path.join(PASTA_SONS, nome + "." + ext)
            if os.path.isfile(caminho):
                try:
                    return pygame.mixer.Sound(caminho)
                except pygame.error:
                    pass
        return None

    @staticmethod
    def _sintetizar(amostras, canais, assinado):
        pico = max(1.0, max(abs(v) for v in amostras))
        esc = 0.8 * 32767 / pico if pico > 1.0 else 0.8 * 32767
        dados = array("h" if assinado else "H")
        deslocar = 0 if assinado else 32768
        for v in amostras:
            q = int(max(-32767, min(32767, v * esc))) + deslocar
            for _ in range(canais):
                dados.append(q)
        return pygame.mixer.Sound(buffer=dados.tobytes())

    def tocar(self, nome):
        som = self.sons.get(nome)
        if som is None:
            return
        try:
            som.play()
        except pygame.error:
            pass
