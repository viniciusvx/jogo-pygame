# PIXEL CLASH

Jogo de luta 2D local para 2 jogadores, feito com Python e Pygame. Sem imagens externas: tudo (lutadores, cenario, efeitos e sons) e gerado por codigo.

## Como instalar e rodar no Windows

1. Instale o Python 3.9 ou mais novo em <https://www.python.org/downloads/> (marque **Add python.exe to PATH** no instalador).
2. Abra o Prompt de Comando (ou PowerShell) na pasta do jogo.
3. Instale as dependencias:

   ```
   py -m pip install -r requirements.txt
   ```

4. Rode o jogo:

   ```
   py main.py
   ```

A janela pode ser redimensionada; o jogo mantem a proporcao. Para testar sem abrir janela (util para conferir se esta tudo certo):

```
set SDL_VIDEODRIVER=dummy
set SDL_AUDIODRIVER=dummy
py tests/smoke_test.py
```

## Controles

| Acao              | Player 1 (Blaze) | Player 2 (Frost) |
|-------------------|------------------|------------------|
| Esquerda / Direita| A / D            | Setas esq. / dir.|
| Pular             | W                | Seta cima        |
| Defender          | S                | Seta baixo       |
| Soco (rapido)     | F                | J                |
| Chute forte       | G                | K                |
| Especial          | H                | L                |

Gerais: `ESC` pausa, `F1` mostra hitboxes, `R` joga de novo na tela de resultado. Nos menus use setas (ou W/S) e ENTER, ou o mouse.

Regras: melhor de 3 rounds, 60 segundos por round. O especial gasta 50 de energia (a barra recarrega sozinha e ao acertar golpes). Defender (no chao) reduz o dano, mas voce nao ataca enquanto defende. Se o tempo acabar, vence quem tiver mais vida.

## Como mudar teclas e balanceamento

Tudo fica em `pixelclash/config.py`:

- **Teclas**: dicionario `CONTROLES` (por exemplo, troque `pygame.K_f` por `pygame.K_z`). A tela CONTROLES do jogo le esse dicionario, entao ja mostra as teclas novas.
- **Dano**: `DANO_DOS_ATAQUES` e o campo `dano` de cada golpe em `ATAQUES`.
- **Velocidade dos golpes**: `startup`, `ativo`, `recuperacao` e `cooldown` (em frames; 60 = 1 segundo).
- **Alcance, empurrao e atordoamento**: `alcance`, `knockback`, `hitstun`, `lancamento`.
- **Especial**: `custo`, `cooldown` e `bloqueio` em `ATAQUES["especial"]`.
- **Personagens**: `PERSONAGENS` (cores, `velocidade`, `alcance_bonus`, velocidade e tamanho do projetil).
- **Partida**: `VIDA_MAXIMA`, `TEMPO_ROUND`, `ROUNDS_PARA_VENCER`, `ENERGIA_POR_SEGUNDO`, `GRAVIDADE`, `FORCA_PULO`.

## Estrutura do codigo

```
main.py                 ponto de entrada
pixelclash/
  config.py             todas as constantes (teclas, balanceamento)
  game.py               loop principal, estados (menu, controles, luta, pausa, resultado) e entrada
  ui.py                 fontes, textos, menus neon, HUD e textos centrais (ROUND, FIGHT!, K.O.!)
  match.py              regras da partida: rounds, timer, acertos, KO, hitstop
  fighter.py            lutadores (Blaze e Frost), golpes e projeteis
  arena.py              cenario neon animado
  effects.py            particulas, aneis, textos de dano, tremor e flash
  audio.py              sons gerados por codigo (ou arquivos de assets/sons)
assets/sons/            sons opcionais
tests/smoke_test.py     teste de fumaca headless (partida completa)
```

Toda a logica roda em frames (60 FPS fixo), sem dt.

## Dica: trocar os sons

Os sons sao sintetizados automaticamente, mas voce pode usar os seus: coloque um arquivo `.wav` ou `.ogg` em `assets/sons/` com o nome do som e ele substitui o gerado. Nomes aceitos:

`soco, golpe_forte, bloqueio, whoosh, especial_carga, especial_disparo, impacto_especial, pulo, pouso, ko, selecionar, confirmar, round, fight, vitoria, erro`

Exemplo: `assets/sons/soco.wav`. Sem placa de som, o jogo roda em silencio.
