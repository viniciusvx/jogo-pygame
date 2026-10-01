"""Lutadores, ataques e projeteis (tudo em frames, 60 FPS fixo)."""
import math
import random

import pygame

from . import config as C

try:
    from .effects import glow
except ImportError:  # effects.py ainda nao existe: gradiente simples local
    _cache_glow = {}

    def glow(raio, cor):
        raio = max(1, int(raio))
        chave = (raio, tuple(cor))
        surf = _cache_glow.get(chave)
        if surf is None:
            surf = pygame.Surface((raio * 2, raio * 2))
            passos = min(raio, 24)
            for i in range(passos):
                k = ((i + 1) / passos) ** 2.2
                c = tuple(int(v * k) for v in cor)
                pygame.draw.circle(surf, c, (raio, raio), max(1, int(raio - i * raio / passos)))
            _cache_glow[chave] = surf
        return surf


# ------------------------------------------------------------------- utilitarios
CONTORNO = (16, 10, 24)
BRANCO = (255, 255, 255)
COR_JOGADOR = {1: (255, 225, 80), 2: (90, 240, 150)}
ACOES_ATAQUE = ("especial", "forte", "basico")     # prioridade do buffer
ESTADOS_LIVRES = ("idle", "walking", "jumping")
ATRITO_CHAO = 0.85
ATRITO_AR = 0.99
TAM_HITFLASH = 10
TAM_BLOCKFLASH = 10
LIMITE_RASTRO = 7


class _Dic(dict):
    """dict com acesso por atributo (spec.alcance == spec["alcance"])."""
    __slots__ = ()

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k) from None


