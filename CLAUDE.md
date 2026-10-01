# PIXEL CLASH — guia do projeto

Jogo de luta 2D local para 2 jogadores (Python 3 + Pygame, sem imagens externas, roda no Windows).
Oficina de ~4h: **simples, estável, divertido**. Não adicionar dependências além do Pygame (nada de numpy).

## Regras de código
- Identificadores em português sem acento; nomes de classe em inglês: `Fighter, Attack, Projectile, Particle, Game, Match, Arena`.
- Constantes ficam em `pixelclash/config.py` (já pronto — **não alterar**, só ler). Sem números mágicos espalhados.
- Toda a lógica é em **frames** (60 FPS fixo). Sem dt.
- Comentários só onde não é óbvio. Evitar criar Surfaces/objetos por frame (usar cache). Máx. partículas = `MAX_PARTICULAS`.
- Estados do lutador (strings): `idle, walking, jumping, attacking, defending, hurt, defeated, victory`.
- Cada módulo importa só: `import pygame`, `from . import config as C` e os módulos listados em "depende de".

## Módulos e contratos (a API abaixo é fixa; módulos são escritos em paralelo)

### effects.py (depende de: config)
- `glow(raio, cor) -> Surface` cache; surface preta sem alpha para `blit(..., special_flags=pygame.BLEND_ADD)`.
- `class Particle` (`__slots__`).
- `class Efeitos(fonte)`: `fonte` = pygame Font para textos de dano.
  - `burst(x, y, cor, n=10, vel=5, vida=(15,30), tam=(2,5), grav=0.2, faiscas=False, angulo=None, abertura=6.283)` — `faiscas=True` desenha linhas na direção da velocidade; `angulo` (rad) centra o leque; respeita `MAX_PARTICULAS`.
  - `particula(x, y, vx, vy, cor, vida, tam, grav=0.0)` — emite uma única.
  - `anel(x, y, cor, r0=8, r1=60, vida=14, largura=3)`; `texto(x, y, txt, cor)` (sobe e some);
  - `tremer(v)` (guarda o máximo), `flashar(alpha, cor=(255,255,255))`;
  - `update()`, `update_tremor()` (só tremor/flash, usado no hitstop), `offset` (property → `(dx, dy)` inteiros);
  - `draw(surf)` partículas+anéis+textos; `draw_flash(surf)` overlay de flash em tela cheia (Surface pré-alocada).
  - `limpar()`.

### audio.py (depende de: config)
- `class Audio`: `tocar(nome)` nunca falha (sem mixer = silêncio). Sons gerados com `array` + `pygame.mixer.Sound(buffer=...)`, respeitando `mixer.get_init()` (freq/canais). Se existir `assets/sons/<nome>.wav|ogg` usa o arquivo.
- Nomes: `soco, golpe_forte, bloqueio, whoosh, especial_carga, especial_disparo, impacto_especial, pulo, pouso, ko, selecionar, confirmar, round, fight, vitoria, erro`.

### arena.py (depende de: config, effects.glow)
- `class Arena`: `update()`, `draw(surf)`. Fundo neon/futurista em cache (céu degradê, sol synthwave suave, skyline com janelas, pilares neon, chão com grid em perspectiva); animado: estrelas piscando, poeira/partículas subindo, scanline no chão, linha do chão pulsando. Chão em `C.CHAO_Y`. Cenário **não** pode ofuscar os lutadores (tons escuros/frios).

