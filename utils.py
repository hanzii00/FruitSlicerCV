# ============================================================
#  utils.py  –  Coordinate mapping, drawing helpers, collision
# ============================================================

import pygame
import math
from settings import (
    CAM_WIDTH, CAM_HEIGHT,
    SCREEN_WIDTH, SCREEN_HEIGHT,
    BLADE_COLOR, BLADE_GLOW, BLADE_TRAIL_LENGTH,
    BLADE_MIN_SPEED, BLADE_RADIUS,
)


# ── Coordinate mapping ───────────────────────────────────────

def cam_to_screen(cam_x: int, cam_y: int,
                  margin_x: float = 0.05,
                  margin_y: float = 0.05) -> tuple[int, int]:
    """
    Map a webcam pixel coordinate to a Pygame screen coordinate.
    A small margin is removed from the edges of the cam frame so
    that the finger doesn't have to go to the very edge of the
    camera view to reach the screen edges.

    Args:
        cam_x, cam_y  : raw pixel from MediaPipe (in camera space)
        margin_x/y    : fraction of cam frame to ignore at each edge
    Returns:
        (screen_x, screen_y) clamped to [0, SCREEN_WIDTH/HEIGHT]
    """
    x_min = CAM_WIDTH  * margin_x
    x_max = CAM_WIDTH  * (1 - margin_x)
    y_min = CAM_HEIGHT * margin_y
    y_max = CAM_HEIGHT * (1 - margin_y)

    # Normalise [0, 1] within the trimmed window
    nx = (cam_x - x_min) / (x_max - x_min)
    ny = (cam_y - y_min) / (y_max - y_min)

    # Clamp and scale to screen
    sx = int(max(0.0, min(1.0, nx)) * SCREEN_WIDTH)
    sy = int(max(0.0, min(1.0, ny)) * SCREEN_HEIGHT)
    return sx, sy


# ── Blade trail ──────────────────────────────────────────────

class BladeTrail:
    """
    Stores recent finger-tip positions and draws a glowing sword
    trail effect.  Also computes instantaneous speed for slice detection.
    """

    def __init__(self):
        self._points: list[tuple[int, int]] = []
        self.speed = 0.0   # pixels/frame since last update

    def push(self, pos: tuple[int, int] | None):
        """Add a new tip position.  Pass None when hand not detected."""
        if pos is None:
            # Fade trail when hand leaves
            if self._points:
                self._points.pop(0)
            self.speed = 0.0
            return

        if self._points:
            dx = pos[0] - self._points[-1][0]
            dy = pos[1] - self._points[-1][1]
            self.speed = math.hypot(dx, dy)
        else:
            self.speed = 0.0

        self._points.append(pos)
        if len(self._points) > BLADE_TRAIL_LENGTH:
            self._points.pop(0)

    @property
    def tip(self) -> tuple[int, int] | None:
        """Current (most recent) finger-tip screen position."""
        return self._points[-1] if self._points else None

    @property
    def is_slicing(self) -> bool:
        """True when the finger is moving fast enough to slice."""
        return self.speed >= BLADE_MIN_SPEED

    def draw(self, surface: pygame.Surface):
        """Render the glowing trail from oldest → newest point."""
        n = len(self._points)
        if n < 2:
            return

        for i in range(1, n):
            t      = i / n                     # 0 → 1 along trail
            alpha  = int(t * 230)              # fade older segments
            width  = max(1, int(t * 6))

            # Core white line
            r, g, b = BLADE_COLOR
            col = (
                int(r * t),
                int(g * t),
                int(b * t),
            )
            pygame.draw.line(surface, col,
                             self._points[i - 1], self._points[i], width)

        # Glowing tip circle
        if self.tip:
            # Outer glow
            for glow_r, glow_alpha in [(14, 60), (9, 120), (5, 200)]:
                glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, (*BLADE_GLOW, glow_alpha),
                                   (glow_r, glow_r), glow_r)
                surface.blit(glow_surf,
                             (self.tip[0] - glow_r, self.tip[1] - glow_r),
                             special_flags=pygame.BLEND_RGBA_ADD)
            # Solid white dot
            pygame.draw.circle(surface, (255, 255, 255), self.tip, 4)

    def clear(self):
        self._points.clear()
        self.speed = 0.0


# ── Gradient background ──────────────────────────────────────

def draw_gradient_bg(surface: pygame.Surface,
                     top_col: tuple, bottom_col: tuple):
    """Draw a vertical gradient background."""
    h = surface.get_height()
    w = surface.get_width()
    for y in range(h):
        t = y / h
        r = int(top_col[0] + (bottom_col[0] - top_col[0]) * t)
        g = int(top_col[1] + (bottom_col[1] - top_col[1]) * t)
        b = int(top_col[2] + (bottom_col[2] - top_col[2]) * t)
        pygame.draw.line(surface, (r, g, b), (0, y), (w, y))


# ── Text helpers ─────────────────────────────────────────────

def draw_text_centered(surface: pygame.Surface, text: str,
                        font: pygame.font.Font, color: tuple,
                        cx: int, cy: int,
                        shadow: bool = True):
    """Render text centred at (cx, cy) with optional drop-shadow."""
    if shadow:
        sh_surf = font.render(text, True, (0, 0, 0))
        sh_rect = sh_surf.get_rect(center=(cx + 3, cy + 3))
        surface.blit(sh_surf, sh_rect)
    surf = font.render(text, True, color)
    rect = surf.get_rect(center=(cx, cy))
    surface.blit(surf, rect)


def draw_lives(surface: pygame.Surface, lives: int,
               font: pygame.font.Font, color: tuple,
               x: int, y: int):
    """Render heart icons for remaining lives."""
    heart = "♥"
    spacing = 36
    for i in range(lives):
        draw_text_centered(surface, heart, font, color,
                           x + i * spacing, y, shadow=True)


# ── Collision ────────────────────────────────────────────────

def point_in_circle(px: int, py: int,
                    cx: float, cy: float, r: float) -> bool:
    dx = px - cx
    dy = py - cy
    return dx * dx + dy * dy <= r * r


def segment_circle_intersect(p1: tuple, p2: tuple,
                              cx: float, cy: float, r: float) -> bool:
    """
    Returns True if the line segment p1→p2 passes through
    a circle centred at (cx, cy) with radius r.
    Used for more robust slice detection with fast finger movement.
    """
    ax, ay = p1
    bx, by = p2
    dx, dy = bx - ax, by - ay
    fx, fy = ax - cx, ay - cy

    a = dx * dx + dy * dy
    if a == 0:
        return point_in_circle(ax, ay, cx, cy, r)

    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return False
    discriminant = math.sqrt(discriminant)
    t1 = (-b - discriminant) / (2 * a)
    t2 = (-b + discriminant) / (2 * a)
    return (0 <= t1 <= 1) or (0 <= t2 <= 1)