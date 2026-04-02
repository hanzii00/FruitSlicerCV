# ============================================================
#  hand_tracker.py  –  MediaPipe-based hand tracking
#  Replaces fragile HSV skin-color detection with a proper
#  ML hand landmark model that works regardless of:
#    - skin tone
#    - lighting conditions
#    - cluttered / warm-colored backgrounds
#
#  Install dependency once:
#    pip install mediapipe
# ============================================================
import cv2
import mediapipe as mp
import threading
import time
from settings import CAM_INDEX, CAM_WIDTH, CAM_HEIGHT, FLIP_CAM

# Landmark indices for each fingertip and its lower knuckle (MCP)
_TIP_IDS = [4, 8, 12, 16, 20]   # thumb, index, middle, ring, pinky tips
_MCP_IDS = [2, 5,  9, 13, 17]   # corresponding base knuckles


class HandTracker:
    def __init__(self):
        self.finger_tip    = None   # (x, y) of index fingertip in pixel coords
        self.landmarks     = None   # raw mediapipe NormalizedLandmarkList
        self.frame         = None   # annotated BGR frame

        self._lock         = threading.Lock()
        self._running      = True
        self._finger_count = 0
        self._gesture_name = "UNKNOWN"

        # ── MediaPipe setup ──────────────────────────────────────────────
        self._mp_hands   = mp.solutions.hands
        self._mp_draw    = mp.solutions.drawing_utils
        self._mp_styles  = mp.solutions.drawing_styles
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,          # we only care about one hand
            model_complexity=1,       # 1 = full model, better with partial hands
            min_detection_confidence=0.4,  # lower = detects even partial hands
            min_tracking_confidence=0.3,   # lower = keeps tracking through occlusion
        )
        # ─────────────────────────────────────────────────────────────────

        # Persistence: hold last known tip for this many frames after detection drops
        self._last_tip     = None
        self._tip_hold     = 0
        self._tip_hold_max = 8     # ~0.25 s at 30 fps

        # Smoothing: exponential moving average on tip position
        self._smooth_tip   = None
        self._smooth_alpha = 0.5   # 0 = very smooth/laggy, 1 = instant/raw

        self._cap = cv2.VideoCapture(CAM_INDEX)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, 30)

        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------ #
    #  Main capture / processing loop                                      #
    # ------------------------------------------------------------------ #
    def _capture_loop(self):
        while self._running:
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            if FLIP_CAM:
                frame = cv2.flip(frame, 1)

            h, w = frame.shape[:2]
            annotated = frame.copy()

            # MediaPipe expects RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._hands.process(rgb)

            tip          = None
            finger_count = 0
            gesture_name = "NO_HAND"

            if results.multi_hand_landmarks:
                hand_lms = results.multi_hand_landmarks[0]

                # Draw skeleton
                self._mp_draw.draw_landmarks(
                    annotated,
                    hand_lms,
                    self._mp_hands.HAND_CONNECTIONS,
                    self._mp_styles.get_default_hand_landmarks_style(),
                    self._mp_styles.get_default_hand_connections_style(),
                )

                # Raw index fingertip position (landmark 8)
                idx_tip = hand_lms.landmark[8]
                raw_tip = (int(idx_tip.x * w), int(idx_tip.y * h))

                # ── Smoothing: exponential moving average ──────────────
                if self._smooth_tip is None:
                    self._smooth_tip = raw_tip
                else:
                    sx = self._smooth_alpha * raw_tip[0] + (1 - self._smooth_alpha) * self._smooth_tip[0]
                    sy = self._smooth_alpha * raw_tip[1] + (1 - self._smooth_alpha) * self._smooth_tip[1]
                    self._smooth_tip = (sx, sy)

                tip = (int(self._smooth_tip[0]), int(self._smooth_tip[1]))

                # Reset persistence counter — we have a live detection
                self._last_tip = tip
                self._tip_hold = self._tip_hold_max

                cv2.circle(annotated, tip, 12, (0, 255, 0), -1)
                cv2.circle(annotated, tip, 12, (255, 255, 255), 2)

                finger_count = self._count_fingers(hand_lms)
                gesture_name = self._classify_gesture(finger_count)

                cv2.putText(annotated, f"Fingers: {finger_count}", (10, 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.putText(annotated, f"Gesture: {gesture_name}", (10, 65),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 100, 100), 2)

            else:
                # ── Persistence: hold last known tip for a few frames ──
                if self._tip_hold > 0 and self._last_tip is not None:
                    self._tip_hold -= 1
                    tip = self._last_tip
                    # Draw faded indicator so the player can see it's held
                    cv2.circle(annotated, tip, 12, (0, 180, 0), -1)
                    cv2.circle(annotated, tip, 12, (200, 200, 200), 2)
                    cv2.putText(annotated, "Tracking...", (10, 35),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 1)
                else:
                    self._smooth_tip = None   # reset smoother when truly lost
                    cv2.putText(annotated, "Show your hand to the camera",
                                (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                                (200, 200, 200), 1)

            with self._lock:
                self.finger_tip    = tip
                self.landmarks     = results.multi_hand_landmarks[0] if results.multi_hand_landmarks else None
                self._finger_count = finger_count
                self._gesture_name = gesture_name
                self.frame         = annotated

    # ------------------------------------------------------------------ #
    #  Finger counting via landmark geometry                               #
    # ------------------------------------------------------------------ #
    def _count_fingers(self, hand_lms):
        """
        A finger is "extended" when its tip is farther from the wrist
        than its MCP knuckle.  Works regardless of hand orientation or
        lighting — pure geometry on the 21 landmarks.
        """
        lm    = hand_lms.landmark
        wrist = lm[0]
        count = 0

        for i, (tip_id, mcp_id) in enumerate(zip(_TIP_IDS, _MCP_IDS)):
            tip = lm[tip_id]
            mcp = lm[mcp_id]

            if i == 0:
                # Thumb: extended when tip is clearly away from wrist horizontally
                if abs(tip.x - wrist.x) > abs(mcp.x - wrist.x):
                    count += 1
            else:
                # Other fingers: tip is above (lower y value) than its MCP
                if tip.y < mcp.y:
                    count += 1

        return count

    # ------------------------------------------------------------------ #
    #  Gesture classification                                              #
    # ------------------------------------------------------------------ #
    def _classify_gesture(self, finger_count):
        if finger_count >= 4:
            return "OPEN_PALM"
        elif finger_count == 3:
            return "THREE"
        elif finger_count == 2:
            return "PEACE"
        elif finger_count == 1:
            return "POINTING"
        else:
            return "FIST"

    # ------------------------------------------------------------------ #
    #  Public API  (identical to the original – no game code changes)     #
    # ------------------------------------------------------------------ #
    def get_state(self):
        with self._lock:
            return self.finger_tip, self.landmarks, self.frame

    def is_open_palm(self):
        with self._lock:
            return self._finger_count >= 4

    def get_gesture_info(self):
        """Returns (gesture_name, finger_count)."""
        with self._lock:
            return self._gesture_name, self._finger_count

    def show_debug(self, pygame_surface=None):
        """Display camera + game overlay and return keyboard input."""
        import numpy as np
        with self._lock:
            frame = self.frame
        if frame is not None:
            # Brighten the camera feed
            frame = cv2.convertScaleAbs(frame, alpha=1.4, beta=25)

            if pygame_surface is not None:
                import pygame
                game_arr = pygame.surfarray.array3d(pygame_surface)
                game_arr = np.transpose(game_arr, (1, 0, 2))
                game_arr = cv2.cvtColor(game_arr.astype(np.uint8), cv2.COLOR_RGB2BGR)
                game_arr = cv2.resize(game_arr, (frame.shape[1], frame.shape[0]))
                # Camera dominant — game UI/fruits lightly overlaid
                frame = cv2.addWeighted(frame, 0.45, game_arr, 0.55, 0)

            cv2.imshow("FruitSlicerCV – Hand Tracking", frame)
            # Capture keyboard input: return the key code (or -1 if no key pressed)
            key = cv2.waitKey(1) & 0xFF
            return key
        return -1

    def release(self):
        self._running = False
        self._thread.join(timeout=2)
        self._hands.close()
        self._cap.release()
        cv2.destroyAllWindows()