### fighter.py (depende de: config, effects.glow)
- `class Attack(nome, spec)`: `frame`, `acertou` (bool), `ativo` (property), `fase`, `terminou`, `update()`, `hitbox(fighter) -> Rect|None` (None se projétil/inativo).
- `class Projectile(dono, x, y, direcao, spec)`: `dono`, `spec`, `x, y`, `rect`, `vivo`, `update(efeitos)` (move, emite rastro, `vivo=False` ao sair da tela), `draw(surf)`. Visual: Blaze = bola de fogo, Frost = cristal de gelo (usa `dono.perfil`).
- `class Fighter(jogador, personagem, x, facing, controles)`:
  - atributos: `jogador, perfil, nome, x, y, vx, vy, facing(±1), hp, hp_visual, energia, state, attack, cooldown, cooldown_especial, invuln, flash_hit, flash_block, combo, no_chao, rect (Rect midbottom=(x,y)), ultimo_dano, eventos (list), novos_projeteis (list), rastro`.
  - `reset()` (início de round), `update(held, pressed, oponente, pode_agir)`; `held` = dict ação→bool (`esquerda,direita,defesa,pulo,basico,forte,especial`), `pressed` = lista de ações apertadas neste frame (KEYDOWN). Buffer de input `C.BUFFER_INPUT`. Ataques só em `idle/walking/jumping`; defender só no chão e impede atacar; derrotado/hurt/victory não agem; ataque exige cooldown 0; especial exige `energia>=custo` e `cooldown_especial==0`; regen passiva de energia; limite da arena; gravidade/chão; vira para o oponente quando livre no chão.
  - `eventos` recebe tuplas: `("pulo",) ("pouso",) ("ataque", nome) ("erro_energia",) ("projetil",)`. Match consome e limpa. No frame em que o especial fica ativo, cria `Projectile` em `novos_projeteis` (+ evento `("projetil",)`).
  - `pode_ser_atingido()`; `receber_golpe(spec, x_atacante) -> "hit"|"block"` (bloqueio só se `state=="defending"` e atacante à frente; dano = `round(dano*bloqueio)` mín. 1 se bloqueado; hit: cancela ataque, `hurt`, hitstun = `max(8, spec.hitstun - REDUCAO_COMBO*combo)`, `combo+=1`, knockback para longe do atacante, lançamento (`vy=-spec.lancamento`), `flash_hit`; `hp<=0` → `defeated`); grava `ultimo_dano`. Combo zera quando sai do hurt; `invuln=INVULNERAVEL_APOS_HIT` ao sair.
  - `ponto_mao_especial() -> (x, y)`; `ambiente(efeitos)` (brasas p/ Blaze, neve p/ Frost, baixa frequência).
  - `draw(surf, mostrar_hitbox=False)`: lutador geométrico (tronco, membros, cabeça). Blaze: chamas no cabelo animadas, faixa, traje vermelho/laranja. Frost: cabelo de cristais, cachecol ondulante, traje azul/branco. Poses por estado (soco = braço, forte = chute com rastro/swoosh, especial = orb de carga crescente com glow, defesa = braços cruzados + bolha de escudo, hurt = inclinado/branco piscando, defeated = deitado, victory = braços para cima e pulinhos). Sombra no chão, indicador triangular colorido sobre a cabeça.

### match.py (depende de: config, effects, audio, arena, fighter)
- `class Match(audio, fonte_dano)`: atributos lidos pela UI: `f1, f2, vitorias[2], round, timer (frames), fase ("intro"|"fight"|"ko"|"fim"), fase_t, combo_info (None|dict(lado,n,t)), msg_round (str), vencedor_round (0/1/2), terminou (bool), vencedor (1|2|None), efeitos, arena, projeteis, hitstop`.
- `update(held1, pressed1, held2, pressed2)`: fases intro (ROUND n → FIGHT!, ninguém age até "fight"), luta (timer, hits melee e projéteis, colisão entre lutadores, projéteis anulam-se), KO (câmera lenta nos primeiros frames, vencedor em `victory`, ponto concedido ao entrar), próximo round ou `terminou=True` (melhor de 3). Tempo esgotado → maior HP vence; empate → round repetido sem ponto. Hitstop, tremor, flash, partículas, anéis, textos de dano, "N HITS!", sons.
- `draw(surf)` desenha arena, sombras/lutadores, projéteis, efeitos (sem HUD) no canvas; `offset` do tremor é aplicado pelo `Game`.

### ui.py (depende de: config)
- `class Fontes`: `mini, pequena, media, grande, titulo` (`pygame.font.SysFont("impact,arialblack,verdana,arial", n)`).
- `texto(fonte, txt, cor, contorno=None) -> Surface` (cache) e `desenhar_texto(surf, fonte, txt, cor, pos, ancora="center", contorno=(0,0,0))`.
- `class Menu(itens)`: `sel`, `mover(d)`, `draw(surf, cx, y, t, fontes)`, `item_em(pos) -> idx|None`; botões neon com seleção destacada.
- `desenhar_hud(surf, match, fontes, t)`: barras de vida (com rastro de dano), nomes, P1/P2, energia (marca do custo + "ESPECIAL!" pulsando), timer central, pips de rounds `P1 ● ○ / P2 ○ ●`, combo.
- `desenhar_textos_centrais(surf, match, fontes)`: "ROUND N", "FIGHT!", "K.O.!", "TEMPO!", "EMPATE", com zoom de entrada.

### game.py + main.py (depende de: todos)
- `class Game`: `run()`; estados `MENU, CONTROLES, LUTA, PAUSA, RESULTADO`. Janela `pygame.SCALED|RESIZABLE` (com fallback). Entrada: `pygame.key.get_pressed()` p/ segurado e KEYDOWN p/ `pressed`, mapeados por `C.CONTROLES`. Menu: JOGAR/CONTROLES/SAIR (setas ou W/S + ENTER, mouse). CONTROLES mostra teclas dos 2 jogadores (lidas de `C.CONTROLES`) + gerais. ESC pausa (PAUSADO: CONTINUAR / VOLTAR AO MENU). RESULTADO: "PLAYER N WINS!", placar final, `R` jogar de novo, `ESC`/Enter menu. F1 alterna hitboxes. `main.py`: `from pixelclash.game import Game; Game().run()`.

## Testes
`python tests/smoke_test.py` (headless: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`) simula uma partida completa.
