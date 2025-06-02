import cv2
import numpy as np
import os
import json

class CameraCalibrator:
    def __init__(self, video_path, snapshot_path=None):
        """
        Initialize the CameraCalibrator with video path and optional snapshot path.
        
        Args:
            video_path (str): Path to the input video file
            snapshot_path (str, optional): Path to save/load a snapshot image from the video
        """
        self.video_path = video_path
        self.snapshot_path = snapshot_path
        self.image = None  # Stores the current image/frame
        self.image_points = []  # 2D image points for calibration
        self.object_points = []  # 3D world points for calibration
        self.intrinsic = None  # Camera intrinsic matrix
        self.dist_coeffs = np.zeros((4, 1))  # Distortion coefficients
        self.rvec = None  # Rotation vector
        self.tvec = None  # Translation vector
        self.marker_lines = {}  # Stores distance marker positions

    def load_image(self):
        """Load an image from either existing snapshot or video file."""
        print(f"Loading image for video: {self.video_path}")
        if self.image is not None:
            print("Image already loaded, skipping.")
            return True

        # Try to load from existing snapshot if path provided
        if self.snapshot_path and os.path.exists(self.snapshot_path):
            print(f"Loading existing snapshot: {self.snapshot_path}")
            self.image = cv2.imread(self.snapshot_path)
            if self.image is None:
                raise Exception(f"Failed to load image from {self.snapshot_path}")
            print(f"Loaded snapshot with shape: {self.image.shape}")
            return True
        else:
            # If no snapshot exists, capture from video
            print(f"Creating new snapshot from video: {self.video_path}")
            if not os.path.exists(self.video_path):
                raise Exception(f"Video file not found: {self.video_path}")

            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                raise Exception(f"Could not open video file: {self.video_path}")

            ret, frame = cap.read()
            cap.release()
            if not ret:
                raise Exception(f"Failed to read frame from video: {self.video_path}")

            self.image = frame.copy()
            print(f"Loaded frame with shape: {self.image.shape}")

            # Save the snapshot if path provided
            if self.snapshot_path:
                print(f"Saving snapshot to: {self.snapshot_path}")
                os.makedirs(os.path.dirname(self.snapshot_path), exist_ok=True)
                cv2.imwrite(self.snapshot_path, frame)
                if not os.path.exists(self.snapshot_path):
                    raise Exception(f"Failed to save snapshot to: {self.snapshot_path}")
                print(f"Snapshot saved successfully: {self.snapshot_path}")

            return True

    def calibrate(self):
        """
        Perform camera calibration using the collected 2D-3D point correspondences.
        Uses Perspective-n-Point (PnP) algorithm to estimate camera pose.
        """
        if len(self.image_points) != len(self.object_points):
            raise Exception("Number of 2D and 3D points must match")
        if len(self.image_points) < 4:
            raise Exception("Need at least 4 points for calibration")
            
        self.load_image()
        h, w = self.image.shape[:2]
        
        # Initialize intrinsic matrix with reasonable defaults
        self.intrinsic = np.array([
            [w, 0, w/2],  # fx, skew, cx
            [0, h, h/2],  # 0, fy, cy
            [0, 0, 1]     # 0, 0, 1
        ], dtype=np.float32)
        
        print(f"Calibrating with image_points shape: {self.image_points.shape}")
        print(f"Calibrating with object_points shape: {self.object_points.shape}")
        
        # Solve Perspective-n-Point problem
        ret, rvec, tvec = cv2.solvePnP(
            self.object_points,
            self.image_points,
            self.intrinsic,
            self.dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        
        if not ret:
            raise Exception("Calibration failed")
        self.rvec = rvec
        self.tvec = tvec

    def draw_distance_markers(self):
        """
        Draw distance markers on the image based on the calibration.
        Projects 3D points at known distances onto the image plane.
        """
        if self.rvec is None or self.tvec is None:
            raise Exception("Camera not calibrated yet")
            
        self.load_image()
        image_height, image_width = self.image.shape[:2]
        self.marker_lines = {}
        
        # Define distances to mark (in meters) with their colors and names
        distances = [(20, (0, 255, 0), 'green'), (40, (0, 0, 255), 'red')]
        
        for x, color, name in distances:
            print(f"Processing distance marker: x={x}, color={color}, name={name}")
            
            # Create 3D point at distance x meters from camera (assuming y=3.5m, z=0)
            world_point = np.array([[float(x), 3.5, 0.0]], dtype=np.float32)
            
            # Project 3D point to 2D image coordinates
            img_point, _ = cv2.projectPoints(world_point, self.rvec, self.tvec,
                                            self.intrinsic, self.dist_coeffs)
            print(f"Projected image point: {img_point}")
            
            y2d = int(img_point[0][0][1])  # Extract y-coordinate
            print(f"Calculated y2d: {y2d}")
            
            # Store and draw the marker line
            self.marker_lines[name] = y2d
            cv2.line(self.image, (0, y2d), (image_width, y2d), color, 2)
            
            # Add distance text label
            text = str(x) + "m"
            print(f"Text to draw: {text}")
            cv2.putText(self.image, text, (5, y2d - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    def save_calibration(self, file_path):
        """
        Save calibration parameters to a JSON file.
        
        Args:
            file_path (str): Path to save the calibration data
        """
        if self.rvec is None or self.tvec is None:
            raise Exception("No calibration data to save")
            
        calibration_data = {
            'intrinsic': self.intrinsic.tolist(),
            'dist_coeffs': self.dist_coeffs.tolist(),
            'rvec': self.rvec.tolist(),
            'tvec': self.tvec.tolist(),
            'image_points': self.image_points.tolist(),
            'object_points': self.object_points.tolist()
        }
        
        with open(file_path, 'w') as f:
            json.dump(calibration_data, f, indent=4)

    def load_calibration(self, file_path):
        """
        Load calibration parameters from a JSON file.
        
        Args:
            file_path (str): Path to load the calibration data from
        """
        if not os.path.exists(file_path):
            raise Exception(f"Calibration file {file_path} not found")
            
        with open(file_path, 'r') as f:
            calibration_data = json.load(f)
            
        # Convert lists back to numpy arrays with correct data types
        self.intrinsic = np.array(calibration_data['intrinsic'], dtype=np.float32)
        self.dist_coeffs = np.array(calibration_data['dist_coeffs'], dtype=np.float32)
        self.rvec = np.array(calibration_data['rvec'], dtype=np.float32)
        self.tvec = np.array(calibration_data['tvec'], dtype=np.float32)
        self.image_points = np.array(calibration_data['image_points'], dtype=np.float32)
        self.object_points = np.array(calibration_data['object_points'], dtype=np.float32)
        
        print(f"Calibration loaded from {file_path}")