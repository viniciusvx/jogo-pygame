"""Loop principal, estados (menu, controles, luta, pausa, resultado) e entrada."""
import math
import random
import sys

import pygame

from . import config as C
from . import ui
from .arena import Arena
from .audio import Audio
from .effects import Efeitos
from .fighter import Fighter
from .match import Match

MENU, CONTROLES, LUTA, PAUSA, RESULTADO = "MENU", "CONTROLES", "LUTA", "PAUSA", "RESULTADO"

ACOES = ("esquerda", "direita", "defesa", "pulo", "basico", "forte", "especial")
ROTULOS = (
    ("esquerda", "Mover para esquerda"), ("direita", "Mover para direita"),
    ("pulo", "Pular"), ("defesa", "Defender"),
    ("basico", "Soco (rapido)"), ("forte", "Chute forte"),
    ("especial", "Especial (50 energia)"),
)
CONFETE_N = 140
CONFETE_CORES = ((255, 80, 80), (255, 220, 70), (80, 240, 255), (255, 90, 220), (120, 255, 140), (255, 255, 255))
ATRASO_RESULTADO = 110  # frames entre o fim da luta e a tela de resultado


class Game:
    def __init__(self):
        pygame.init()
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except pygame.error:
            pass  # sem audio: Audio fica em silencio
        pygame.display.set_caption(C.TITULO)
        try:
            self.tela = pygame.display.set_mode((C.LARGURA, C.ALTURA), pygame.SCALED | pygame.RESIZABLE)
        except pygame.error:
            self.tela = pygame.display.set_mode((C.LARGURA, C.ALTURA))
        self.canvas = pygame.Surface((C.LARGURA, C.ALTURA))
        self.clock = pygame.time.Clock()
        self.fontes = ui.Fontes()
        self.audio = Audio()
        self.rodando = True
        self.t = 0
        self.estado = MENU
        self.mostrar_hitbox = C.MOSTRAR_HITBOXES
        self.rng = random.Random()

        self.menu = ui.Menu(["JOGAR", "CONTROLES", "SAIR"])
        self.menu_pausa = ui.Menu(["CONTINUAR", "VOLTAR AO MENU"])
        self.match = None
        self.fim_t = 0
        self.confete = [[0.0] * 7 for _ in range(CONFETE_N)]
        self._iniciar_fundo_menu()

    # --- preparo -------------------------------------------------------------
    def _iniciar_fundo_menu(self):
        self.arena_menu = Arena()
        self.efeitos_menu = Efeitos(self.fontes.pequena)
        self.menu_f1 = Fighter(1, "blaze", 250, 1, C.CONTROLES[1])
        self.menu_f2 = Fighter(2, "frost", C.LARGURA - 250, -1, C.CONTROLES[2])

    def novo_match(self):
        self.match = Match(self.audio, self.fontes.pequena)
        self.fim_t = 0
        self.estado = LUTA

    def ir_menu(self):
        self.estado = MENU
        self.menu.sel = 0
        self.match = None

    # --- entrada -------------------------------------------------------------
    def _segurados(self, teclas, jogador):
        mapa = C.CONTROLES[jogador]
        return {a: bool(teclas[mapa[a]]) for a in ACOES}

    def _apertados(self, eventos, jogador):
        mapa = C.CONTROLES[jogador]
        inv = {tecla: a for a, tecla in mapa.items()}
        return [inv[e.key] for e in eventos if e.type == pygame.KEYDOWN and e.key in inv]

    def _confirmar_menu(self):
        item = self.menu.itens[self.menu.sel]
        self.audio.tocar("confirmar")
        if item == "JOGAR":
            self.novo_match()
        elif item == "CONTROLES":
            self.estado = CONTROLES
        else:
            self.rodando = False

    def _confirmar_pausa(self):
        self.audio.tocar("confirmar")
        if self.menu_pausa.sel == 0:
            self.estado = LUTA
        else:
            self.ir_menu()

    def _navegar(self, menu, e):
        """Setas/WASD/mouse num Menu. Retorna True se ENTER/clique confirmou."""
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_UP, pygame.K_w):
                menu.mover(-1)
                self.audio.tocar("selecionar")
            elif e.key in (pygame.K_DOWN, pygame.K_s):
                menu.mover(1)
                self.audio.tocar("selecionar")
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return True
        elif e.type == pygame.MOUSEMOTION:
            i = menu.item_em(e.pos)
            if i is not None and i != menu.sel:
                menu.sel = i
                self.audio.tocar("selecionar")
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            i = menu.item_em(e.pos)
            if i is not None:
                menu.sel = i
                return True
        return False

    def _eventos(self, eventos):
        for e in eventos:
            if e.type == pygame.QUIT:
                self.rodando = False
                continue
            if e.type == pygame.KEYDOWN and e.key == pygame.K_F1:
                self.mostrar_hitbox = not self.mostrar_hitbox
                continue
            if self.estado == MENU:
                if self._navegar(self.menu, e):
                    self._confirmar_menu()
            elif self.estado == CONTROLES:
                if (e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_BACKSPACE)) \
                        or e.type == pygame.MOUSEBUTTONDOWN:
                    self.audio.tocar("selecionar")
                    self.estado = MENU
            elif self.estado == LUTA:
                if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_p):
                    self.menu_pausa.sel = 0
                    self.estado = PAUSA
                    self.audio.tocar("selecionar")
            elif self.estado == PAUSA:
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    self.estado = LUTA
                elif self._navegar(self.menu_pausa, e):
                    self._confirmar_pausa()
            elif self.estado == RESULTADO:
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_r:
                        self.audio.tocar("confirmar")
                        self.novo_match()
                    elif e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.audio.tocar("selecionar")
                        self.ir_menu()

    # --- atualizacao -----------------------------------------------------------
    def _update_menu_fundo(self):
        vazio = {a: False for a in ACOES}
        for f, op in ((self.menu_f1, self.menu_f2), (self.menu_f2, self.menu_f1)):
            f.update(vazio, [], op, True)
            f.eventos.clear()
            f.ambiente(self.efeitos_menu)
        self.arena_menu.update()
        self.efeitos_menu.update()

    def _update_luta(self, eventos):
        teclas = pygame.key.get_pressed()
        self.match.update(
            self._segurados(teclas, 1), self._apertados(eventos, 1),
            self._segurados(teclas, 2), self._apertados(eventos, 2),
        )
        if self.match.terminou:
            self.fim_t += 1
            if self.fim_t >= ATRASO_RESULTADO:
                self._entrar_resultado()

    def _entrar_resultado(self):
        self.estado = RESULTADO
        self.fim_t = 0
        self.audio.tocar("vitoria")
        for c in self.confete:
            self._reciclar_confete(c, inicial=True)

    def _reciclar_confete(self, c, inicial=False):
        c[0] = self.rng.uniform(0, C.LARGURA)
        c[1] = self.rng.uniform(-C.ALTURA, 0) if inicial else self.rng.uniform(-40, -5)
        c[2] = self.rng.uniform(-0.8, 0.8)
        c[3] = self.rng.uniform(1.2, 3.2)
        c[4] = self.rng.randrange(len(CONFETE_CORES))
        c[5] = self.rng.uniform(0, 6.28)
        c[6] = self.rng.uniform(0.05, 0.2)

    def _update_resultado(self):
        self.fim_t += 1
        for c in self.confete:
            c[0] += c[2] + math.sin(c[5]) * 0.6
            c[1] += c[3]
            c[5] += c[6]
            if c[1] > C.ALTURA + 10:
                self._reciclar_confete(c)
        if self.match is not None:
            # mantem animacao de vitoria/particulas sem input
            vazio = {a: False for a in ACOES}
            self.match.update(vazio, [], vazio, [])

    def update(self, eventos):
        self.t += 1
        self._eventos(eventos)
        if self.estado in (MENU, CONTROLES):
            self._update_menu_fundo()
        elif self.estado == LUTA:
            self._update_luta(eventos)
        elif self.estado == RESULTADO:
            self._update_resultado()

    # --- desenho ---------------------------------------------------------------
    def _draw_fundo_menu(self, surf):
        self.arena_menu.draw(surf)
        self.menu_f1.draw(surf)
        self.menu_f2.draw(surf)
        self.efeitos_menu.draw(surf)
        veu = self._veu(110)
        surf.blit(veu, (0, 0))

    def _veu(self, alpha):
        if not hasattr(self, "_veus"):
            self._veus = {}
        v = self._veus.get(alpha)
        if v is None:
            v = pygame.Surface((C.LARGURA, C.ALTURA), pygame.SRCALPHA)
            v.fill((4, 4, 16, alpha))
            self._veus[alpha] = v
        return v

    def _draw_menu(self, surf):
        self._draw_fundo_menu(surf)
        cx = C.LARGURA // 2
        ui.desenhar_titulo(surf, self.fontes, cx, 120, self.t)
        ui.desenhar_texto(surf, self.fontes.pequena, "LUTA LOCAL PARA 2 JOGADORES", ui.CIANO, (cx, 190))
        self.menu.draw(surf, cx, 245, self.t, self.fontes)
        ui.desenhar_texto(surf, self.fontes.mini, "Setas / W S + ENTER  |  Mouse", ui.CINZA, (cx, C.ALTURA - 18))
        ui.desenhar_neon(surf, self.fontes.media, "BLAZE", C.PERSONAGENS["blaze"]["cor"], (250, 486), self.t)
        ui.desenhar_neon(surf, self.fontes.media, "FROST", C.PERSONAGENS["frost"]["cor"], (C.LARGURA - 250, 486), self.t)

    def _painel_controles(self, surf, jogador, x, y, w):
        perfil = C.PERSONAGENS["blaze" if jogador == 1 else "frost"]
        h = 300
        painel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(painel, (10, 12, 30, 215), painel.get_rect(), border_radius=12)
        surf.blit(painel, (x, y))
        pygame.draw.rect(surf, perfil["cor"], (x, y, w, h), 3, border_radius=12)
        ui.desenhar_texto(surf, self.fontes.media, f"PLAYER {jogador} - {perfil['nome'].upper()}",
                          perfil["cor_clara"], (x + w // 2, y + 28))
        for i, (acao, rotulo) in enumerate(ROTULOS):
            yy = y + 68 + i * 32
            ui.desenhar_texto(surf, self.fontes.pequena, rotulo, ui.CINZA, (x + 18, yy), "midleft")
            nome = pygame.key.name(C.CONTROLES[jogador][acao]).upper()
            tecla = ui.texto(self.fontes.pequena, nome, ui.BRANCO, None)
            caixa = pygame.Rect(0, 0, max(34, tecla.get_width() + 18), 26)
            caixa.midright = (x + w - 16, yy)
            pygame.draw.rect(surf, (30, 40, 90), caixa, border_radius=6)
            pygame.draw.rect(surf, ui.CIANO, caixa, 2, border_radius=6)
            surf.blit(tecla, tecla.get_rect(center=caixa.center))

    def _draw_controles(self, surf):
        self._draw_fundo_menu(surf)
        surf.blit(self._veu(130), (0, 0))
        cx = C.LARGURA // 2
        ui.desenhar_neon(surf, self.fontes.grande, "CONTROLES", ui.CIANO, (cx, 48), self.t)
        self._painel_controles(surf, 1, 40, 90, 400)
        self._painel_controles(surf, 2, C.LARGURA - 440, 90, 400)
        geral = "ESC pausa   |   F1 hitboxes   |   R jogar de novo (no resultado)   |   Melhor de 3 rounds"
        ui.desenhar_texto(surf, self.fontes.pequena, geral, ui.AMARELO, (cx, 418))
        ui.desenhar_texto(surf, self.fontes.pequena, "Dica: defender reduz o dano; golpes seguidos encurtam o combo.",
                          ui.CINZA, (cx, 446))
        if (self.t // 30) % 2 == 0:
            ui.desenhar_texto(surf, self.fontes.pequena, "ESC / ENTER  voltar", ui.BRANCO, (cx, 490))

    def _draw_luta(self, surf):
        m = self.match
        m.draw(self.canvas)
        if self.mostrar_hitbox:
            self._draw_hitboxes(self.canvas)
        dx, dy = m.efeitos.offset
        surf.fill((0, 0, 0))
        surf.blit(self.canvas, (dx, dy))
        ui.desenhar_hud(surf, m, self.fontes, self.t)
        ui.desenhar_textos_centrais(surf, m, self.fontes)
        m.efeitos.draw_flash(surf)

    def _draw_hitboxes(self, surf):
        for f in (self.match.f1, self.match.f2):
            pygame.draw.rect(surf, (0, 255, 120), f.rect, 1)
            if f.attack is not None:
                hb = f.attack.hitbox(f)
                if hb is not None:
                    pygame.draw.rect(surf, (255, 60, 60), hb, 2)

    def _draw_pausa(self, surf):
        self._draw_luta(surf)
        surf.blit(self._veu(170), (0, 0))
        cx = C.LARGURA // 2
        ui.desenhar_neon(surf, self.fontes.grande, "PAUSADO", ui.AMARELO, (cx, 150), self.t)
        self.menu_pausa.draw(surf, cx, 210, self.t, self.fontes)

    def _draw_resultado(self, surf):
        m = self.match
        self._draw_luta(surf)
        surf.blit(self._veu(120), (0, 0))
        cx = C.LARGURA // 2
        venc = m.vencedor or 1
        perfil = (m.f1 if venc == 1 else m.f2).perfil
        for c in self.confete:
            cor = CONFETE_CORES[int(c[4])]
            larg = 2 + int(abs(math.sin(c[5])) * 8)
            pygame.draw.rect(surf, cor, (int(c[0]), int(c[1]), larg, 8))
        zoom = min(1.0, self.fim_t / 18)
        escala = 1.0 + 0.9 * (1 - zoom) ** 2 + 0.04 * math.sin(self.t * 0.12)
        img = ui.texto(self.fontes.titulo, f"PLAYER {venc} WINS!", perfil["cor_clara"], (20, 10, 40))
        img = pygame.transform.smoothscale(img, (int(img.get_width() * escala), int(img.get_height() * escala)))
        halo = ui.brilho_texto(self.fontes.titulo, f"PLAYER {venc} WINS!", perfil["cor"])
        surf.blit(halo, halo.get_rect(center=(cx, 160)), special_flags=pygame.BLEND_ADD)
        surf.blit(img, img.get_rect(center=(cx, 160)))
        ui.desenhar_texto(surf, self.fontes.grande, f"{m.f1.nome.upper()}  {m.vitorias[0]}  x  {m.vitorias[1]}  {m.f2.nome.upper()}",
                          ui.BRANCO, (cx, 250))
        ui.desenhar_texto(surf, self.fontes.pequena, "PLACAR FINAL (melhor de 3)", ui.CINZA, (cx, 288))
        if (self.t // 25) % 2 == 0:
            ui.desenhar_texto(surf, self.fontes.media, "R  JOGAR DE NOVO", ui.AMARELO, (cx, 350))
        ui.desenhar_texto(surf, self.fontes.media, "ESC  MENU", ui.CIANO, (cx, 390))

    def draw(self):
        s = self.tela
        if self.estado == MENU:
            self._draw_menu(s)
        elif self.estado == CONTROLES:
            self._draw_controles(s)
        elif self.estado == LUTA:
            self._draw_luta(s)
        elif self.estado == PAUSA:
            self._draw_pausa(s)
        elif self.estado == RESULTADO:
            self._draw_resultado(s)

    # --- loop ------------------------------------------------------------------
    def frame(self, eventos=None):
        """Um quadro completo (eventos, logica, desenho). Usado por run() e pelos testes."""
        if eventos is None:
            eventos = pygame.event.get()
        self.update(eventos)
        self.draw()

    def run(self):
        while self.rodando:
            self.frame()
            pygame.display.flip()
            self.clock.tick(C.FPS)
        pygame.quit()
        sys.exit()
