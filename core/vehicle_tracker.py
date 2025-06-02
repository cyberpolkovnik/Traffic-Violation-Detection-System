from ultralytics import YOLO
import cv2
import numpy as np
import json
import time
from core.sort import Sort


class VehicleTracker:
    def __init__(self, yolo_model_path, log_file_path, video_path=None, real_distance_meters=20):
        """
        Initialize the VehicleTracker with YOLO model and tracking configuration.
        
        Args:
            yolo_model_path (str): Path to YOLO model weights
            log_file_path (str): Path to save speed logs
            video_path (str, optional): Path to input video file
            real_distance_meters (int): Known distance between marker lines in meters
        """
        self.model = YOLO(yolo_model_path)  # YOLO object detection model
        self.sort_tracker = Sort()  # SORT tracker for object tracking
        self.y_green = None  # Y-coordinate of green marker line
        self.y_red = None  # Y-coordinate of red marker line
        self.vehicle_data = {}  # Stores tracking data for each vehicle
        self.log_file_path = log_file_path  # Path to save speed logs
        self.speed_logs = []  # List of logged speed measurements
        self.frame_count = 0  # Counter for processed frames
        self.fps = None  # Frames per second of the video
        self.video_path = video_path  # Path to input video
        self.real_distance_meters = real_distance_meters  # Known distance between markers

    def set_lines(self, y_green, y_red):
        """
        Set the y-coordinates of the marker lines used for speed calculation.
        
        Args:
            y_green (int): Y-coordinate of green line (closer line)
            y_red (int): Y-coordinate of red line (farther line)
        """
        self.y_green = y_green
        self.y_red = y_red

    def _initialize_fps(self):
        """Initialize FPS by reading from video if not already set."""
        if self.fps is None:
            cap = cv2.VideoCapture(self.video_path)
            self.fps = cap.get(cv2.CAP_PROP_FPS) or 25  # Default to 25 if not available
            cap.release()
            print(f"[INFO] FPS set to: {self.fps}")

    def _is_inside_zone(self, cy):
        """
        Check if a point is between the two marker lines.
        
        Args:
            cy (int): Y-coordinate of the point to check
            
        Returns:
            bool: True if point is between the lines
        """
        return min(self.y_green, self.y_red) <= cy <= max(self.y_green, self.y_red)

    def _calculate_speed(self, start, end):
        """
        Calculate speed based on time taken to cross known distance.
        
        Args:
            start (float): Start time in seconds
            end (float): End time in seconds
            
        Returns:
            tuple: (speed_kmh, duration_seconds) or (None, None) if invalid
        """
        duration = end - start
        if duration <= 0:
            return None, None
        # Calculate speed: distance/time converted to km/h
        speed = (self.real_distance_meters / duration) * 3.6
        return round(speed, 2), round(duration, 2)

    def _log_speed(self, track_id, vehicle, speed, duration):
        """
        Log speed measurement and update vehicle data.
        
        Args:
            track_id (int): ID of the tracked vehicle
            vehicle (dict): Vehicle tracking data
            speed (float): Calculated speed in km/h
            duration (float): Time taken to cross the zone
        """
        vehicle["speed"] = speed
        log_entry = {
            "track_id": track_id,
            "speed_kmh": speed,
            "duration_s": duration,
            "timestamp": time.time(),
            "start_time": vehicle["start"],
            "end_time": vehicle["end"]
        }
        self.speed_logs.append(log_entry)
        print(f"[LOG] ID {track_id}: {speed} km/h in {duration} s")

    def process_detection(self, track, current_time):
        """
        Process a single detection and update tracking data.
        
        Args:
            track (array): Tracking data [x1,y1,x2,y2,track_id]
            current_time (float): Current time in video timeline
            
        Returns:
            tuple: Tracking and processing results
        """
        x1, y1, x2, y2, track_id = map(int, track)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2  # Center point of bounding box
        
        # Get or create vehicle tracking data
        vehicle = self.vehicle_data.setdefault(track_id, {
            "start": None, "end": None, "speed": None, "active": False
        })

        in_zone = self._is_inside_zone(cy)

        # Handle zone entry/exit events
        if in_zone and not vehicle["active"]:
            vehicle["start"] = current_time
            vehicle["active"] = True
        elif not in_zone and vehicle["active"]:
            vehicle["end"] = current_time
            vehicle["active"] = False

            # Calculate speed if we have valid timing data
            if vehicle["start"] is not None:
                speed, duration = self._calculate_speed(vehicle["start"], vehicle["end"])
                if speed is not None:
                    self._log_speed(track_id, vehicle, speed, duration)

        return x1, y1, x2, y2, track_id, in_zone, vehicle

    def track_objects(self, frame):
        """
        Process a frame to detect, track, and measure vehicle speeds.
        
        Args:
            frame (numpy.ndarray): Input video frame
            
        Returns:
            numpy.ndarray: Frame with visualizations
        """
        self._initialize_fps()
        self.frame_count += 1
        current_time = self.frame_count / self.fps  # Current time in video

        # Run YOLO detection
        results = self.model(frame, verbose=False)[0]
        # Format detections for SORT tracker [x1,y1,x2,y2,confidence]
        detections = [
            [*map(int, box.xyxy[0]), float(box.conf[0])]
            for box in results.boxes
        ]

        # Update tracker with new detections
        tracks = self.sort_tracker.update(np.array(detections))

        # Process each tracked object
        for track in tracks:
            x1, y1, x2, y2, track_id, in_zone, vehicle = self.process_detection(track, current_time)

            # Choose color based on zone status
            color = (255, 255, 0) if in_zone else (57, 255, 20)  # Yellow if in zone, green otherwise
            label = f"ID {track_id}"
            if vehicle["speed"] is not None:
                label += f" | {vehicle['speed']} km/h"

            # Draw bounding box and label
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        return frame

    def save_logs(self):
        """Save collected speed logs to JSON file."""
        with open(self.log_file_path, 'w') as f:
            json.dump(self.speed_logs, f, indent=4)
        print(f"[INFO] Speed logs saved to: {self.log_file_path}")