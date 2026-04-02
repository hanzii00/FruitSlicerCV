# ============================================================
#  fruit.py  –  Fruit & Bomb classes with physics + rendering
#  Fruits now load images from the assets/ folder automatically.
#  Drop any PNG in assets/ and it becomes a fruit — no code changes needed.
# ============================================================

import pygame
import math
import random
import os
import glob

from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    GRAVITY, FRUIT_RADIUS, BOMB_RADIUS,
    BOMB_COLOR, BOMB_SPARK,
    PARTICLE_COUNT, PARTICLE_LIFETIME,
    PARTICLE_SPEED_MAX, PARTICLE_GRAVITY,
)

# ── Asset loading ─────────────────────────────────────────────

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

def _load_fruit_images(radius: int) -> dict[str, pygame.Surface]:
    """
    Scan assets/ for *.png files and return a dict of
    { fruit_name: scaled_surface }.  Falls back to a coloured
    circle if no images are found so the game never crashes.
    """
    size = int(radius * 4.0)  # larger so fruits are easy to see and hit
    images: dict[str, pygame.Surface] = {}

    patterns = glob.glob(os.path.join(_ASSETS_DIR, "*.png"))
    for path in patterns:
        name = os.path.splitext(os.path.basename(path))[0].lower()
        try:
            raw = pygame.image.load(path).convert_alpha()
            scaled = pygame.transform.smoothscale(raw, (size, size))
            # Darken by multiplying RGB channels — alpha untouched
            dark = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
            dark.fill((0, 0, 0, 0))
            scaled.set_alpha(None)
            darkened = scaled.copy()
            darkened.fill((160, 160, 160, 255), special_flags=pygame.BLEND_RGBA_MULT)
            images[name] = darkened
        except Exception as e:
            print(f"[fruit.py] Could not load {path}: {e}")

    if not images:
        # Fallback: one generic coloured circle so the game still works
        print("[fruit.py] No fruit images found in assets/ — using fallback circle.")
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(surf, (220, 80, 80), (radius, radius), radius)
        images["fruit"] = surf

    return images

# Populated once on first Fruit instantiation (after pygame.init)
_FRUIT_IMAGES: dict[str, pygame.Surface] = {}
_FRUIT_NAMES:  list[str]                 = []

def _ensure_images_loaded():
    global _FRUIT_IMAGES, _FRUIT_NAMES
    if not _FRUIT_IMAGES:
        _FRUIT_IMAGES = _load_fruit_images(FRUIT_RADIUS)
        _FRUIT_NAMES  = list(_FRUIT_IMAGES.keys())
        print(f"[fruit.py] Loaded fruits: {_FRUIT_NAMES}")


# ── Helpers ──────────────────────────────────────────────────

def _rand_spawn_velocity():
    vx = random.uniform(-3.5, 3.5)
    vy = random.uniform(-14, -10)
    return vx, vy


def _rand_spawn_x():
    margin = FRUIT_RADIUS + 20
    return random.randint(margin, SCREEN_WIDTH - margin)


# ── Particle ─────────────────────────────────────────────────

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "radius")

    def __init__(self, x: float, y: float, color: tuple):
        angle     = random.uniform(0, math.tau)
        speed     = random.uniform(1.5, PARTICLE_SPEED_MAX)
        self.x        = x
        self.y        = y
        self.vx       = math.cos(angle) * speed
        self.vy       = math.sin(angle) * speed - random.uniform(1, 3)
        self.life     = PARTICLE_LIFETIME + random.randint(-8, 8)
        self.max_life = self.life
        self.color    = color
        self.radius   = random.randint(3, 7)

    def update(self):
        self.vy  += PARTICLE_GRAVITY
        self.x   += self.vx
        self.y   += self.vy
        self.life -= 1
        self.vx  *= 0.98

    @property
    def alive(self) -> bool:
        return self.life > 0

    def draw(self, surface: pygame.Surface):
        r, g, b = self.color
        factor  = self.life / self.max_life
        col = (int(r * factor), int(g * factor), int(b * factor))
        pygame.draw.circle(surface, col, (int(self.x), int(self.y)), self.radius)


# ── Base projectile ──────────────────────────────────────────

class _Projectile:
    def __init__(self, x, y, vx, vy, radius):
        self.x      = float(x)
        self.y      = float(y)
        self.vx     = vx
        self.vy     = vy
        self.radius = radius
        self.sliced = False
        self.alive  = True
        self._angle = random.uniform(0, 360)
        self._spin  = random.uniform(-3, 3)

    def update(self):
        if not self.alive:
            return
        self.vy    += GRAVITY
        self.x     += self.vx
        self.y     += self.vy
        self._angle = (self._angle + self._spin) % 360
        if self.y > SCREEN_HEIGHT + self.radius * 2:
            self.alive = False

    @property
    def center(self):
        return int(self.x), int(self.y)


# ── Fruit ────────────────────────────────────────────────────

