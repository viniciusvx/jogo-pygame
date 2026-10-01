"""Constantes do jogo. Mexa aqui para balancear, trocar teclas ou personagens."""
import pygame

# --- Tela -------------------------------------------------------------------
TITULO = "PIXEL CLASH"
LARGURA = 960
ALTURA = 540
FPS = 60                      # toda a logica usa "frames" (60 = 1 segundo)

# --- Fisica -----------------------------------------------------------------
GRAVIDADE = 0.85
VELOCIDADE = 5.0              # velocidade horizontal base (px/frame)
FORCA_PULO = 16.5
CHAO_Y = 455                  # y dos pes dos lutadores
MARGEM_ARENA = 24             # distancia minima entre o lutador e a borda
LARGURA_LUTADOR = 56
ALTURA_LUTADOR = 120

# --- Regras -----------------------------------------------------------------
VIDA_MAXIMA = 100
ENERGIA_MAXIMA = 100
ENERGIA_INICIAL = 20
ENERGIA_POR_SEGUNDO = 3.0     # recarga passiva
ROUNDS_PARA_VENCER = 2        # melhor de 3
TEMPO_ROUND = 60              # segundos
INVULNERAVEL_APOS_HIT = 10    # frames de protecao ao se recuperar de um golpe
REDUCAO_COMBO = 3             # cada golpe seguido encurta o "hitstun" (evita combo infinito)
BUFFER_INPUT = 8              # frames em que um comando antecipado e lembrado

# --- Dano dos ataques -------------------------------------------------------
DANO_DOS_ATAQUES = {"basico": 6, "forte": 14, "especial": 25}

# --- Ataques ------------------------------------------------------------------
# startup/ativo/recuperacao: duracao (frames) de cada fase do golpe.
# cooldown: espera extra antes de poder atacar de novo.
# bloqueio: fracao do dano que passa quando o alvo esta defendendo.
# base/altura: posicao vertical da area de acerto (em relacao aos pes).
ATAQUES = {
    "basico": dict(
        dano=DANO_DOS_ATAQUES["basico"], alcance=52, altura=34, base=70,
        startup=4, ativo=4, recuperacao=9, cooldown=0,
        knockback=5, hitstun=22, energia=6, tremor=0, hitstop=2,
        bloqueio=0.25, lancamento=0, avanco=3.0,
    ),
    "forte": dict(
        dano=DANO_DOS_ATAQUES["forte"], alcance=80, altura=50, base=28,
        startup=13, ativo=6, recuperacao=22, cooldown=6,
        knockback=11, hitstun=26, energia=10, tremor=6, hitstop=5,
        bloqueio=0.30, lancamento=7, avanco=4.0,
    ),
    "especial": dict(
        dano=DANO_DOS_ATAQUES["especial"], projetil=True, custo=50,
        startup=16, ativo=1, recuperacao=22, cooldown=75,
        knockback=14, hitstun=32, energia=8, tremor=12, hitstop=9,
        bloqueio=0.50, lancamento=10, avanco=0,
    ),
}

# --- Personagens ------------------------------------------------------------
PERSONAGENS = {
    "blaze": dict(
        nome="Blaze", cor=(235, 70, 40), cor_clara=(255, 205, 70),
        cor_escura=(70, 18, 20), pele=(232, 170, 125),
        velocidade=1.10,          # multiplicador da VELOCIDADE
        alcance_bonus=0,          # somado ao alcance dos golpes corpo a corpo
        proj_velocidade=12, proj_raio=20,
    ),
    "frost": dict(
        nome="Frost", cor=(60, 150, 235), cor_clara=(200, 245, 255),
        cor_escura=(18, 36, 92), pele=(215, 232, 245),
        velocidade=0.95,
        alcance_bonus=10,
        proj_velocidade=8, proj_raio=27,
    ),
}

# --- Teclas (troque aqui) ---------------------------------------------------
CONTROLES = {
    1: {
        "esquerda": pygame.K_a, "direita": pygame.K_d, "pulo": pygame.K_w,
        "defesa": pygame.K_s,
        "basico": pygame.K_f, "forte": pygame.K_g, "especial": pygame.K_h,
    },
    2: {
        "esquerda": pygame.K_LEFT, "direita": pygame.K_RIGHT, "pulo": pygame.K_UP,
        "defesa": pygame.K_DOWN,
        "basico": pygame.K_j, "forte": pygame.K_k, "especial": pygame.K_l,
    },
}

# --- Efeitos ----------------------------------------------------------------
MAX_PARTICULAS = 350
MOSTRAR_HITBOXES = False      # F1 liga/desliga durante o jogo (util para ajustar golpes)
