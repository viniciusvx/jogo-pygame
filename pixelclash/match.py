"""Partida: rounds, colisoes de golpes/projeteis, efeitos e fases (intro, fight, ko, fim)."""
import math
import random

import pygame

from . import config as C
from .effects import Efeitos
from .arena import Arena
from .fighter import Fighter

# Duracoes (frames)
INTRO_ROUND = 60          # mostra "ROUND n"
INTRO_FIGHT = 40          # mostra "FIGHT!" ainda sem lutar
MSG_FIGHT_EXTRA = 40      # "FIGHT!" continua na tela no inicio da luta
KO_DURACAO = 160
KO_CAMERA_LENTA = 55      # frames iniciais do KO rodando a meia velocidade
KO_SOM_VITORIA = 45
COMBO_EXIBICAO = 90
HITSTOP_MAX = 14
MAX_PROJETEIS = 8
COR_BLOQUEIO = (170, 215, 255)
COR_DANO = (255, 240, 200)
VAZIO = {"esquerda": False, "direita": False, "defesa": False, "pulo": False,
         "basico": False, "forte": False, "especial": False}

# Efeitos por golpe: (faiscas, raio do anel, tamanho do texto, flash alpha, som)
EFEITO_GOLPE = {
    "basico": dict(n=8, vel=5, anel=34, flash=0, som="soco"),
    "forte": dict(n=16, vel=7, anel=52, flash=40, som="golpe_forte"),
    "especial": dict(n=30, vel=9, anel=90, flash=110, som="impacto_especial"),
}