class Fruit(_Projectile):
    def __init__(self):
        _ensure_images_loaded()

        x  = _rand_spawn_x()
        y  = SCREEN_HEIGHT + FRUIT_RADIUS + 10
        vx, vy = _rand_spawn_velocity()
        super().__init__(x, y, vx, vy, FRUIT_RADIUS)

        self.kind = random.choice(_FRUIT_NAMES)
        self._img = _FRUIT_IMAGES[self.kind]          # original (un-rotated)

        # Slice state
        self._slice_timer = 0
        self._left_half   = None
        self._right_half  = None

    # ── Rendering ─────────────────────────────────────────────

    def _draw_whole(self, surface: pygame.Surface):
        cx, cy = self.center

        # Rotate the image according to spin angle
        rotated = pygame.transform.rotate(self._img, -self._angle)
        rect    = rotated.get_rect(center=(cx, cy))

        # Soft drop shadow
        shadow = pygame.Surface(rotated.get_size(), pygame.SRCALPHA)
        shadow.blit(rotated, (0, 0))
        shadow.set_alpha(60)
        surface.blit(shadow, rect.move(4, 4))

        surface.blit(rotated, rect)

    def _make_halves_if_needed(self):
        """Slice the image in half (left / right) on first call."""
        if self._left_half is not None:
            return
        img  = self._img
        w, h = img.get_size()
        mid  = w // 2

        # Left half: only blit the left portion onto a transparent same-size surface
        left = pygame.Surface((w, h), pygame.SRCALPHA)
        left.blit(img, (0, 0), area=pygame.Rect(0, 0, mid, h))
        pygame.draw.line(left, (220, 220, 220), (mid - 1, 0), (mid - 1, h), 2)

        # Right half: blit only the right portion, offset so it sits on the right side
        right = pygame.Surface((w, h), pygame.SRCALPHA)
        right.blit(img, (mid, 0), area=pygame.Rect(mid, 0, w - mid, h))
        pygame.draw.line(right, (220, 220, 220), (mid, 0), (mid, h), 2)

        self._left_half  = left
        self._right_half = right

    def _draw_sliced(self, surface: pygame.Surface):
        self._make_halves_if_needed()
        self._slice_timer += 1
        t = self._slice_timer

        spread = t * 2
        drop   = int(0.5 * GRAVITY * t * t)
        alpha  = max(0, 255 - t * 8)

        for half, dx in ((self._left_half, -spread), (self._right_half, spread)):
            rotated = pygame.transform.rotate(half, -self._angle - t * 3)
            rotated.set_alpha(alpha)
            rect = rotated.get_rect(center=(int(self.x) + dx, int(self.y) + drop))
            surface.blit(rotated, rect)

        if alpha == 0:
            self.alive = False

    def draw(self, surface: pygame.Surface):
        if not self.alive:
            return
        if self.sliced:
            self._draw_sliced(surface)
        else:
            self._draw_whole(surface)

    # ── Slice ─────────────────────────────────────────────────

    def slice(self) -> list["Particle"]:
        self.sliced = True
        # Sample particle colour from the image
        w, h    = self._img.get_size()
        sample  = self._img.get_at((w // 2, h // 2))[:3]
        lighter = tuple(min(255, c + 60) for c in sample)
        return [
            Particle(self.x, self.y, random.choice([sample, lighter]))
            for _ in range(PARTICLE_COUNT)
        ]

    def missed(self) -> bool:
        return not self.sliced and not self.alive


# ── Bomb ─────────────────────────────────────────────────────

class Bomb(_Projectile):
    def __init__(self):
        x  = _rand_spawn_x()
        y  = SCREEN_HEIGHT + BOMB_RADIUS + 10
        vx, vy = _rand_spawn_velocity()
        super().__init__(x, y, vx, vy, BOMB_RADIUS)
        self._fuse_frame = 0

    def draw(self, surface: pygame.Surface):
        if not self.alive:
            return
        self._fuse_frame += 1
        cx, cy = self.center
        r      = self.radius

        pygame.draw.circle(surface, (5, 5, 15),   (cx + 4, cy + 4), r)
        pygame.draw.circle(surface, BOMB_COLOR,   (cx, cy), r)
        pygame.draw.circle(surface, (80, 80, 80), (cx, cy), r, 2)
        pygame.draw.circle(surface, (100, 100, 100),
                           (cx - r // 4, cy - r // 3), r // 4)

        fuse_len   = 14
        fuse_end_x = cx + 6
        fuse_end_y = cy - r
        fuse_tip_x = fuse_end_x + int(3 * math.sin(self._fuse_frame * 0.4))
        fuse_tip_y = fuse_end_y - fuse_len

        pygame.draw.line(surface, (160, 120, 60),
                         (fuse_end_x, fuse_end_y),
                         (fuse_tip_x, fuse_tip_y), 3)

        if (self._fuse_frame // 4) % 2 == 0:
            pygame.draw.circle(surface, BOMB_SPARK,       (fuse_tip_x, fuse_tip_y), 5)
            pygame.draw.circle(surface, (255, 255, 200), (fuse_tip_x, fuse_tip_y), 3)

        font  = pygame.font.SysFont("Arial", 13, bold=True)
        label = font.render("!", True, (255, 60, 60))
        surface.blit(label, label.get_rect(center=(cx, cy)))

    def slice(self) -> list[Particle]:
        self.sliced = True
        return [
            Particle(self.x, self.y, random.choice([BOMB_SPARK, (255, 255, 200)]))
            for _ in range(PARTICLE_COUNT)
        ]

    def missed(self) -> bool:
        return False


# ── Factory ───────────────────────────────────────────────────

def spawn_object(bomb_chance: float = 0.18):
    if random.random() < bomb_chance:
        return Bomb()
    return Fruit()