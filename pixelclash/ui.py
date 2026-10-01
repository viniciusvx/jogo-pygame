"""Interface: fontes, textos, menus neon, HUD e textos centrais."""
import math

import pygame

from . import config as C

CIANO = (60, 235, 255)
MAGENTA = (255, 60, 200)
AMARELO = (255, 220, 70)
BRANCO = (255, 255, 255)
CINZA = (150, 160, 185)
FUNDO_BOTAO = (12, 14, 34)

_cache_texto = {}
_cache_brilho = {}
_cache_botao = {}


class Fontes:
    def __init__(self):
        nomes = "impact,arialblack,verdana,arial"
        self.mini = pygame.font.SysFont(nomes, 14)
        self.pequena = pygame.font.SysFont(nomes, 18)
        self.media = pygame.font.SysFont(nomes, 28)
        self.grande = pygame.font.SysFont(nomes, 48)
        self.titulo = pygame.font.SysFont(nomes, 92)


def texto(fonte, txt, cor, contorno=None):
    """Surface de texto com contorno opcional (cacheada)."""
    chave = (id(fonte), txt, cor, contorno)
    surf = _cache_texto.get(chave)
    if surf is None:
        if len(_cache_texto) > 800:
            _cache_texto.clear()
        base = fonte.render(txt, True, cor)
        if contorno:
            esp = 2
            surf = pygame.Surface((base.get_width() + esp * 2, base.get_height() + esp * 2), pygame.SRCALPHA)
            borda = fonte.render(txt, True, contorno)
            for dx in range(-esp, esp + 1):
                for dy in range(-esp, esp + 1):
                    if dx or dy:
                        surf.blit(borda, (esp + dx, esp + dy))
            surf.blit(base, (esp, esp))
        else:
            surf = base
        _cache_texto[chave] = surf
    return surf


def desenhar_texto(surf, fonte, txt, cor, pos, ancora="center", contorno=(0, 0, 0)):
    img = texto(fonte, txt, cor, contorno)
    r = img.get_rect()
    setattr(r, ancora, pos)
    surf.blit(img, r)
    return r


