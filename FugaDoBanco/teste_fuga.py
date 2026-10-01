"""Teste automatico (sem janela): python teste_fuga.py"""
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame  # noqa: E402

import main as M  # noqa: E402

segurando = set()


class Teclas:
    def __getitem__(self, k):
        return k in segurando


pygame.key.get_pressed = lambda: Teclas()
g = M.Game()
falhas = []


def ok(cond, msg):
    print(("ok: " if cond else "FALHOU: ") + msg)
    if not cond:
        falhas.append(msg)


def tecla(k):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))


def frames(n, dt=1 / 60):
    for _ in range(n):
        g.frame(dt)


def segurar(k, n):
    segurando.add(k)
    frames(n)
    segurando.discard(k)


def longe():
    for gd in g.guardas:
        gd.pos = list(M.centro(1, 24))
        gd.rota = [gd.pos, gd.pos]
        gd.estado = "PATROL"


def nao_colide(pos):
    return not any(M.solido_em((pos[0] + sx * 9, pos[1] + sy * 9)) for sx in (-1, 1) for sy in (-1, 1))


frames(2)
tecla(pygame.K_s); frames(1); tecla(pygame.K_RETURN); frames(1)
ok(g.estado == "ajuda", "COMO JOGAR abre")
tecla(pygame.K_ESCAPE); frames(1); ok(g.estado == "menu", "ESC volta ao menu")
tecla(pygame.K_w); frames(1); tecla(pygame.K_RETURN); frames(1); ok(g.estado == "jogo", "JOGAR inicia")
longe()

p0 = list(g.p.pos); segurar(pygame.K_d, 30); ok(g.p.pos[0] > p0[0] + 40, "D anda para a direita")
p1 = list(g.p.pos); segurar(pygame.K_a, 30); ok(g.p.pos[0] < p1[0] - 40, "A anda para a esquerda")
p2 = list(g.p.pos); segurando.update({pygame.K_d, pygame.K_w}); frames(20); segurando.clear()
ok(g.p.pos[0] > p2[0] + 20 and g.p.pos[1] < p2[1] - 20, "diagonal D+W")
p3 = list(g.p.pos); segurar(pygame.K_s, 20); ok(g.p.pos[1] > p3[1] + 20, "S desce")
for k in (pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s):
    segurar(k, 90)
    ok(nao_colide(g.p.pos), f"colisao com paredes ({pygame.key.name(k)}) {[round(v) for v in g.p.pos]}")

g.p.pos = list(M.centro(36, 14)); g.desenhar_jogo()
ok(g.cx > 500 and g.cy > 200, "camera acompanha o jogador")
s = M.tile(M.centro(*M.COMECO))
alcanca = True
for alvo in [M.tile(x) for x in g.sacos] + [M.SAIDA]:
    c, n = s, 0
    while c != alvo and n < 400:
        c = M.proximo_passo(c, alvo); n += 1
    alcanca = alcanca and c == alvo
ok(alcanca, "todos os sacos e a saida alcancaveis (BFS)")

# deteccao por guarda (Gerencia)
g.novo_jogo(); longe(); gd = g.guardas[3]
gd.rota = [M.centro(11, 2)] * 2; gd.pos = list(M.centro(11, 2)); gd.ang = 0; g.p.pos = list(M.centro(14, 2))
estados = set()
for _ in range(100):
    g.frame(1 / 60); estados.add(gd.estado)
    if g.estado != "jogo":
        break
ok({"DETECT", "CHASE"} <= estados, f"guarda: PATROL->DETECT->CHASE {sorted(estados)}")
# nao detecta: de costas, longe, atras de parede
def caso(gpos, ang, ppos, n=40):
    g.novo_jogo(); longe(); gd = g.guardas[3]
    gd.rota = [M.centro(*gpos)] * 2; gd.pos = list(M.centro(*gpos)); g.p.pos = list(M.centro(*ppos))
    for _ in range(n):
        if gd.estado != "CHASE": gd.ang = ang
        g.frame(1 / 60)
    return gd.estado, g.alerta
ok(caso((15, 2), 0, (12, 2))[0] == "PATROL", "guarda nao ve quem esta atras")
ok(caso((11, 2), 0, (19, 2))[0] == "PATROL", "guarda nao ve quem esta fora do alcance")
ok(caso((11, 5), math.pi / 2, (11, 8))[0] == "PATROL", "parede bloqueia a visao")

# cameras
for i in range(4):
    g.novo_jogo(); longe(); c = g.cams[i]; a = c.angulo(g.t)
    g.p.pos = [c.pos[0] + math.cos(a) * 80, c.pos[1] + math.sin(a) * 80]
    frames(30); ok(g.alerta > 5, f"camera {i} aumenta o alerta ({round(g.alerta)})")

# captura e recomeco
g.novo_jogo(); g.guardas[0].pos = list(g.p.pos); g.guardas[0].estado = "CHASE"; frames(3)
ok(g.estado == "derrota", "captura -> derrota"); g.desenhar_jogo(); g.telas()
tecla(pygame.K_RETURN); frames(2); ok(g.estado == "jogo", "ENTER tenta de novo")

# saida sem dinheiro
longe(); g.p.pos = list(M.centro(*M.SAIDA)); frames(3); ok(g.estado == "jogo", "saida sem dinheiro nao vence")
# coleta dos 8 sacos
for _ in range(M.NS):
    longe(); g.p.pos = list(g.sacos[0]); frames(2); tecla(pygame.K_e); frames(2)
ok(g.dinheiro == M.NS, f"coletou {g.dinheiro}/{M.NS}")
g.p.pos = list(M.centro(*M.SAIDA)); frames(5); ok(g.estado == "vitoria", "vitoria na saida")
frames(30)
tecla(pygame.K_RETURN); frames(2); ok(g.estado == "jogo" and g.nivel == 1, "proxima partida (mais dificil)")
g.tempo = 0.01; frames(3); ok(g.estado == "derrota" and g.motivo.startswith("TEMPO"), "tempo esgotado")
tecla(pygame.K_ESCAPE); frames(1); ok(g.estado == "menu", "ESC volta ao menu")
print("\nTESTES OK" if not falhas else f"\n{len(falhas)} FALHA(S): {falhas}")
sys.exit(1 if falhas else 0)
