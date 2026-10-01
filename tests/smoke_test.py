"""Teste de fumaca headless: menu -> controles -> luta -> pausa -> KO -> resultado -> R -> menu.

Uso: python tests/smoke_test.py   (define SDL dummy sozinho)
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from pixelclash import config as C  # noqa: E402
from pixelclash import game as G  # noqa: E402

SHOTS = os.environ.get("SMOKE_SHOTS")  # pasta opcional para salvar screenshots

_segurando = set()


class _Teclas:
    def __getitem__(self, k):
        return k in _segurando


pygame.key.get_pressed = lambda: _Teclas()


def ev(tecla):
    return pygame.event.Event(pygame.KEYDOWN, key=tecla, mod=0, unicode="", scancode=0)


def passos(jogo, n, eventos=None):
    for i in range(n):
        jogo.frame(eventos if i == 0 and eventos else [])


def foto(jogo, nome):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        pygame.image.save(jogo.tela, os.path.join(SHOTS, nome + ".png"))


def main():
    jogo = G.Game()
    p1, p2 = C.CONTROLES[1], C.CONTROLES[2]

    passos(jogo, 90)
    assert jogo.estado == G.MENU
    foto(jogo, "menu")

    # menu -> controles -> volta
    passos(jogo, 1, [ev(pygame.K_DOWN)])
    assert jogo.menu.sel == 1
    passos(jogo, 1, [ev(pygame.K_RETURN)])
    assert jogo.estado == G.CONTROLES
    passos(jogo, 40)
    foto(jogo, "controles")
    passos(jogo, 1, [ev(pygame.K_ESCAPE)])
    assert jogo.estado == G.MENU

    # menu -> luta
    passos(jogo, 1, [ev(pygame.K_UP)])
    assert jogo.menu.sel == 0
    passos(jogo, 1, [ev(pygame.K_RETURN)])
    assert jogo.estado == G.LUTA and jogo.match is not None
    m = jogo.match

    # intro -> fight
    for _ in range(600):
        if m.fase == "fight":
            break
        passos(jogo, 1)
    assert m.fase == "fight", m.fase
    passos(jogo, 20)

    # os dois jogadores se movem e atacam
    _segurando.update({p1["direita"], p2["esquerda"]})
    x1, x2 = m.f1.x, m.f2.x
    passos(jogo, 40)
    assert m.f1.x > x1 and m.f2.x < x2, "lutadores deveriam andar"
    _segurando.clear()
    ataques = [p1["basico"], p1["forte"], p1["especial"], p2["basico"], p2["forte"], p2["especial"],
               p1["pulo"], p2["pulo"], p1["defesa"], p2["defesa"]]
    for i in range(240):
        k = ataques[(i // 6) % len(ataques)]
        _segurando.add(k)
        passos(jogo, 1, [ev(k)])
        _segurando.discard(k)
    foto(jogo, "luta")

    # pausa e retomada
    passos(jogo, 1, [ev(pygame.K_ESCAPE)])
    assert jogo.estado == G.PAUSA
    passos(jogo, 10)
    foto(jogo, "pausa")
    hp = m.f1.hp
    passos(jogo, 30)
    assert m.f1.hp == hp, "pausa nao pode avancar a luta"
    passos(jogo, 1, [ev(pygame.K_DOWN)])
    passos(jogo, 1, [ev(pygame.K_UP)])
    passos(jogo, 1, [ev(pygame.K_RETURN)])  # CONTINUAR
    assert jogo.estado == G.LUTA

    # pausa -> voltar ao menu -> nova luta
    passos(jogo, 1, [ev(pygame.K_ESCAPE)])
    passos(jogo, 1, [ev(pygame.K_DOWN)])
    passos(jogo, 1, [ev(pygame.K_RETURN)])
    assert jogo.estado == G.MENU and jogo.match is None
    passos(jogo, 1, [ev(pygame.K_RETURN)])
    assert jogo.estado == G.LUTA
    m = jogo.match
    for _ in range(600):
        if m.fase == "fight":
            break
        passos(jogo, 1)
    assert m.fase == "fight"

    # P1 vence 2 rounds: deixa P2 com 1 de vida e ataca ate o KO
    chegou = False
    for _ in range(40000):
        if m.fase == "fight":
            if m.f2.hp > 1:
                m.f2.hp = 1
            _segurando.add(p1["direita"])
            passos(jogo, 1, [ev(p1["basico"])])
            _segurando.discard(p1["direita"])
        else:
            passos(jogo, 1)
        if m.fase == "ko" and not chegou:
            chegou = True
            passos(jogo, 6)
            foto(jogo, "ko")
        if jogo.estado == G.RESULTADO:
            break
    assert chegou, "nunca houve KO"
    assert jogo.estado == G.RESULTADO, jogo.estado
    assert m.terminou and m.vencedor == 1, (m.terminou, m.vencedor)
    passos(jogo, 60)
    foto(jogo, "resultado")

    # R reinicia, ESC volta ao menu
    passos(jogo, 1, [ev(pygame.K_r)])
    assert jogo.estado == G.LUTA and jogo.match is not m
    passos(jogo, 30)
    passos(jogo, 1, [ev(pygame.K_ESCAPE)])
    passos(jogo, 1, [ev(pygame.K_DOWN)])
    passos(jogo, 1, [ev(pygame.K_RETURN)])
    assert jogo.estado == G.MENU
    passos(jogo, 1, [ev(pygame.K_F1)])
    assert jogo.mostrar_hitbox != C.MOSTRAR_HITBOXES

    # SAIR
    passos(jogo, 1, [ev(pygame.K_DOWN)])
    passos(jogo, 1, [ev(pygame.K_DOWN)])
    passos(jogo, 1, [ev(pygame.K_RETURN)])
    assert not jogo.rodando
    pygame.quit()
    print("smoke_test OK")


if __name__ == "__main__":
    main()