def brilho_texto(fonte, txt, cor):
    """Halo suave do texto (para BLEND_ADD), cacheado."""
    chave = (id(fonte), txt, cor)
    img = _cache_brilho.get(chave)
    if img is None:
        base = fonte.render(txt, True, cor)
        w, h = base.get_size()
        grande = pygame.Surface((w + 40, h + 40))
        grande.blit(base, (20, 20))
        pequeno = pygame.transform.smoothscale(grande, (max(1, grande.get_width() // 5), max(1, grande.get_height() // 5)))
        img = pygame.transform.smoothscale(pequeno, grande.get_size())
        img.blit(img.copy(), (0, 0), special_flags=pygame.BLEND_ADD)
        _cache_brilho[chave] = img
    return img


def _texto_aditivo(fonte, txt, cor):
    """Texto sobre fundo preto opaco, para BLEND_ADD (alpha por pixel e ignorado no ADD)."""
    chave = ("add", id(fonte), txt, cor)
    img = _cache_texto.get(chave)
    if img is None:
        base = fonte.render(txt, True, cor)
        img = pygame.Surface(base.get_size())
        img.blit(base, (0, 0))
        _cache_texto[chave] = img
    return img


def desenhar_neon(surf, fonte, txt, cor, pos, t=0, ancora="center"):
    """Texto neon: halo pulsante + miolo claro."""
    halo = brilho_texto(fonte, txt, cor)
    r = halo.get_rect()
    setattr(r, ancora, pos)
    surf.blit(halo, r, special_flags=pygame.BLEND_ADD)
    miolo = tuple(min(255, c + 110) for c in cor)
    img = texto(fonte, txt, miolo, None)
    r2 = img.get_rect(center=r.center)
    surf.blit(img, r2)
    return r2


def desenhar_titulo(surf, fontes, cx, y, t):
    """Titulo PIXEL CLASH com glitch ocasional (canais deslocados)."""
    txt = C.TITULO
    f = fontes.titulo
    glitch = (t % 140) < 7 or (t % 331) < 4
    desl = 0
    if glitch:
        desl = ((t * 7919) % 17) - 8
    img_c = _texto_aditivo(f, txt, CIANO)
    img_m = _texto_aditivo(f, txt, MAGENTA)
    pulso = 0.5 + 0.5 * math.sin(t * 0.06)
    # halo
    halo = brilho_texto(f, txt, (int(120 + 60 * pulso), 40, int(200 + 40 * pulso)))
    surf.blit(halo, halo.get_rect(center=(cx, y)), special_flags=pygame.BLEND_ADD)
    for img, dx, dy in ((img_m, 4 + desl, 3), (img_c, -4 - desl, -2)):
        r = img.get_rect(center=(cx + dx, y + dy))
        surf.blit(img, r, special_flags=pygame.BLEND_ADD)
    miolo = texto(f, txt, (255, 245, 255), (40, 10, 70))
    r = miolo.get_rect(center=(cx, y))
    if glitch:
        # fatias horizontais deslocadas
        fatia = 10
        for i, yy in enumerate(range(0, r.h, fatia)):
            off = (((i * 37 + t) % 5) - 2) * 5
            surf.blit(miolo, (r.x + off, r.y + yy), (0, yy, r.w, fatia))
    else:
        surf.blit(miolo, r)


class Menu:
    LARGURA = 320
    ALTURA = 54
    ESPACO = 16

    def __init__(self, itens):
        self.itens = list(itens)
        self.sel = 0
        self.rects = []

    def mover(self, d):
        self.sel = (self.sel + d) % len(self.itens)

    def item_em(self, pos):
        for i, r in enumerate(self.rects):
            if r.collidepoint(pos):
                return i
        return None

    def _botao(self, w, h, selecionado):
        chave = (w, h, selecionado)
        s = _cache_botao.get(chave)
        if s is None:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            fundo = (30, 40, 90, 230) if selecionado else (*FUNDO_BOTAO, 190)
            pygame.draw.rect(s, fundo, (0, 0, w, h), border_radius=10)
            _cache_botao[chave] = s
        return s

    def draw(self, surf, cx, y, t, fontes):
        self.rects = []
        for i, nome in enumerate(self.itens):
            r = pygame.Rect(0, 0, self.LARGURA, self.ALTURA)
            r.midtop = (cx, y + i * (self.ALTURA + self.ESPACO))
            sel = i == self.sel
            if sel:
                r.inflate_ip(int(8 + 6 * math.sin(t * 0.15)), 4)
            self.rects.append(r)
            surf.blit(self._botao(r.w, r.h, sel), r)
            cor = CIANO if sel else (90, 110, 170)
            pygame.draw.rect(surf, cor, r, 3 if sel else 2, border_radius=10)
            if sel:
                halo = pygame.Surface(r.size, pygame.SRCALPHA)
                pygame.draw.rect(halo, (*CIANO, 70), halo.get_rect(), 8, border_radius=12)
                surf.blit(halo, r)
                desenhar_texto(surf, fontes.media, ">", AMARELO, (r.x + 22, r.centery))
                desenhar_texto(surf, fontes.media, "<", AMARELO, (r.right - 22, r.centery))
            desenhar_texto(surf, fontes.media, nome, BRANCO if sel else CINZA, r.center)
        # rects de clique usam o tamanho base (sem pulso)
        return self.rects


# --- HUD ---------------------------------------------------------------------
_BARRA_W = 384
_BARRA_H = 26
_MARGEM = 26
_BARRA_Y = 30


def _cor_vida(frac):
    if frac > 0.5:
        return (70, 230, 110)
    if frac > 0.25:
        return (250, 205, 60)
    return (240, 60, 60)


def _barra_vida(surf, f, lado, fontes, t):
    """lado 0 = esquerda (esvazia para fora), 1 = direita."""
    cx = C.LARGURA // 2
    if lado == 0:
        r = pygame.Rect(_MARGEM, _BARRA_Y, _BARRA_W, _BARRA_H)
    else:
        r = pygame.Rect(C.LARGURA - _MARGEM - _BARRA_W, _BARRA_Y, _BARRA_W, _BARRA_H)
    pygame.draw.rect(surf, (10, 10, 24), r.inflate(6, 6), border_radius=6)
    frac = max(0.0, min(1.0, f.hp / C.VIDA_MAXIMA))
    frac_v = max(frac, min(1.0, f.hp_visual / C.VIDA_MAXIMA))

    def trecho(fr):
        w = int(r.w * fr)
        if lado == 0:
            return pygame.Rect(r.x, r.y, w, r.h)
        return pygame.Rect(r.right - w, r.y, w, r.h)

    pygame.draw.rect(surf, (30, 32, 52), r, border_radius=4)
    if frac_v > frac:
        pygame.draw.rect(surf, (255, 245, 210), trecho(frac_v), border_radius=4)
    if frac > 0:
        cor = _cor_vida(frac)
        rr = trecho(frac)
        pygame.draw.rect(surf, cor, rr, border_radius=4)
        brilho = pygame.Rect(rr.x, rr.y, rr.w, rr.h // 3)
        pygame.draw.rect(surf, tuple(min(255, c + 60) for c in cor), brilho, border_radius=4)
    cor_borda = f.perfil["cor"]
    pygame.draw.rect(surf, cor_borda, r.inflate(6, 6), 3, border_radius=6)

    # nome e etiqueta do jogador
    rotulo = f"P{f.jogador}  {f.nome.upper()}"
    if lado == 0:
        desenhar_texto(surf, fontes.pequena, rotulo, BRANCO, (r.x, r.y - 6), "bottomleft")
    else:
        desenhar_texto(surf, fontes.pequena, rotulo, BRANCO, (r.right, r.y - 6), "bottomright")

    # energia
    er = pygame.Rect(r.x, r.bottom + 10, int(_BARRA_W * 0.66), 10)
    if lado == 1:
        er.right = r.right
    pygame.draw.rect(surf, (10, 10, 24), er.inflate(4, 4), border_radius=4)
    fe = max(0.0, min(1.0, f.energia / C.ENERGIA_MAXIMA))
    custo = C.ATAQUES["especial"]["custo"]
    pronto = f.energia >= custo
    if fe > 0:
        w = int(er.w * fe)
        rr = pygame.Rect(er.x, er.y, w, er.h)
        if lado == 1:
            rr.right = er.right
        cor = (255, 230, 90) if pronto else (60, 170, 255)
        pygame.draw.rect(surf, cor, rr, border_radius=3)
    marca = int(er.w * custo / C.ENERGIA_MAXIMA)
    mx = er.x + marca if lado == 0 else er.right - marca
    pygame.draw.line(surf, BRANCO, (mx, er.y - 2), (mx, er.bottom + 1), 2)
    pygame.draw.rect(surf, (120, 140, 200), er.inflate(4, 4), 2, border_radius=4)
    if pronto and f.cooldown_especial == 0:
        k = 0.6 + 0.4 * math.sin(t * 0.3)
        cor = tuple(int(c * k) for c in AMARELO)
        pos = (er.right + 10, er.centery) if lado == 0 else (er.x - 10, er.centery)
        desenhar_texto(surf, fontes.mini, "ESPECIAL!", cor, pos, "midleft" if lado == 0 else "midright")


def _pips(surf, vit, lado, y):
    cx = C.LARGURA // 2
    n = C.ROUNDS_PARA_VENCER
    for i in range(n):
        dx = 50 + i * 22
        x = cx - dx if lado == 0 else cx + dx
        cheio = i < vit
        pygame.draw.circle(surf, (10, 10, 24), (x, y), 9)
        if cheio:
            pygame.draw.circle(surf, AMARELO, (x, y), 7)
        else:
            pygame.draw.circle(surf, (110, 120, 160), (x, y), 7, 2)


def desenhar_hud(surf, match, fontes, t):
    cx = C.LARGURA // 2
    _barra_vida(surf, match.f1, 0, fontes, t)
    _barra_vida(surf, match.f2, 1, fontes, t)

    # timer
    seg = max(0, math.ceil(match.timer / C.FPS))
    urgente = seg <= 10 and match.fase == "fight"
    caixa = pygame.Rect(0, 0, 76, 56)
    caixa.center = (cx, _BARRA_Y + 14)
    pygame.draw.rect(surf, (10, 10, 24), caixa, border_radius=10)
    pygame.draw.rect(surf, (255, 90, 90) if urgente else (120, 140, 200), caixa, 3, border_radius=10)
    fonte = fontes.grande
    cor = BRANCO
    if urgente and (t // 8) % 2 == 0:
        cor = (255, 110, 110)
    desenhar_texto(surf, fonte, str(seg), cor, caixa.center)

    # rounds
    desenhar_texto(surf, fontes.mini, "P1", CINZA, (cx - 100, _BARRA_Y + 52))
    desenhar_texto(surf, fontes.mini, "P2", CINZA, (cx + 100, _BARRA_Y + 52))
    _pips(surf, match.vitorias[0], 0, _BARRA_Y + 52)
    _pips(surf, match.vitorias[1], 1, _BARRA_Y + 52)
    desenhar_texto(surf, fontes.mini, f"ROUND {match.round}", CINZA, (cx, _BARRA_Y + 52))

    # combo
    info = match.combo_info
    if info and info.get("n", 0) >= 2:
        lado = 0 if info.get("lado") == 1 else 1
        n = info["n"]
        k = min(1.0, info.get("t", 30) / 20)
        cor = tuple(int(c * (0.4 + 0.6 * k)) for c in AMARELO)
        pos = (_MARGEM + 4, 118) if lado == 0 else (C.LARGURA - _MARGEM - 4, 118)
        desenhar_texto(surf, fontes.media, f"{n} HITS!", cor, pos, "topleft" if lado == 0 else "topright")


_zoom = {"msg": None, "t": 0}


def desenhar_textos_centrais(surf, match, fontes):
    """ROUND N / FIGHT! / K.O.! / TEMPO! / EMPATE com zoom de entrada."""
    msg = None
    cor = BRANCO
    if match.fase in ("intro", "fight"):
        msg = match.msg_round or None
        if match.fase == "fight" and match.fase_t > 50:
            msg = None
        cor = AMARELO if msg and "FIGHT" in msg.upper() else BRANCO
    elif match.fase == "ko":
        msg = match.msg_round or None
        if not msg:
            if match.f1.state == "defeated" or match.f2.state == "defeated":
                msg = "K.O.!"
            elif match.vencedor_round == 0:
                msg = "EMPATE"
            else:
                msg = "TEMPO!"
        cor = (255, 80, 80) if "K.O" in msg.upper() else AMARELO
    if msg != _zoom["msg"]:
        _zoom["msg"] = msg
        _zoom["t"] = 0
    else:
        _zoom["t"] += 1
    if not msg:
        return
    k = min(1.0, _zoom["t"] / 12)
    escala = 2.4 - 1.4 * (1 - (1 - k) ** 3)
    img = texto(fontes.titulo, msg, cor, (20, 10, 40))
    w = max(1, int(img.get_width() * escala))
    h = max(1, int(img.get_height() * escala))
    img = pygame.transform.smoothscale(img, (w, h)) if escala != 1 else img
    img.set_alpha(int(255 * min(1.0, 0.3 + k)))
    surf.blit(img, img.get_rect(center=(C.LARGURA // 2, C.ALTURA // 2 - 40)))
