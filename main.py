import sys
import os
import math
import random
import time

# Hide Pygame window - game only appears in camera feed
os.environ['SDL_VIDEODRIVER'] = 'dummy'

import pygame

from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE,
    STARTING_LIVES, FRUIT_MISS_PENALTY,
    FRUIT_SPAWN_INTERVAL, MIN_SPAWN_INTERVAL,
    MAX_FRUITS_ALIVE, BOMB_CHANCE,
    SCORE_PER_FRUIT, SCORE_COMBO_BONUS, COMBO_WINDOW,
    BG_TOP, BG_BOTTOM, UI_COLOR, SCORE_COLOR, LIFE_COLOR,
)
from hand_tracker import HandTracker
from fruit import Fruit, Bomb, spawn_object, Particle
from utils import (
    cam_to_screen, BladeTrail,
    draw_gradient_bg, draw_text_centered, draw_lives,
    segment_circle_intersect,
)


# ════════════════════════════════════════════════════════════
#  Game states
# ════════════════════════════════════════════════════════════

STATE_START    = "start"
STATE_PLAYING  = "playing"
STATE_GAMEOVER = "gameover"


# ════════════════════════════════════════════════════════════
#  Floating score text ("+1", "+COMBO" etc.)
# ════════════════════════════════════════════════════════════

class FloatingText:
    def __init__(self, text: str, x: int, y: int,
                 color=(255, 220, 80), size=32, lifetime=55):
        self.text     = text
        self.x        = float(x)
        self.y        = float(y)
        self.color    = color
        self.size     = size
        self.lifetime = lifetime
        self.max_life = lifetime
        self.vy       = -1.8

    def update(self):
        self.y       += self.vy
        self.lifetime -= 1
        self.vy      *= 0.97

    @property
    def alive(self) -> bool:
        return self.lifetime > 0

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        alpha  = int(255 * (self.lifetime / self.max_life))
        surf   = font.render(self.text, True, self.color)
        surf.set_alpha(alpha)
        rect   = surf.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(surf, rect)


# ════════════════════════════════════════════════════════════
#  Game
# ════════════════════════════════════════════════════════════

