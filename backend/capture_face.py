import logging
import os

import cv2

logger = logging.getLogger(__name__)


def capture_reference_face(output_path="reference.jpg"):
    """
    Opens the webcam and captures a frame when the user presses 's' or 'Space'.
    Saves the frame to the specified output path.
    """
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        logger.error("Could not open webcam for reference face capture.")
        return

    logger.info("Press 's' or 'SPACE' to capture your face; 'q' or 'ESC' to quit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("Failed to capture a frame from the webcam.")
                break

            # Display the resulting frame
            cv2.imshow('Capture Reference Face', frame)

            key = cv2.waitKey(1) & 0xFF

            # 's' or SPACE to save
            if key == ord('s') or key == 32:
                if cv2.imwrite(output_path, frame):
                    logger.info("Reference face saved to %s", output_path)
                else:
                    logger.error("Failed to write reference face to %s", output_path)
                break

            # 'q' or ESC to quit
            if key == ord('q') or key == 27:
                logger.info("Reference face capture cancelled.")
                break
    except Exception:
        logger.exception("Unexpected error during reference face capture.")
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # Ensure backend directory context
    script_dir = os.path.dirname(os.path.abspath(__file__))
    save_path = os.path.join(script_dir, "reference.jpg")
    capture_reference_face(save_path)
