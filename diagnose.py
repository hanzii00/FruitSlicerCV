"""
Quick diagnostic: shows your webcam feed with skin mask overlay.
Prints the actual YCrCb values at the centre of the frame so we
can tune SKIN_LOWER / SKIN_UPPER to match YOUR skin tone.
Run with:  python diagnose.py
Press Q to quit.
"""
import cv2
import numpy as np

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# Current thresholds
SKIN_LOWER = np.array([0,   133,  77], dtype=np.uint8)
SKIN_UPPER = np.array([255, 173, 127], dtype=np.uint8)

print("Showing webcam. Hold your hand in front of camera.")
print("YCrCb values at frame centre are printed below.")
print("Press Q to quit.")

while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)

    ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
    mask  = cv2.inRange(ycrcb, SKIN_LOWER, SKIN_UPPER)

    # Colour the mask green and overlay
    overlay = frame.copy()
    overlay[mask > 0] = (0, 200, 0)
    blended = cv2.addWeighted(frame, 0.6, overlay, 0.4, 0)

    # Print YCrCb at centre pixel
    h, w = frame.shape[:2]
    cx, cy = w//2, h//2
    yval, cr, cb = ycrcb[cy, cx]
    print(f"\rCentre YCrCb: Y={yval:3d}  Cr={cr:3d}  Cb={cb:3d}   ", end="", flush=True)

    # Draw crosshair at centre
    cv2.circle(blended, (cx, cy), 6, (0, 0, 255), -1)
    cv2.putText(blended, f"Y={yval} Cr={cr} Cb={cb}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
    cv2.putText(blended, "Green = detected skin | Q to quit",
                (10, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

    cv2.imshow("Skin Diagnostic", blended)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print()