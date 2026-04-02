# ============================================================
#  settings.py  –  Global constants for Fruit Ninja CV
# ============================================================

# ── Window ──────────────────────────────────────────────────
SCREEN_WIDTH  = 1280
SCREEN_HEIGHT = 720
FPS           = 60
TITLE         = "Fruit Ninja CV"

# ── Camera ──────────────────────────────────────────────────
CAM_INDEX     = 0          # 0 = default webcam
CAM_WIDTH     = 640
CAM_HEIGHT    = 480
FLIP_CAM      = True       # Mirror so movement feels natural

# ── Hand tracking ───────────────────────────────────────────
MAX_HANDS             = 1
DETECTION_CONFIDENCE  = 0.7
TRACKING_CONFIDENCE   = 0.6
FINGER_TIP_ID         = 8  # MediaPipe landmark index for index-finger tip
THUMB_TIP_ID          = 4
PINKY_TIP_ID          = 20
INDEX_MCP_ID          = 5
PINKY_MCP_ID          = 17
WRIST_ID              = 0

# ── Blade / slicing ─────────────────────────────────────────
BLADE_TRAIL_LENGTH    = 18   # Number of trail points to keep
BLADE_MIN_SPEED       = 8    # px/frame – minimum speed to count as a slice
BLADE_RADIUS          = 28   # Collision radius around finger tip (px)

# ── Fruit physics ───────────────────────────────────────────
GRAVITY               = 0.25   # pixels / frame²  (applied to vy each frame)
FRUIT_SPAWN_INTERVAL  = 90     # frames between spawns (decreases with score)
MIN_SPAWN_INTERVAL    = 35
FRUIT_RADIUS          = 42     # Base hitbox radius (px)
MAX_FRUITS_ALIVE      = 12
FRUIT_MISS_PENALTY    = 1      # Lives lost when a fruit falls off-screen
STARTING_LIVES        = 3

# ── Bomb ────────────────────────────────────────────────────
BOMB_CHANCE           = 0.18   # Probability that a new spawn is a bomb
BOMB_RADIUS           = 38

# ── Particle effects ────────────────────────────────────────
PARTICLE_COUNT        = 22     # Juice particles per slice
PARTICLE_LIFETIME     = 35     # Frames a particle lives
PARTICLE_SPEED_MAX    = 7.0
PARTICLE_GRAVITY      = 0.18

# ── Score ────────────────────────────────────────────────────
SCORE_PER_FRUIT       = 1
SCORE_COMBO_BONUS     = 2      # Extra points when slicing multiple at once
COMBO_WINDOW          = 12     # Frames within which slices count as a combo

# ── Colours (R, G, B) ───────────────────────────────────────
BG_TOP          = (10,  14,  30)
BG_BOTTOM       = (20,  30,  60)
BLADE_COLOR     = (255, 255, 255)
BLADE_GLOW      = (150, 220, 255)
UI_COLOR        = (255, 255, 255)
SCORE_COLOR     = (255, 220,  80)
LIFE_COLOR      = (255,  70,  70)
BOMB_COLOR      = (50,   50,  50)
BOMB_SPARK      = (255, 140,   0)

# Fruit colour palette  { name: (fill, highlight) }
FRUIT_COLORS = {
    "watermelon": ((220,  60,  80), (100, 180,  60)),
    "orange":     ((255, 140,   0), (255, 200,  60)),
    "apple":      ((220,  40,  40), (240, 180,  40)),
    "kiwi":       (( 80, 160,  60), (200, 220, 100)),
    "lemon":      ((255, 230,  50), (255, 255, 160)),
    "grape":      ((130,  60, 180), (200, 140, 240)),
    "strawberry": ((220,  50,  70), (255, 180, 100)),
    "mango":      ((255, 170,  30), (255, 220, 100)),
}
FRUIT_NAMES = list(FRUIT_COLORS.keys())