class Match:
    def __init__(self, audio, fonte_dano):
        self.audio = audio
        self.efeitos = Efeitos(fonte_dano)
        self.arena = Arena()
        esq = C.LARGURA * 0.28
        self.f1 = Fighter(1, "blaze", esq, 1, C.CONTROLES[1])
        self.f2 = Fighter(2, "frost", C.LARGURA - esq, -1, C.CONTROLES[2])
        self.vitorias = [0, 0]
        self.round = 1
        self.timer = C.TEMPO_ROUND * C.FPS
        self.fase = "intro"
        self.fase_t = 0
        self.combo_info = None
        self.msg_round = ""
        self.vencedor_round = 0
        self.terminou = False
        self.vencedor = None
        self.projeteis = []
        self.hitstop = 0
        self._iniciar_round()

    # ------------------------------------------------------------------ rounds
    def _iniciar_round(self):
        self.f1.reset()
        self.f2.reset()
        self.projeteis.clear()
        self.efeitos.limpar()
        self.timer = C.TEMPO_ROUND * C.FPS
        self.fase = "intro"
        self.fase_t = 0
        self.hitstop = 0
        self.combo_info = None
        self.vencedor_round = 0
        self.msg_round = "ROUND %d" % self.round
        self.audio.tocar("round")

    def _encerrar_round(self, motivo):
        h1, h2 = self.f1.hp, self.f2.hp
        if motivo == "ko":
            if h1 <= 0 and h2 <= 0:
                v = 0
            else:
                v = 2 if h1 <= 0 else 1
            self.msg_round = "K.O.!"
        else:
            v = 0 if h1 == h2 else (1 if h1 > h2 else 2)
            self.msg_round = "TEMPO!" if v else "EMPATE"
        self.vencedor_round = v
        self.fase = "ko"
        self.fase_t = 0
        self.projeteis.clear()
        self.combo_info = None
        for f in (self.f1, self.f2):
            f.attack = None
        if v:
            self.vitorias[v - 1] += 1
            (self.f1 if v == 1 else self.f2).state = "victory"
        if motivo == "ko":
            self.audio.tocar("ko")

    def _fim_do_ko(self):
        for i in (0, 1):
            if self.vitorias[i] >= C.ROUNDS_PARA_VENCER:
                self.vencedor = i + 1
                self.terminou = True
                self.fase = "fim"
                self.fase_t = 0
                return
        if self.vencedor_round:
            self.round += 1
        self._iniciar_round()

    # ------------------------------------------------------------------ update
    def update(self, held1, pressed1, held2, pressed2):
        if self.hitstop > 0:
            self.hitstop -= 1
            self.efeitos.update_tremor()
            return

        self.fase_t += 1
        self.arena.update()
        self.efeitos.update()
        if self.combo_info:
            self.combo_info["t"] -= 1
            if self.combo_info["t"] <= 0:
                self.combo_info = None

        if self.fase == "intro":
            self._update_intro()
        elif self.fase == "fight":
            self._update_luta(held1, pressed1, held2, pressed2)
        elif self.fase == "ko":
            self._update_ko()
        else:
            self._update_lutadores(VAZIO, [], VAZIO, [], False)

    def _update_intro(self):
        self._update_lutadores(VAZIO, [], VAZIO, [], False)
        if self.fase_t == INTRO_ROUND:
            self.msg_round = "FIGHT!"
            self.audio.tocar("fight")
        elif self.fase_t >= INTRO_ROUND + INTRO_FIGHT:
            self.fase = "fight"
            self.fase_t = 0

    def _update_luta(self, h1, p1, h2, p2):
        if self.fase_t > MSG_FIGHT_EXTRA and self.msg_round == "FIGHT!":
            self.msg_round = ""
        self.timer -= 1
        self._update_lutadores(h1, p1, h2, p2, True)
        self._resolver_golpes()
        self._update_projeteis()
        self._separar_lutadores()
        if self.f1.hp <= 0 or self.f2.hp <= 0:
            self._encerrar_round("ko")
        elif self.timer <= 0:
            self.timer = 0
            self._encerrar_round("tempo")

    def _update_ko(self):
        # camera lenta: lutadores avancam so em frames pares no inicio
        if self.fase_t > KO_CAMERA_LENTA or self.fase_t % 2 == 0:
            self._update_lutadores(VAZIO, [], VAZIO, [], False)
            self._separar_lutadores()
        for f in (self.f1, self.f2):
            if f.hp <= 0:
                f.state = "defeated"
        v = self.vencedor_round
        if v:
            w = self.f1 if v == 1 else self.f2
            if w.state != "victory":
                w.attack = None
                w.state = "victory"
        if self.fase_t == KO_SOM_VITORIA and v:
            self.audio.tocar("vitoria")
        if self.fase_t >= KO_DURACAO:
            self._fim_do_ko()

    def _update_lutadores(self, h1, p1, h2, p2, pode_agir):
        self.f1.update(h1, p1, self.f2, pode_agir)
        self.f2.update(h2, p2, self.f1, pode_agir)
        for f in (self.f1, self.f2):
            self._processar_eventos(f)
            f.ambiente(self.efeitos)
            self._particulas_de_carga(f)
            if f.novos_projeteis:
                for p in f.novos_projeteis:
                    if len(self.projeteis) < MAX_PROJETEIS:
                        self.projeteis.append(p)
                f.novos_projeteis.clear()

    # ----------------------------------------------------------------- eventos
    def _processar_eventos(self, f):
        for ev in f.eventos:
            tipo = ev[0]
            if tipo == "pulo":
                self.audio.tocar("pulo")
            elif tipo == "pouso":
                self.audio.tocar("pouso")
                self.efeitos.burst(f.x, C.CHAO_Y, (170, 175, 200), n=6, vel=2.5,
                                   vida=(10, 20), tam=(2, 4), grav=0.05, angulo=-math.pi / 2,
                                   abertura=math.pi)
            elif tipo == "ataque":
                self.audio.tocar("especial_carga" if ev[1] == "especial" else "whoosh")
            elif tipo == "erro_energia":
                self.audio.tocar("erro")
            elif tipo == "projetil":
                self.audio.tocar("especial_disparo")
                hx, hy = f.ponto_mao_especial()
                self.efeitos.burst(hx, hy, f.perfil["cor_clara"], n=14, vel=6, vida=(10, 22),
                                   tam=(2, 5), grav=0.0, angulo=0 if f.facing > 0 else math.pi,
                                   abertura=1.6)
                self.efeitos.anel(hx, hy, f.perfil["cor"], r0=6, r1=44, vida=12)
                self.efeitos.tremer(3)
        f.eventos.clear()

    def _particulas_de_carga(self, f):
        a = f.attack
        if a is None or f.state != "attacking" or getattr(a, "nome", None) != "especial":
            return
        if a.ativo or a.terminou or a.frame % 2:
            return
        hx, hy = f.ponto_mao_especial()
        ang = random.uniform(0, math.tau)
        dist = random.uniform(30, 60)
        vida = 14
        px, py = hx + math.cos(ang) * dist, hy + math.sin(ang) * dist
        cor = f.perfil["cor_clara"] if a.frame % 4 else f.perfil["cor"]
        self.efeitos.particula(px, py, (hx - px) / vida, (hy - py) / vida, cor, vida,
                               random.randint(2, 4))

    # ------------------------------------------------------------------- golpes
    @staticmethod
    def _spec_de(attack):
        spec = getattr(attack, "spec", None)
        if spec is None:
            spec = C.ATAQUES.get(getattr(attack, "nome", None))
        return spec

    def _resolver_golpes(self):
        # coleta primeiro para que os dois golpes do mesmo frame se resolvam (trade)
        acertos = []
        for atq, alvo in ((self.f1, self.f2), (self.f2, self.f1)):
            a = atq.attack
            if a is None or not a.ativo or a.acertou:
                continue
            caixa = a.hitbox(atq)
            if caixa is not None and alvo.pode_ser_atingido() and caixa.colliderect(alvo.rect):
                acertos.append((atq, alvo, a, caixa))
        for atq, alvo, a, caixa in acertos:
            spec = self._spec_de(a)
            a.acertou = True
            inter = caixa.clip(alvo.rect)
            ponto = inter.center if inter.width and inter.height else alvo.rect.center
            self._aplicar_golpe(atq, alvo, spec, getattr(a, "nome", "basico"), ponto)

    def _update_projeteis(self):
        for p in self.projeteis:
            p.update(self.efeitos)
        # projetil contra projetil
        ps = self.projeteis
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                a, b = ps[i], ps[j]
                if a.vivo and b.vivo and a.dono is not b.dono and a.rect.colliderect(b.rect):
                    a.vivo = b.vivo = False
                    mx = (a.rect.centerx + b.rect.centerx) / 2
                    my = (a.rect.centery + b.rect.centery) / 2
                    self.efeitos.burst(mx, my, a.dono.perfil["cor_clara"], n=18, vel=7,
                                       faiscas=True)
                    self.efeitos.burst(mx, my, b.dono.perfil["cor_clara"], n=18, vel=7,
                                       faiscas=True)
                    self.efeitos.anel(mx, my, (255, 255, 255), r0=10, r1=80, vida=16, largura=4)
                    self.efeitos.tremer(5)
                    self.efeitos.flashar(60)
                    self.audio.tocar("impacto_especial")
        # projetil contra oponente
        for p in ps:
            if not p.vivo:
                continue
            alvo = self.f2 if p.dono is self.f1 else self.f1
            if alvo.pode_ser_atingido() and p.rect.colliderect(alvo.rect):
                p.vivo = False
                self._aplicar_golpe(p.dono, alvo, p.spec, "especial", p.rect.center, p.x)
        self.projeteis = [p for p in ps if p.vivo]

    def _aplicar_golpe(self, atq, alvo, spec, nome, ponto, x_origem=None):
        res = alvo.receber_golpe(spec, atq.x if x_origem is None else x_origem)
        px, py = ponto
        ef = EFEITO_GOLPE.get(nome, EFEITO_GOLPE["basico"])
        cor = atq.perfil["cor_clara"]
        dano = alvo.ultimo_dano
        direcao = 1 if alvo.x >= atq.x else -1
        ang = 0 if direcao > 0 else math.pi
        ganho = spec["energia"]

        if res == "block":
            ganho //= 2
            self.efeitos.burst(px, py, COR_BLOQUEIO, n=ef["n"] // 2 + 3, vel=ef["vel"] * 0.8,
                               faiscas=True, angulo=ang + math.pi, abertura=2.2)
            self.efeitos.anel(px, py, COR_BLOQUEIO, r0=6, r1=ef["anel"] * 0.6, vida=10)
            self.efeitos.tremer(spec["tremor"] // 3)
            self.hitstop = max(self.hitstop, min(HITSTOP_MAX, spec["hitstop"] // 2))
            self.audio.tocar("bloqueio")
            self.efeitos.texto(alvo.x, alvo.rect.top - 10, "-%d" % dano, COR_BLOQUEIO)
        else:
            self.efeitos.burst(px, py, cor, n=ef["n"], vel=ef["vel"], faiscas=True,
                               angulo=ang, abertura=2.4)
            self.efeitos.burst(px, py, (255, 255, 255), n=ef["n"] // 3 + 2, vel=ef["vel"] * 0.6,
                               vida=(8, 16))
            self.efeitos.anel(px, py, cor, r0=8, r1=ef["anel"], vida=14)
            self.efeitos.tremer(spec["tremor"])
            if ef["flash"]:
                self.efeitos.flashar(ef["flash"])
            self.hitstop = max(self.hitstop, min(HITSTOP_MAX, spec["hitstop"]))
            self.audio.tocar(ef["som"])
            self.efeitos.texto(alvo.x, alvo.rect.top - 10, "-%d" % dano,
                               cor if nome != "basico" else COR_DANO)
            if alvo.combo >= 2:
                self.combo_info = dict(lado=atq.jogador, n=alvo.combo, t=COMBO_EXIBICAO)
                self.efeitos.texto(alvo.x, alvo.rect.top - 38, "%d HITS!" % alvo.combo, cor)

        atq.energia = min(C.ENERGIA_MAXIMA, atq.energia + ganho)

        if alvo.hp <= 0:
            self.efeitos.burst(px, py, (255, 255, 255), n=34, vel=10, faiscas=True)
            self.efeitos.anel(px, py, (255, 255, 255), r0=10, r1=130, vida=22, largura=5)
            self.efeitos.tremer(14)
            self.efeitos.flashar(170)
            self.hitstop = max(self.hitstop, HITSTOP_MAX)

    # ------------------------------------------------------------- colisao fisica
    def _separar_lutadores(self):
        a, b = self.f1, self.f2
        if not a.rect.colliderect(b.rect):
            return
        sobra = min(a.rect.right, b.rect.right) - max(a.rect.left, b.rect.left)
        if sobra <= 0:
            return
        esq, dir_ = (a, b) if (a.x, -a.facing) <= (b.x, -b.facing) else (b, a)
        lim_e = C.MARGEM_ARENA + esq.rect.width / 2
        lim_d = C.LARGURA - C.MARGEM_ARENA - dir_.rect.width / 2
        meia = sobra / 2
        esq.x -= meia
        dir_.x += meia
        # se um bateu na parede, o outro leva o resto
        if esq.x < lim_e:
            dir_.x += lim_e - esq.x
            esq.x = lim_e
        if dir_.x > lim_d:
            esq.x -= dir_.x - lim_d
            dir_.x = lim_d
        esq.x = max(esq.x, lim_e)
        dir_.x = min(dir_.x, lim_d)
        for f in (a, b):
            f.rect.midbottom = (round(f.x), round(f.y))

    # --------------------------------------------------------------------- draw
    def draw(self, surf, mostrar_hitbox=None):
        if mostrar_hitbox is None:
            mostrar_hitbox = C.MOSTRAR_HITBOXES
        self.arena.draw(surf)
        # quem esta atacando fica na frente
        ordem = [self.f1, self.f2]
        if self.f1.state == "attacking" and self.f2.state != "attacking":
            ordem.reverse()
        if self.f1.state == "defeated":
            ordem = [self.f1, self.f2]
        elif self.f2.state == "defeated":
            ordem = [self.f2, self.f1]
        for f in ordem:
            f.draw(surf, mostrar_hitbox)
        for p in self.projeteis:
            p.draw(surf)
        self.efeitos.draw(surf)
        self.efeitos.draw_flash(surf)