def _dic(d):
    return d if isinstance(d, _Dic) else _Dic(d)


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp2(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def _mix(c, alvo, k):
    return (int(c[0] + (alvo[0] - c[0]) * k), int(c[1] + (alvo[1] - c[1]) * k),
            int(c[2] + (alvo[2] - c[2]) * k))


def _osso(a, b, dobra):
    """Ponto do cotovelo/joelho entre a e b, deslocado perpendicularmente."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if d < 1e-3:
        return mx, my
    return mx - dy / d * dobra, my + dx / d * dobra


def _blit_glow(surf, raio, cor, pos):
    g = glow(max(4, int(raio) // 4 * 4), cor)
    surf.blit(g, (int(pos[0]) - g.get_width() // 2, int(pos[1]) - g.get_height() // 2),
              special_flags=pygame.BLEND_ADD)


_cache_sombra = {}
_cache_bolha = {}


def _sombra(largura):
    largura = max(10, int(largura) // 6 * 6)
    s = _cache_sombra.get(largura)
    if s is None:
        s = pygame.Surface((largura, 14), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 55), s.get_rect())
        pygame.draw.ellipse(s, (0, 0, 0, 70), s.get_rect().inflate(-largura // 3, -5))
        _cache_sombra[largura] = s
    return s


def _bolha(cor):
    s = _cache_bolha.get(cor)
    if s is None:
        s = pygame.Surface((96, 142), pygame.SRCALPHA)
        r = s.get_rect()
        pygame.draw.ellipse(s, (*cor, 38), r)
        pygame.draw.ellipse(s, (*cor, 45), r.inflate(-14, -14))
        pygame.draw.ellipse(s, (*cor, 190), r, 3)
        pygame.draw.arc(s, (255, 255, 255, 200), r.inflate(-12, -12), 1.9, 2.8, 3)
        _cache_bolha[cor] = s
    return s


# ------------------------------------------------------------------------ Attack
class Attack:
    def __init__(self, nome, spec):
        self.nome = nome
        self.spec = _dic(spec)
        self.frame = 0
        self.acertou = False
        self.total = self.spec.startup + self.spec.ativo + self.spec.recuperacao

    @property
    def ativo(self):
        return self.spec.startup <= self.frame < self.spec.startup + self.spec.ativo

    @property
    def fase(self):
        if self.frame < self.spec.startup:
            return "startup"
        if self.frame < self.spec.startup + self.spec.ativo:
            return "ativo"
        if self.frame < self.total:
            return "recuperacao"
        return "fim"

    @property
    def terminou(self):
        return self.frame >= self.total

    def update(self):
        self.frame += 1

    def hitbox(self, fighter):
        s = self.spec
        if s.get("projetil") or not self.ativo:
            return None
        alcance = s.alcance + fighter.perfil.alcance_bonus
        r = fighter.rect
        esq = r.right if fighter.facing > 0 else r.left - alcance
        return pygame.Rect(esq, round(fighter.y) - s.base - s.altura, alcance, s.altura)


# -------------------------------------------------------------------- Projectile
class Projectile:
    def __init__(self, dono, x, y, direcao, spec):
        self.dono = dono
        self.spec = _dic(spec)
        self.x = float(x)
        self.y = float(y)
        self.direcao = direcao
        self.raio = dono.perfil.proj_raio
        self.vx = direcao * dono.perfil.proj_velocidade
        self.rect = pygame.Rect(0, 0, self.raio * 2, self.raio * 2)
        self.rect.center = (round(self.x), round(self.y))
        self.vivo = True
        self.t = 0
        self.tipo = dono.personagem

    def update(self, efeitos):
        self.t += 1
        self.x += self.vx
        self.rect.center = (round(self.x), round(self.y))
        if self.x < -80 or self.x > C.LARGURA + 80:
            self.vivo = False
            return
        p = self.dono.perfil
        if self.t % 2 == 0:
            r = self.raio
            py = self.y + random.uniform(-r * 0.5, r * 0.5)
            if self.tipo == "blaze":
                efeitos.particula(self.x - self.direcao * r * 0.8, py,
                                  -self.direcao * random.uniform(0.5, 1.5), random.uniform(-1.2, 0),
                                  random.choice((p.cor, p.cor_clara, (255, 150, 40))),
                                  random.randint(12, 22), random.uniform(r * 0.15, r * 0.3), -0.04)
            else:
                efeitos.particula(self.x - self.direcao * r * 0.6, py,
                                  -self.direcao * random.uniform(0.2, 0.8), random.uniform(-0.3, 0.6),
                                  random.choice((p.cor_clara, BRANCO, p.cor)),
                                  random.randint(16, 28), random.uniform(1.5, 3.2), 0.03)

    def draw(self, surf):
        p = self.dono.perfil
        r = self.raio
        cx, cy = int(self.x), int(self.y)
        d = self.direcao
        t = self.t
        if self.tipo == "blaze":
            _blit_glow(surf, r * 2.8, (150, 60, 20), (cx, cy))
            for i in range(5, 0, -1):    # cauda de chama
                k = i / 5
                rr = r * (1 - k * 0.65) * (1 + 0.12 * math.sin(t * 0.7 + i))
                ox = cx - d * i * r * 0.62
                oy = cy + math.sin(t * 0.5 + i * 1.3) * r * 0.22 * k
                pygame.draw.circle(surf, p.cor if i % 2 else _mix(p.cor, p.cor_clara, 0.5),
                                   (int(ox), int(oy)), max(2, int(rr)))
            pygame.draw.circle(surf, CONTORNO, (cx, cy), r + 2, 3)
            pygame.draw.circle(surf, p.cor, (cx, cy), r)
            pygame.draw.circle(surf, (255, 150, 40), (cx, cy), int(r * 0.75))
            pygame.draw.circle(surf, p.cor_clara, (cx, cy), int(r * 0.5 + math.sin(t * 0.6) * 2))
            pygame.draw.circle(surf, BRANCO, (cx, cy), int(r * 0.24))
        else:
            _blit_glow(surf, r * 2.6, (40, 110, 170), (cx, cy))
            ang = t * 0.12

            def diamante(k, a):
                pts = []
                for dx, dy in ((1.45, 0), (0, 0.78), (-1.2, 0), (0, -0.78)):
                    x0, y0 = dx * r * k, dy * r * k
                    pts.append((cx + x0 * math.cos(a) - y0 * math.sin(a),
                                cy + x0 * math.sin(a) + y0 * math.cos(a)))
                return pts

            a0 = 0.0 if d > 0 else math.pi
            for i in range(3):    # estilhacos orbitando
                a = ang * 1.6 + i * 2.094
                sx, sy = cx + math.cos(a) * r * 1.05, cy + math.sin(a) * r * 0.8
                pygame.draw.polygon(surf, p.cor_clara, [(sx + 6 * math.cos(a), sy + 6 * math.sin(a)),
                                                        (sx - 3 * math.sin(a), sy + 3 * math.cos(a)),
                                                        (sx - 5 * math.cos(a), sy - 5 * math.sin(a)),
                                                        (sx + 3 * math.sin(a), sy - 3 * math.cos(a))])
            pygame.draw.polygon(surf, CONTORNO, diamante(1.12, a0 + math.sin(t * 0.15) * 0.25), 4)
            pygame.draw.polygon(surf, p.cor_clara, diamante(1.0, a0 + math.sin(t * 0.15) * 0.25))
            pygame.draw.polygon(surf, p.cor, diamante(0.62, a0 + math.sin(t * 0.15) * 0.25))
            pygame.draw.polygon(surf, BRANCO, diamante(0.28, a0 + math.sin(t * 0.15) * 0.25))


# ----------------------------------------------------------------------- Fighter
class Fighter:
    def __init__(self, jogador, personagem, x, facing, controles):
        self.jogador = jogador
        self.personagem = personagem
        self.perfil = _Dic(C.PERSONAGENS[personagem])
        self.nome = self.perfil.nome
        self.controles = controles
        self.x_inicial = x
        self.facing_inicial = facing
        self.eventos = []
        self.novos_projeteis = []
        self.rect = pygame.Rect(0, 0, C.LARGURA_LUTADOR, C.ALTURA_LUTADOR)
        self.t = 0
        self.reset()

    def reset(self):
        self.x = float(self.x_inicial)
        self.y = float(C.CHAO_Y)
        self.vx = 0.0
        self.vy = 0.0
        self.facing = self.facing_inicial
        self.hp = C.VIDA_MAXIMA
        self.hp_visual = float(C.VIDA_MAXIMA)
        self.energia = float(C.ENERGIA_INICIAL)
        self.state = "idle"
        self.attack = None
        self.cooldown = 0
        self.cooldown_especial = 0
        self.invuln = 0
        self.flash_hit = 0
        self.flash_block = 0
        self.combo = 0
        self.hitstun = 0
        self.no_chao = True
        self.ultimo_dano = 0
        self.buffer = {}
        self.rastro = []
        self.eventos.clear()
        self.novos_projeteis.clear()
        self.rect.midbottom = (round(self.x), round(self.y))

    # ------------------------------------------------------------------ logica
    def pode_ser_atingido(self):
        return self.state not in ("defeated", "victory") and self.invuln <= 0

    def ponto_mao_especial(self):
        return (self.x + self.facing * 32, self.y - 80)

    def receber_golpe(self, spec, x_atacante):
        if not self.pode_ser_atingido():
            return None
        spec = _dic(spec)
        longe = 1 if self.x > x_atacante else -1 if self.x < x_atacante else -self.facing
        na_frente = (x_atacante - self.x) * self.facing >= 0
        self.buffer.clear()
        if self.state == "defending" and na_frente:
            dano = max(1, round(spec.dano * spec.bloqueio))
            self.hp = max(0, self.hp - dano)
            self.ultimo_dano = dano
            self.flash_block = TAM_BLOCKFLASH
            self.vx = longe * spec.knockback * 0.5
            if self.hp <= 0:
                self._derrotar(spec, longe)
            return "block"
        self.attack = None
        self.hitstun = max(8, spec.hitstun - C.REDUCAO_COMBO * self.combo)
        self.combo += 1
        self.ultimo_dano = spec.dano
        self.hp = max(0, self.hp - spec.dano)
        self.flash_hit = TAM_HITFLASH
        self.vx = longe * spec.knockback
        if spec.lancamento > 0:
            self.vy = -spec.lancamento
            self.no_chao = False
        self.state = "hurt"
        if self.hp <= 0:
            self._derrotar(spec, longe)
        return "hit"

    def _derrotar(self, spec, longe):
        self.state = "defeated"
        self.attack = None
        self.vx = longe * max(spec.knockback, 8)
        self.vy = -max(spec.lancamento, 7)
        self.no_chao = False
        self.flash_hit = max(self.flash_hit, TAM_HITFLASH)

    def _iniciar_ataque(self, nome):
        spec = _dic(C.ATAQUES[nome])
        self.attack = Attack(nome, spec)
        self.state = "attacking"
        self.buffer.clear()
        self.eventos.append(("ataque", nome))
        if spec.get("projetil"):
            self.energia -= spec.custo
            self.cooldown_especial = spec.cooldown
        if self.no_chao:
            self.vx = 0.0

    def _tentar_ataque(self):
        for nome in ACOES_ATAQUE:
            if self.buffer.get(nome, 0) <= 0:
                continue
            spec = C.ATAQUES[nome]
            if nome == "especial":
                if self.cooldown_especial > 0:
                    self.buffer.pop(nome)
                    continue
                if self.energia < spec["custo"]:
                    self.buffer.pop(nome)
                    self.eventos.append(("erro_energia",))
                    continue
            if self.cooldown > 0:
                continue
            self._iniciar_ataque(nome)
            return True
        return False

    def _avancar_ataque(self):
        a = self.attack
        a.update()
        s = a.spec
        if s.get("projetil") and a.frame == s.startup:
            px, py = self.ponto_mao_especial()
            self.novos_projeteis.append(
                Projectile(self, px + self.facing * 8, py, self.facing, s))
            self.eventos.append(("projetil",))
        if self.no_chao:
            if a.frame < s.startup + s.ativo:
                self.vx = self.facing * s.avanco
            else:
                self.vx *= 0.5
        if a.terminou:
            if not s.get("projetil"):
                self.cooldown = s.cooldown
            self.attack = None
            self.state = "idle" if self.no_chao else "jumping"

    def update(self, held, pressed, oponente, pode_agir):
        self.t += 1
        for k in ("cooldown", "cooldown_especial", "invuln", "flash_hit", "flash_block"):
            v = getattr(self, k)
            if v > 0:
                setattr(self, k, v - 1)
        self.energia = min(C.ENERGIA_MAXIMA, self.energia + C.ENERGIA_POR_SEGUNDO / C.FPS)
        if self.hp_visual > self.hp:
            self.hp_visual = max(self.hp, self.hp_visual - 0.5)
        else:
            self.hp_visual = float(self.hp)

        if not pode_agir:
            held, pressed = {}, ()
            self.buffer.clear()
        else:
            for a in pressed:
                if a in ACOES_ATAQUE:
                    self.buffer[a] = C.BUFFER_INPUT

        s = self.state
        if s == "defeated":
            self._friccao(0.9)
        elif s == "victory":
            self.attack = None
            self._friccao(0.8)
        elif s == "hurt":
            self.hitstun -= 1
            self._friccao(ATRITO_CHAO)
            if self.hitstun <= 0 and self.no_chao:
                self.state = "idle"
                self.combo = 0
                self.invuln = C.INVULNERAVEL_APOS_HIT
        else:
            if self.state == "attacking":
                self._avancar_ataque()
            if self.state in ESTADOS_LIVRES or self.state == "defending":
                self._controlar(held, oponente)
        self._fisica()

        for k in list(self.buffer):
            self.buffer[k] -= 1
            if self.buffer[k] <= 0:
                del self.buffer[k]
        self._atualizar_rastro()

    def _friccao(self, f):
        self.vx *= f if self.no_chao else ATRITO_AR

    def _controlar(self, held, oponente):
        esq = held.get("esquerda", False)
        dir_ = held.get("direita", False)
        dire = (1 if dir_ else 0) - (1 if esq else 0)
        vel = C.VELOCIDADE * self.perfil.velocidade
        if self.no_chao:
            if oponente is not None and abs(oponente.x - self.x) > 2:
                self.facing = 1 if oponente.x > self.x else -1
            if held.get("defesa"):
                self.state = "defending"
                self.vx *= 0.7
                return
            if self.state == "defending":
                self.state = "idle"
            if self._tentar_ataque():
                return
            if held.get("pulo") or self.buffer.get("pulo"):
                self.vy = -C.FORCA_PULO
                self.no_chao = False
                self.state = "jumping"
                self.vx = dire * vel
                self.eventos.append(("pulo",))
                return
            self.vx = dire * vel
            self.state = "walking" if dire else "idle"
        else:
            if self.state == "attacking":
                return
            self.state = "jumping"
            if self._tentar_ataque():
                return
            self.vx = dire * vel if dire else self.vx * 0.92

    def _fisica(self):
        if not self.no_chao or self.vy < 0:
            self.vy += C.GRAVIDADE
        self.x += self.vx
        self.y += self.vy
        minimo = C.MARGEM_ARENA + C.LARGURA_LUTADOR // 2
        maximo = C.LARGURA - minimo
        if self.x < minimo or self.x > maximo:
            self.x = min(max(self.x, minimo), maximo)
            self.vx = 0.0
        if self.y >= C.CHAO_Y:
            if not self.no_chao and self.vy > 2 and self.state in ("jumping", "attacking"):
                self.eventos.append(("pouso",))
            self.y = float(C.CHAO_Y)
            self.vy = 0.0
            self.no_chao = True
            if self.state == "jumping":
                self.state = "idle"
        else:
            self.no_chao = False
        self.rect.midbottom = (round(self.x), round(self.y))

    def _atualizar_rastro(self):
        ponta = None
        a = self.attack
        if self.state == "attacking" and a is not None and a.nome != "especial" \
                and a.frame >= a.spec.startup - 1:
            j = self._juntas()
            p = j["mao_f"] if a.nome == "basico" else j["pe_f"]
            ponta = (self.x + self.facing * p[0], self.y - p[1])
        if ponta is not None:
            self.rastro.append(ponta)
            if len(self.rastro) > LIMITE_RASTRO:
                self.rastro.pop(0)
        elif self.rastro:
            self.rastro.pop(0)

    def ambiente(self, efeitos):
        if self.state == "defeated" or random.random() > 0.11:
            return
        p = self.perfil
        y = self.y - random.uniform(30, 125)
        if self.personagem == "blaze":
            efeitos.particula(self.x + random.uniform(-16, 16), y, random.uniform(-0.3, 0.3),
                              random.uniform(-1.6, -0.6), random.choice((p.cor, p.cor_clara)),
                              random.randint(25, 45), random.uniform(1.5, 3), -0.01)
        else:
            efeitos.particula(self.x + random.uniform(-26, 26), y, random.uniform(-0.4, 0.4),
                              random.uniform(0.2, 0.6), random.choice((p.cor_clara, BRANCO)),
                              random.randint(40, 60), random.uniform(1.5, 2.6), 0.0)

    # ------------------------------------------------------------------- pose
    def _fases(self):
        """(peso do preparo, extensao) do golpe atual, ambos em 0..1."""
        a = self.attack
        s = a.spec
        if a.frame < s.startup:
            return a.frame / max(1, s.startup), 0.0
        if a.frame < s.startup + s.ativo:
            k = min(1.0, (a.frame - s.startup + 1) / 2)
            return 1 - k, k
        r = min(1.0, (a.frame - s.startup - s.ativo) / max(1, s.recuperacao))
        return 0.0, 1 - r * r

    def _juntas(self):
        """Pose em coordenadas locais (x para frente, y para cima, pes em y=0)."""
        t, st = self.t, self.state
        j = dict(quadril=(0, 52), ombro=(3, 90), cabeca=(5, 106),
                 mao_f=(26, 84), mao_t=(14, 92), pe_f=(16, 0), pe_t=(-14, 0),
                 ba_f=-7, ba_t=-7, bp_f=5, bp_t=5, oy=0, orb=None, deitado=False, bolha=False)
        no_ar = not self.no_chao
        if st == "idle":
            b = math.sin(t * 0.1) * 1.6
            j.update(ombro=(3, 90 + b), cabeca=(5, 106 + b), mao_f=(26, 84 + b), mao_t=(15, 92 + b),
                     quadril=(0, 51 + b * 0.4))
        elif st == "walking":
            ph = t * 0.3
            s, c = math.sin(ph), math.cos(ph)
            j.update(pe_f=(s * 18 + 2, max(0, c) * 9), pe_t=(-s * 18 + 2, max(0, -c) * 9),
                     quadril=(0, 51 - abs(s) * 2), mao_f=(23 - s * 7, 84), mao_t=(14 + s * 7, 91),
                     ombro=(5, 89), cabeca=(8, 105))
        if no_ar and st in ("jumping", "attacking"):
            if self.vy < 0:
                j.update(pe_f=(18, 28), pe_t=(-8, 16), bp_f=12, bp_t=-8, mao_f=(26, 100), mao_t=(8, 102))
            else:
                j.update(pe_f=(14, 8), pe_t=(-14, 3), bp_f=6, bp_t=4, mao_f=(24, 104), mao_t=(6, 100))
        elif st == "jumping":
            j.update(pe_f=(12, 6), pe_t=(-12, 6))

        if st == "attacking" and self.attack is not None:
            w, e = self._fases()
            a = self.attack
            alc = a.spec.get("alcance", 0) + self.perfil.alcance_bonus
            solo = self.no_chao
            if a.nome == "basico":
                full = (24 + alc, 90)
                j["mao_f"] = _lerp2(_lerp2((26, 84), (6, 90), w), full, e)
                j["ba_f"] = _lerp(-7, 0, e)
                j["mao_t"] = _lerp2((15, 92), (10, 86), e)
                j["ombro"] = (3 + 5 * e - 3 * w, 90)
                j["cabeca"] = (5 + 6 * e - 3 * w, 106)
                j["quadril"] = (3 * e, 51)
                if solo:
                    j["pe_f"] = (16 + 9 * e, 0)
                    j["pe_t"] = (-14 - 3 * e, 0)
            elif a.nome == "forte":
                cam, full = (12, 38), (28 + alc - 8, 54)
                j["pe_f"] = _lerp2(_lerp2((16, 0), cam, w), full, e)
                j["bp_f"] = _lerp(_lerp(5, 18, w), 0, e)
                j["ombro"] = (3 - 9 * e, 89)
                j["cabeca"] = (5 - 13 * e, 105)
                j["quadril"] = (-3 * e, 52)
                j["mao_f"] = (30 - 12 * e, 82 + 16 * e)
                j["mao_t"] = (10 - 20 * e, 92 + 4 * e)
                if solo:
                    j["pe_t"] = (-12 - 3 * e, 0)
            else:
                crouch = 7 * w * (1 - e) if e < 1 else 0
                j["quadril"] = (0, 52 - crouch)
                j["ombro"] = (3 + 3 * e, 90 - crouch)
                j["cabeca"] = (5 + 4 * e, 106 - crouch)
                j["mao_f"] = _lerp2((30, 78), (46, 84), e)
                j["mao_t"] = _lerp2((24, 74), (38, 80), e)
                j["ba_f"] = j["ba_t"] = _lerp(-6, 0, e)
                if solo:
                    j["pe_f"], j["pe_t"] = (24, 0), (-18, 0)
                    j["bp_f"] = j["bp_t"] = 10
                if a.frame < a.spec.startup:
                    j["orb"] = a.frame / max(1, a.spec.startup)
        elif st == "defending":
            j.update(quadril=(0, 44), ombro=(0, 80), cabeca=(2, 95), mao_f=(26, 90), mao_t=(23, 76),
                     pe_f=(19, 0), pe_t=(-17, 0), bp_f=9, bp_t=9, ba_f=-9, ba_t=-12, bolha=True)
        elif st == "hurt" or (st == "defeated" and not self.no_chao):
            k = 1.0 if st == "hurt" else 1.6
            wob = math.sin(t * 0.8) * 3
            j.update(quadril=(-3, 50), ombro=(-8 * k, 86), cabeca=(-15 * k, 99),
                     mao_f=(20 + wob, 102), mao_t=(-26 * k, 82 - wob), pe_f=(14, 4 if no_ar else 0),
                     pe_t=(-12, 0), ba_f=-3, ba_t=-3)
            if no_ar:
                j.update(pe_f=(16, 14), pe_t=(-10, 8))
        elif st == "defeated":
            j.update(quadril=(0, 10), ombro=(-32, 11), cabeca=(-50, 13), mao_f=(-18, 6),
                     mao_t=(-40, 5), pe_f=(36, 12), pe_t=(34, 4), bp_f=6, bp_t=-4, ba_f=-2, ba_t=-2,
                     deitado=True)
        elif st == "victory":
            hop = abs(math.sin(t * 0.13)) * 14
            j.update(mao_f=(20, 134), mao_t=(-6, 130), ba_f=-3, ba_t=-3, ombro=(2, 90),
                     cabeca=(3, 106), pe_f=(14, 0), pe_t=(-12, 0), oy=hop)
        return j

    # ------------------------------------------------------------------ desenho
    def draw(self, surf, mostrar_hitbox=False):
        j = self._juntas()
        f = self.facing
        p = self.perfil
        blaze = self.personagem == "blaze"
        t = self.t
        oy = j["oy"]
        bx, by = int(round(self.x)), int(round(self.y))
        branco = self.flash_hit > 0 and (self.flash_hit // 2) % 2 == 0

        def cor(c):
            return _mix(c, BRANCO, 0.8) if branco else c

        def P(q):
            return (bx + f * q[0], by - q[1] - oy)

        # sombra
        alt = min(1.0, (C.CHAO_Y - self.y) / 140)
        lg = (74 if not j["deitado"] else 108) * (1 - 0.4 * alt)
        sh = _sombra(lg)
        surf.blit(sh, (bx - sh.get_width() // 2, C.CHAO_Y - 7))

        quad, omb, cab = P(j["quadril"]), P(j["ombro"]), P(j["cabeca"])
        mao_f, mao_t = P(j["mao_f"]), P(j["mao_t"])
        pe_f, pe_t = P(j["pe_f"]), P(j["pe_t"])
        esb = 0.62 if j["deitado"] else 1.0
        larg_membro = 11 if blaze else 9
        raio_cab = 14 if blaze else 13
        sw, hw = (14, 12) if blaze else (11, 9)
        sw, hw = sw * esb, hw * esb
        deriva = -self.vx * 0.6

        tecido = cor(p.cor)
        calca = cor(_mix(p.cor_escura, p.cor, 0.4))    # mais claro que o fundo escuro
        trim = cor(p.cor_clara)
        pele = cor(p.pele)
        bota = cor(p.cor) if blaze else cor(p.cor_clara)

        # --- atras do corpo: faixa (Blaze) / cachecol (Frost)
        if blaze:
            self._faixa(surf, j, P, trim, deriva, t)
        else:
            self._cachecol(surf, j, P, trim, tecido, deriva, t)

        # --- membros de tras
        joelho_t = P(_osso(j["quadril"], j["pe_t"], j["bp_t"]))
        cot_t = P(_osso(j["ombro"], j["mao_t"], j["ba_t"]))
        escura = _mix(calca, (0, 0, 0), 0.25)
        self._perna(surf, quad, joelho_t, pe_t, larg_membro, escura, _mix(bota, (0, 0, 0), 0.3), f)
        manga_t = pele if blaze else _mix(tecido, (0, 0, 0), 0.25)
        self._braco(surf, omb, cot_t, mao_t, larg_membro - 1, manga_t, trim if blaze else cor(p.cor_clara),
                    _mix(trim, (0, 0, 0), 0.25) if blaze else cor(p.cor_clara))

        # --- tronco
        self._tronco(surf, omb, quad, sw, hw, tecido, trim, pele, blaze, f, branco)

        # --- perna e braco da frente
        joelho_f = P(_osso(j["quadril"], j["pe_f"], j["bp_f"]))
        cot_f = P(_osso(j["ombro"], j["mao_f"], j["ba_f"]))
        self._perna(surf, quad, joelho_f, pe_f, larg_membro, calca, bota, f)

        # --- cabeca
        self._cabeca(surf, cab, raio_cab, pele, blaze, j, f, cor, t)

        manga_f = pele if blaze else tecido
        self._braco(surf, omb, cot_f, mao_f, larg_membro - 1, manga_f, trim if blaze else cor(p.cor_clara),
                    trim if blaze else cor(p.cor_clara))

        # --- efeitos de golpe
        if len(self.rastro) > 1:
            self._swoosh(surf, p)
        if j["orb"] is not None:
            self._orb(surf, P((30, 80)), j["orb"])
        if self.attack is not None and self.attack.ativo and not self.attack.spec.get("projetil"):
            _blit_glow(surf, 26, p.cor, self.rastro[-1] if self.rastro else mao_f)
        if j["bolha"]:
            b = _bolha(tuple(p.cor_clara))
            surf.blit(b, (bx + f * 8 - b.get_width() // 2, by - 66 - b.get_height() // 2))
        if self.flash_block > 0:
            _blit_glow(surf, 46, (170, 190, 230), (bx + f * 30, by - 70))
        if branco:
            _blit_glow(surf, 56, (120, 120, 120), (bx, by - 62))

        # --- indicador do jogador
        topo = by - (40 if j["deitado"] else 163) + int(math.sin(t * 0.1) * 3)
        pts = [(bx - 8, topo), (bx + 8, topo), (bx, topo + 11)]
        pygame.draw.polygon(surf, CONTORNO, [(x, y + (1 if i == 2 else 0)) for i, (x, y) in enumerate(pts)], 5)
        pygame.draw.polygon(surf, COR_JOGADOR.get(self.jogador, BRANCO), pts)

        if mostrar_hitbox:
            pygame.draw.rect(surf, (80, 160, 255), self.rect, 1)
            if self.attack is not None:
                hb = self.attack.hitbox(self)
                if hb is not None:
                    pygame.draw.rect(surf, (255, 60, 60), hb, 2)

    # partes -----------------------------------------------------------
    @staticmethod
    def _linhas(surf, pts, larg, cor, contorno=True):
        pts = [(int(x), int(y)) for x, y in pts]
        if contorno:
            pygame.draw.lines(surf, CONTORNO, False, pts, larg + 4)
            for q in pts:
                pygame.draw.circle(surf, CONTORNO, q, larg // 2 + 2)
        pygame.draw.lines(surf, cor, False, pts, larg)
        for q in pts:
            pygame.draw.circle(surf, cor, q, larg // 2)

    def _perna(self, surf, quad, joelho, pe, larg, cor_calca, cor_bota, f):
        self._linhas(surf, [quad, joelho, pe], larg, cor_calca)
        ponta = (pe[0] + f * 8, pe[1])
        self._linhas(surf, [(pe[0] - f * 2, pe[1]), ponta], larg - 1, cor_bota)

    def _braco(self, surf, omb, cot, mao, larg, cor_manga, cor_luva, cor_mao):
        self._linhas(surf, [omb, cot, mao], larg, cor_manga)
        pygame.draw.circle(surf, CONTORNO, (int(mao[0]), int(mao[1])), larg // 2 + 4)
        pygame.draw.circle(surf, cor_luva, (int(mao[0]), int(mao[1])), larg // 2 + 2)
        pygame.draw.circle(surf, cor_mao, (int(mao[0]), int(mao[1])), max(2, larg // 2 - 1))

    def _tronco(self, surf, omb, quad, sw, hw, tecido, trim, pele, blaze, f, branco):
        dx, dy = omb[0] - quad[0], omb[1] - quad[1]
        d = math.hypot(dx, dy) or 1
        nx, ny = -dy / d, dx / d
        pts = [(omb[0] + nx * sw, omb[1] + ny * sw), (omb[0] - nx * sw, omb[1] - ny * sw),
               (quad[0] - nx * hw, quad[1] - ny * hw), (quad[0] + nx * hw, quad[1] + ny * hw)]
        pygame.draw.polygon(surf, CONTORNO, pts, 5)
        pygame.draw.polygon(surf, tecido, pts)
        meio = ((omb[0] * 0.55 + quad[0] * 0.45), (omb[1] * 0.55 + quad[1] * 0.45))
        if blaze:
            # colete aberto mostrando o peito + cinto largo
            v = [(omb[0] + nx * 3, omb[1] + ny * 3), (omb[0] - nx * 3, omb[1] - ny * 3), meio]
            pygame.draw.polygon(surf, pele, v)
            self._linhas(surf, [(quad[0] + nx * hw, quad[1] + ny * hw + 1),
                                (quad[0] - nx * hw, quad[1] - ny * hw + 1)], 6, trim, False)
        else:
            self._linhas(surf, [(omb[0] + nx * sw, omb[1] + ny * sw),
                                (omb[0] - nx * sw, omb[1] - ny * sw)], 5, trim, False)
            r = 5
            pygame.draw.polygon(surf, trim, [(meio[0], meio[1] - r - 1), (meio[0] + r, meio[1]),
                                             (meio[0], meio[1] + r + 1), (meio[0] - r, meio[1])])
            self._linhas(surf, [(quad[0] + nx * hw, quad[1] + ny * hw),
                                (quad[0] - nx * hw, quad[1] - ny * hw)], 3, trim, False)

    def _cabeca(self, surf, cab, r, pele, blaze, j, f, cor, t):
        p = self.perfil
        cx, cy = cab
        cab_i = (int(cx), int(cy))
        k = 0.35 if j["deitado"] else 1.0

        def L(ang, rad):    # ponto em coordenadas polares locais ao redor da cabeca
            return (cx + f * math.cos(ang) * rad, cy - math.sin(ang) * rad)

        # cabelo atras do rosto
        if blaze:
            _blit_glow(surf, 40, (110, 45, 10), cab_i)
            for i in range(6):
                a = math.radians(165 - i * 26)
                h = (16 + 9 * math.sin(self.t * 0.35 + i * 1.9) + (6 if i in (2, 3) else 0)) * k
                tip = L(a + 0.3, r + h)
                pts = [L(a - 0.34, r - 1), tip, L(a + 0.34, r - 1)]
                pygame.draw.polygon(surf, CONTORNO, pts, 4)
                pygame.draw.polygon(surf, cor(p.cor), pts)
                tip2 = L(a + 0.25, r + h * 0.58)
                pygame.draw.polygon(surf, cor(p.cor_clara), [L(a - 0.2, r - 1), tip2, L(a + 0.2, r - 1)])
        else:
            _blit_glow(surf, 36, (30, 80, 120), cab_i)
            formas = ((2.45, 24, 0.30), (2.0, 32, 0.28), (1.62, 38, 0.27), (1.25, 31, 0.28), (0.85, 24, 0.30))
            for i, (a, h, w) in enumerate(formas):
                h = (h + math.sin(self.t * 0.05 + i) * 1.5) * k
                tip = L(a, r + h)
                pts = [L(a - w, r - 1), tip, L(a + w, r - 1)]
                pygame.draw.polygon(surf, CONTORNO, pts, 4)
                pygame.draw.polygon(surf, cor(p.cor_clara), pts)
                pygame.draw.polygon(surf, cor(p.cor), [pts[0], tip, L(a - w * 0.1, r + h * 0.35)])
                pygame.draw.line(surf, BRANCO, L(a + w * 0.4, r), tip, 1)
        # rosto
        pygame.draw.circle(surf, CONTORNO, cab_i, r + 2)
        pygame.draw.circle(surf, pele, cab_i, r)
        morto = self.state in ("defeated",) or (self.state == "hurt" and self.flash_hit > 0)
        ex, ey = cx + f * 6, cy - 2
        if morto:
            for dx in (-3, 3):
                pygame.draw.line(surf, CONTORNO, (ex + dx - 2, ey - 2), (ex + dx + 2, ey + 2), 2)
                pygame.draw.line(surf, CONTORNO, (ex + dx - 2, ey + 2), (ex + dx + 2, ey - 2), 2)
        else:
            pygame.draw.circle(surf, BRANCO, (int(ex), int(ey)), 4)
            pygame.draw.circle(surf, (30, 20, 40) if blaze else (20, 60, 120), (int(ex + f * 1.5), int(ey)), 2)
            if blaze:    # sobrancelha brava
                pygame.draw.line(surf, CONTORNO, (ex - f * 5, ey - 6), (ex + f * 5, ey - 3), 2)
        if blaze:    # faixa por cima da testa
            self._linhas(surf, [(cx - f * (r + 1), cy - 6), (cx + f * (r + 1), cy - 7)], 5,
                         cor(p.cor_clara), False)
            pygame.draw.line(surf, CONTORNO, (cx - f * (r + 1), cy - 3), (cx + f * (r + 1), cy - 4), 1)

    def _faixa(self, surf, j, P, trim, deriva, t):
        cab = j["cabeca"]
        for lado in (0, 1):
            pts = [P((cab[0] - 12, cab[1] - 6))]
            for i in range(1, 4):
                px, py = P((cab[0] - 12 - i * 8, cab[1] - 6 - i * 1.5 - lado * i * 2))
                pts.append((px + deriva * i * 0.5, py + math.sin(t * 0.3 + i + lado * 2) * 3))
            self._linhas(surf, pts, 4, trim)

    def _cachecol(self, surf, j, P, trim, tecido, deriva, t):
        omb = j["ombro"]
        pts = [P((omb[0] + 1, omb[1] + 4))]
        for i in range(1, 7):
            px, py = P((omb[0] - 2 - i * 9, omb[1] + 3 + i * 0.6))
            pts.append((px + deriva * i * 0.4, py + math.sin(t * 0.2 - i * 0.8) * (2 + i * 0.9)))
        self._linhas(surf, pts, 8, trim)
        self._linhas(surf, pts[1:], 3, tecido, False)
        # ponta caindo na frente do peito
        a = P((omb[0] + 3, omb[1] + 2))
        self._linhas(surf, [a, (a[0] + self.facing * 3, a[1] + 16)], 6, trim)

    def _swoosh(self, surf, p):
        pts = self.rastro
        forte = self.attack is not None and self.attack.nome == "forte"
        n = len(pts)
        for i in range(1, n):
            k = i / n
            w = int((9 if forte else 5) * k) + 1
            pygame.draw.line(surf, p.cor_clara if i < n - 1 else BRANCO,
                             (int(pts[i - 1][0]), int(pts[i - 1][1])), (int(pts[i][0]), int(pts[i][1])), w)

    def _orb(self, surf, pos, prog):
        p = self.perfil
        r = _lerp(3, p.proj_raio * 0.95, prog) + math.sin(self.t * 0.6) * 1.5
        pos = (int(pos[0]), int(pos[1]))
        _blit_glow(surf, r * 2.4, p.cor if self.personagem == "blaze" else (60, 130, 200), pos)
        pygame.draw.circle(surf, CONTORNO, pos, int(r) + 2)
        pygame.draw.circle(surf, p.cor, pos, int(r))
        pygame.draw.circle(surf, p.cor_clara, pos, max(1, int(r * 0.62)))
        pygame.draw.circle(surf, BRANCO, pos, max(1, int(r * 0.3)))