class Game:
    """Main game controller."""

    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)

        # Create hidden display (no visible window; game overlays on camera)
        self.screen = pygame.display.set_mode(
            (SCREEN_WIDTH, SCREEN_HEIGHT)
        )
        self.clock  = pygame.time.Clock()

        # Pre-render gradient background once on a surface
        self._bg = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        draw_gradient_bg(self._bg, BG_TOP, BG_BOTTOM)

        # Fonts
        self._font_xl  = pygame.font.SysFont("Arial", 80,  bold=True)
        self._font_lg  = pygame.font.SysFont("Arial", 48,  bold=True)
        self._font_md  = pygame.font.SysFont("Arial", 34,  bold=True)
        self._font_sm  = pygame.font.SysFont("Arial", 24,  bold=False)
        self._font_hud = pygame.font.SysFont("Arial", 36,  bold=True)

        # Subsystems
        self._tracker   = HandTracker()
        self._blade     = BladeTrail()
        self._show_debug = False

        # Game data (reset in new_game)
        self._state         = STATE_START
        self._score         = 0
        self._lives         = STARTING_LIVES
        self._high_score    = 0
        self._fruits: list  = []
        self._particles: list[Particle] = []
        self._floaters: list[FloatingText] = []
        self._spawn_timer   = 0
        self._spawn_interval = FRUIT_SPAWN_INTERVAL
        self._frame         = 0
        
        # Gesture tracking
        self._gesture_name  = "UNKNOWN"
        self._finger_count  = 0

        # Combo tracking
        self._combo_slices  = 0
        self._combo_timer   = 0

        # Palm gesture debounce
        self._palm_cooldown = 0

        # Flash overlay for bomb hit
        self._flash_alpha   = 0

    # ── Game reset ───────────────────────────────────────────

    def new_game(self):
        self._score          = 0
        self._lives          = STARTING_LIVES
        self._fruits         = []
        self._particles      = []
        self._floaters       = []
        self._spawn_timer    = 0
        self._spawn_interval = FRUIT_SPAWN_INTERVAL
        self._frame          = 0
        self._combo_slices   = 0
        self._combo_timer    = 0
        self._flash_alpha    = 0
        self._blade.clear()
        self._state          = STATE_PLAYING

    # ── Main loop ─────────────────────────────────────────────

    def run(self):
        while True:
            self._handle_events()
            self._update()
            self._draw()
            self.clock.tick(FPS)

    # ── Events ───────────────────────────────────────────────

    def _handle_events(self):
        # No pygame events since window is hidden; keyboard input comes from OpenCV
        pass
    
    def _handle_keyboard(self, key: int):
        """Handle keyboard input from OpenCV window."""
        if key == -1 or key == 255:  # No key pressed
            return
        
        # Convert key code to character
        try:
            ch = chr(key).lower()
        except:
            return
        
        if ch == 'q':
            self._quit()
        elif ch == 'r':
            self.new_game()
        elif ch == 'd':
            self._show_debug = not self._show_debug
        elif ch == 'f':
            # Fullscreen toggle (for reference, but dummy driver doesn't support it)
            pass

    def _quit(self):
        self._tracker.release()
        pygame.quit()
        sys.exit()

    # ── Update ───────────────────────────────────────────────

    def _update(self):
        self._frame += 1

        # ── 1. Read hand tracker ──────────────────────────────
        tip_cam, lms, cam_frame = self._tracker.get_state()
        self._gesture_name, self._finger_count = self._tracker.get_gesture_info()

        # Map camera coords → screen coords
        if tip_cam is not None:
            tip_screen = cam_to_screen(*tip_cam)
        else:
            tip_screen = None

        self._blade.push(tip_screen)

        # Show camera window with game overlay and capture keyboard input
        key = self._tracker.show_debug(self.screen)
        self._handle_keyboard(key)

        # ── 2. Palm gesture (start / restart) ─────────────────
        if self._palm_cooldown > 0:
            self._palm_cooldown -= 1

        if self._palm_cooldown == 0 and self._tracker.is_open_palm():
            if self._state in (STATE_START, STATE_GAMEOVER):
                self.new_game()
                self._palm_cooldown = 90   # ~1.5 s cooldown

        # ── 3. State-specific updates ─────────────────────────
        if self._state == STATE_PLAYING:
            self._update_playing()

        # ── 4. Particles & floaters (always animate) ──────────
        self._particles = [p for p in self._particles if p.alive]
        for p in self._particles:
            p.update()

        self._floaters = [f for f in self._floaters if f.alive]
        for f in self._floaters:
            f.update()

        # Flash fade
        if self._flash_alpha > 0:
            self._flash_alpha = max(0, self._flash_alpha - 8)

    def _update_playing(self):
        # ── Difficulty ramp (decrease spawn interval) ─────────
        self._spawn_interval = max(
            MIN_SPAWN_INTERVAL,
            FRUIT_SPAWN_INTERVAL - self._score * 2
        )

        # ── Spawn ──────────────────────────────────────────────
        self._spawn_timer += 1
        if (self._spawn_timer >= self._spawn_interval and
                len(self._fruits) < MAX_FRUITS_ALIVE):
            self._fruits.append(spawn_object(BOMB_CHANCE))
            self._spawn_timer = 0

        # ── Combo decay ───────────────────────────────────────
        if self._combo_timer > 0:
            self._combo_timer -= 1
        else:
            self._combo_slices = 0

        # ── Fruit physics ─────────────────────────────────────
        sliced_this_frame = 0

        for obj in self._fruits:
            obj.update()

            # Missed fruits and bombs simply disappear — no penalty

        # ── Slicing detection ─────────────────────────────────
        blade_tip  = self._blade.tip
        trail_pts  = list(self._blade._points)   # snapshot

        if blade_tip and self._blade.is_slicing and len(trail_pts) >= 2:
            p1 = trail_pts[-2]
            p2 = trail_pts[-1]

            for obj in self._fruits:
                if obj.sliced or not obj.alive:
                    continue
                hit = segment_circle_intersect(
                    p1, p2, obj.x, obj.y, obj.radius
                )
                if not hit:
                    continue

                # Slice!
                particles = obj.slice()
                self._particles.extend(particles)

                if isinstance(obj, Bomb):
                    # ── CHANGED: bomb hit → lose one heart, not instant game over ──
                    self._flash_alpha = 200
                    self._lives -= 1
                    self._floaters.append(
                        FloatingText(
                            "-1 ❤",
                            int(obj.x), int(obj.y) - 20,
                            color=(255, 60, 60), size=36, lifetime=70,
                        )
                    )
                    if self._lives <= 0:
                        self._end_game()
                        return
                    # ── END CHANGE ──────────────────────────────────────────────
                else:
                    # Fruit slice → score
                    sliced_this_frame += 1
                    self._score += SCORE_PER_FRUIT
                    self._floaters.append(
                        FloatingText(f"+{SCORE_PER_FRUIT}",
                                     int(obj.x), int(obj.y) - 20)
                    )

        # Combo bonus
        if sliced_this_frame >= 2:
            bonus = sliced_this_frame * SCORE_COMBO_BONUS
            self._score += bonus
            self._combo_slices += sliced_this_frame
            self._combo_timer   = COMBO_WINDOW
            cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            self._floaters.append(
                FloatingText(f"COMBO ×{sliced_this_frame}!",
                             cx, cy, color=(255, 120, 30), size=44)
            )
        elif sliced_this_frame == 1:
            self._combo_slices += 1
            self._combo_timer   = COMBO_WINDOW

        # Prune dead fruits
        self._fruits = [f for f in self._fruits if f.alive]

    def _end_game(self):
        self._high_score = max(self._high_score, self._score)
        self._state      = STATE_GAMEOVER

    # ── Draw ─────────────────────────────────────────────────

    def _draw(self):
        # Background
        self.screen.blit(self._bg, (0, 0))

        if self._state == STATE_START:
            self._draw_start()
        elif self._state == STATE_PLAYING:
            self._draw_playing()
        elif self._state == STATE_GAMEOVER:
            self._draw_gameover()

        # Particles and floaters always on top
        for p in self._particles:
            p.draw(self.screen)
        for f in self._floaters:
            f.draw(self.screen, self._font_md)

        # Blade trail
        self._blade.draw(self.screen)

        # Gesture indicator
        self._draw_gesture_indicator()

        # Red flash overlay for bomb
        if self._flash_alpha > 0:
            flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            flash.fill((200, 30, 30, self._flash_alpha))
            self.screen.blit(flash, (0, 0))

        pygame.display.flip()

    # ── Screen: Start ────────────────────────────────────────

    def _draw_start(self):
        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2

        # Decorative fruits bouncing in background
        self._draw_decorative_fruits()

        # Title
        draw_text_centered(self.screen, "🍉 FRUIT NINJA CV",
                           self._font_xl, (255, 220, 60), cx, cy - 160)
        draw_text_centered(self.screen,
                           "Slice fruits with your finger!",
                           self._font_md, (200, 230, 255), cx, cy - 80)

        # Instructions panel
        lines = [
            "✋  Open palm   →  Start game",
            "☝  Index finger  →  Slice fruits",
            "💣  Slice a bomb  →  Lose a heart!",
            "R  →  Restart   |   D  →  Debug cam   |   Q  →  Quit",
        ]
        for i, line in enumerate(lines):
            draw_text_centered(self.screen, line,
                               self._font_sm, (180, 210, 255),
                               cx, cy + 10 + i * 36)

        # Pulse "SHOW OPEN PALM" prompt
        pulse = int(200 + 55 * math.sin(self._frame * 0.06))
        draw_text_centered(self.screen, "✋  Show open palm to START",
                           self._font_md, (pulse, 255, pulse),
                           cx, cy + 200)

        if self._high_score > 0:
            draw_text_centered(self.screen,
                               f"Best score: {self._high_score}",
                               self._font_sm, (255, 200, 80),
                               cx, cy + 250)

    # ── Screen: Playing ──────────────────────────────────────

    def _draw_playing(self):
        # Fruits
        for obj in self._fruits:
            obj.draw(self.screen)

        # HUD
        self._draw_hud()

    def _draw_hud(self):
        # Score
        score_text = f"SCORE  {self._score}"
        draw_text_centered(self.screen, score_text,
                           self._font_hud, SCORE_COLOR,
                           SCREEN_WIDTH // 2, 36)

        # Lives (hearts)
        draw_lives(self.screen, self._lives,
                   self._font_hud, LIFE_COLOR, 40, 36)

        # Hint bar bottom
        hint = "R=Restart  D=Debug  Q=Quit"
        draw_text_centered(self.screen, hint,
                           self._font_sm, (100, 120, 160),
                           SCREEN_WIDTH // 2, SCREEN_HEIGHT - 20)

    def _draw_gesture_indicator(self):
        """Draw hand gesture indicator in top-right corner."""
        gesture_text = f"Gesture: {self._gesture_name}"
        finger_text = f"Fingers: {self._finger_count}"

        # Choose color based on gesture
        color = (150, 150, 150)  # default gray
        if self._gesture_name == "OPEN_PALM":
            color = (0, 255, 0)   # green
        elif self._gesture_name == "POINTING":
            color = (255, 200, 0)  # yellow
        elif self._gesture_name == "FIST":
            color = (255, 0, 0)    # red

        # Draw semi-transparent background box
        font_height = 24
        box_y1 = 10
        box_y2 = box_y1 + font_height * 2 + 10
        box_x1 = SCREEN_WIDTH - 280
        box_x2 = SCREEN_WIDTH - 10

        bg_box = pygame.Surface((box_x2 - box_x1, box_y2 - box_y1), pygame.SRCALPHA)
        bg_box.fill((0, 0, 0, 100))
        self.screen.blit(bg_box, (box_x1, box_y1))

        # Draw text
        draw_text_centered(self.screen, gesture_text,
                           self._font_sm, color,
                           (box_x1 + box_x2) // 2, box_y1 + 15)
        draw_text_centered(self.screen, finger_text,
                           self._font_sm, (180, 220, 255),
                           (box_x1 + box_x2) // 2, box_y1 + 45)

    # ── Screen: Game Over ────────────────────────────────────

    def _draw_gameover(self):
        cx = SCREEN_WIDTH  // 2
        cy = SCREEN_HEIGHT // 2

        # Dim overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        draw_text_centered(self.screen, "GAME OVER",
                           self._font_xl, (220, 50, 50), cx, cy - 120)
        draw_text_centered(self.screen, f"Score:  {self._score}",
                           self._font_lg, SCORE_COLOR, cx, cy - 30)
        draw_text_centered(self.screen, f"Best:   {self._high_score}",
                           self._font_md, (200, 200, 200), cx, cy + 40)

        pulse = int(200 + 55 * math.sin(self._frame * 0.07))
        draw_text_centered(self.screen, "✋  Open palm  or  press R  to restart",
                           self._font_md, (pulse, 255, pulse), cx, cy + 120)
        draw_text_centered(self.screen, "Press Q to quit",
                           self._font_sm, (150, 150, 180), cx, cy + 175)

    # ── Decorative background fruits on start screen ─────────

    def _draw_decorative_fruits(self):
        """A few large semi-transparent fruit circles drifting in the BG."""
        seed_cols = [(220, 60, 80), (255, 140, 0), (80, 160, 60),
                     (255, 230, 50), (130, 60, 180)]
        for i, col in enumerate(seed_cols):
            t   = (self._frame * 0.4 + i * 72) % 360
            x   = int(100 + i * 240 + 40 * math.sin(math.radians(t + i * 40)))
            y   = int(SCREEN_HEIGHT // 2 + 60 * math.cos(math.radians(t)))
            surf = pygame.Surface((160, 160), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*col, 40), (80, 80), 80)
            self.screen.blit(surf, (x - 80, y - 80))


# ════════════════════════════════════════════════════════════
#  Entry point
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("  Fruit Ninja CV  –  Python + OpenCV + MediaPipe + Pygame")
    print("=" * 55)
    print("  Controls:")
    print("    ✋  Open palm       →  Start / Restart")
    print("    ☝  Index finger    →  Slice fruits (move fast!)")
    print("    💣  Slice a bomb    →  Lose a heart!")
    print("    R                  →  Restart")
    print("    D                  →  Toggle debug camera window")
    print("    Q / Esc            →  Quit")
    print("=" * 55)
    Game().run()