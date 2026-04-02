# 🍉 Fruit Ninja CV

A real-time desktop **Fruit Ninja** clone where you slice fruits using your **index finger** tracked by your webcam — built with Python, OpenCV, MediaPipe, and Pygame.

---

## 📁 Project Structure

```
fruit_ninja_cv/
├── main.py           # Game loop, states, rendering
├── hand_tracker.py   # MediaPipe hand tracking (background thread)
├── fruit.py          # Fruit / Bomb / Particle classes & physics
├── utils.py          # Coordinate mapping, blade trail, helpers
├── settings.py       # All tunable constants
└── requirements.txt  # pip dependencies
```

---

## 🛠 Installation

### 1 — Prerequisites

- **Python 3.10+** (3.11 recommended)
- A working **webcam**

### 2 — Create a virtual environment (recommended)

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

> **Troubleshooting tips:**
> - On **Apple Silicon (M1/M2/M3)** Macs: `mediapipe` may need `pip install mediapipe-silicon`
> - On **Linux** you may need: `sudo apt install libgl1`
> - If `pygame` doesn't display: `pip install pygame --pre`

---

## ▶ Running the Game

```bash
python main.py
```

---

## 🎮 Controls

| Action | How |
|---|---|
| Start / Restart | ✋ Show **open palm** to webcam |
| Slice a fruit | ☝ Move **index finger** fast across a fruit |
| Restart | Press **R** |
| Toggle debug cam | Press **D** |
| Fullscreen | Press **F** |
| Quit | Press **Q** or **Esc** |

---

## 🕹 How to Play

1. Run `python main.py`
2. **Show your open hand** (palm facing the camera) to start
3. Point your **index finger** at fruits flying up on screen
4. **Swipe your finger quickly** across a fruit to slice it — slow movements don't count!
5. **Avoid bombs** (dark round objects with a glowing fuse) — touching one ends the game
6. You have **3 lives** — each fruit that falls off-screen costs one life
7. Slice **multiple fruits in one swipe** for a **COMBO** bonus!

---

## ⚙ Tuning (settings.py)

| Setting | Default | Description |
|---|---|---|
| `BLADE_MIN_SPEED` | `8` | Minimum finger speed (px/frame) to count as a slice |
| `BLADE_RADIUS` | `28` | Collision radius around finger tip |
| `DETECTION_CONFIDENCE` | `0.7` | MediaPipe detection sensitivity |
| `FRUIT_SPAWN_INTERVAL` | `90` | Frames between fruit spawns (decreases with score) |
| `BOMB_CHANCE` | `0.18` | Probability each spawn is a bomb (0.0–1.0) |
| `STARTING_LIVES` | `3` | Lives at game start |
| `FLIP_CAM` | `True` | Mirror the webcam feed (natural movement) |
| `CAM_INDEX` | `0` | Webcam index (change if you have multiple cameras) |

---

## 🏗 Architecture Notes

### Threading model
`HandTracker` captures webcam frames and runs MediaPipe inference in a **background daemon thread**. The main game thread reads the latest finger position via a lock-protected shared variable — this prevents the 30 Hz camera from stalling the 60 FPS game loop.

### Coordinate mapping
MediaPipe returns landmark positions as **normalised [0, 1] floats** relative to the camera frame. `cam_to_screen()` in `utils.py` converts these to Pygame screen pixels with a configurable edge margin so the player doesn't need to reach the very edge of the camera view.

### Slice detection
Slicing uses **segment–circle intersection** (a ray-cast) between the last two blade-trail points and each fruit's hitbox. This catches fast swipes that might "skip" a fruit hitbox between frames — much more reliable than point-in-circle checks alone.

### Particle system
Each sliced fruit spawns ~22 `Particle` objects with randomised velocity, gravity, and fade-out — giving the juice-splatter effect without any external graphics files.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `opencv-python` | Webcam capture + frame handling |
| `mediapipe` | Real-time hand landmark detection |
| `pygame` | Game window, rendering, event loop |

No external assets, fonts, or sound files required — everything is drawn procedurally.