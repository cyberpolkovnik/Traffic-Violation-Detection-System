from fastapi import FastAPI, File, UploadFile, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import cv2
import numpy as np
import json
import shutil
import os
import subprocess
from pydantic import BaseModel

from core.camera_calibration import CameraCalibrator
from core.vehicle_tracker import VehicleTracker
from core.database import Database
from config import SPEED_THRESHOLD_KMH, REAL_DISTANCE_METERS

# Initialize FastAPI application
app = FastAPI()

# Mount directories for serving static files, snapshots, processed videos, and video clips
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")
app.mount("/processed_videos", StaticFiles(directory="processed_videos"), name="processed_videos")
app.mount("/video_clips", StaticFiles(directory="video_clips"), name="video_clips")
# Initialize Jinja2 templates for rendering HTML
templates = Jinja2Templates(directory="templates")

# Define directories for file storage
UPLOAD_DIRECTORY = "uploaded_videos"
CALIBRATION_DIRECTORY = "calibration_data"
PROCESSED_VIDEOS_DIRECTORY = "processed_videos"
VIDEO_CLIPS_DIRECTORY = "video_clips"

# Create directories if they don't exist
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
os.makedirs(CALIBRATION_DIRECTORY, exist_ok=True)
os.makedirs(PROCESSED_VIDEOS_DIRECTORY, exist_ok=True)
os.makedirs(VIDEO_CLIPS_DIRECTORY, exist_ok=True)
os.makedirs("snapshots", exist_ok=True)

# Path to YOLO model for vehicle tracking
MODEL_PATH = "core/model/best.pt"

# Database configuration
DB_CONFIG = {
    "dbname": "traffic_reports",
    "user": "traffic_user",
    "password": "01234",
    "host": "localhost",
    "port": "5432"
}

# Pydantic model for video processing request
class ProcessVideoRequest(BaseModel):
    video_filename: str
    calibration_file: str

# Route to serve the main page
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Render the index.html template for the main page
    return templates.TemplateResponse(request, "index.html", {"request": request})

# Route to handle file uploads
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Construct path for saving the uploaded video file
    file_location = os.path.join(UPLOAD_DIRECTORY, file.filename)
    try:
        # Save the uploaded file to the designated directory
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)
        print(f"Uploaded file: {file_location}")
        # Return success response
        return JSONResponse(content={"info": "File uploaded successfully"})
    except Exception as e:
        print(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

# Route to serve the calibration page
@app.get("/calibration", response_class=HTMLResponse)
async def calibration_page(request: Request, filename: str = Query(...)):
    try:
        # Construct paths for video and snapshot
        video_path = os.path.join(UPLOAD_DIRECTORY, filename)
        snapshot_path = os.path.join("snapshots", f"{filename}.jpg")

        print(f"Calibration request for video: {video_path}")
        # Check if video file exists
        if not os.path.exists(video_path):
            raise HTTPException(status_code=400, detail=f"Video file not found: {video_path}")

        # Initialize calibrator and load image
        calibrator = CameraCalibrator(video_path, snapshot_path)
        calibrator.load_image()

        # Verify snapshot was created successfully
        if not os.path.exists(snapshot_path):
            raise HTTPException(status_code=500, detail=f"Failed to create snapshot: {snapshot_path}")

        print(f"Snapshot available at: {snapshot_path}")
        # Render calibration.html with snapshot and filename
        return templates.TemplateResponse(request, "calibration.html", {
            "request": request,
            "snapshot_path": f"/snapshots/{filename}.jpg",
            "filename": filename
        })
    except Exception as e:
        print(f"Error in calibration page: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating snapshot: {str(e)}")

# Route to save calibration data
@app.post("/save_calibration")
async def save_calibration(data: dict):
    try:
        print(f"Received calibration data: {data}")
        # Extract filename from request data
        filename = data.get("filename")
        if not filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        # Convert image and object points to numpy arrays
        image_points = [[point['x'], point['y']] for point in data.get("image_points", [])]
        object_points = data.get("object_points", [])
        
        image_points = np.array(image_points, dtype=np.float32)
        object_points = np.array(object_points, dtype=np.float32)
        
        print(f"Image points: {image_points}")
        print(f"Object points: {object_points}")
        
        # Validate point counts for calibration
        if len(image_points) < 4 or len(object_points) < 4:
            raise HTTPException(status_code=400, detail="At least 4 points required")
        if len(image_points) != len(object_points):
            raise HTTPException(status_code=400, detail="Number of 2D and 3D points must match")

        # Verify video file exists
        video_path = os.path.join(UPLOAD_DIRECTORY, filename)
        print(f"Checking video path: {video_path}, exists: {os.path.exists(video_path)}")
        if not os.path.exists(video_path):
            raise HTTPException(status_code=400, detail=f"Video file not found: {video_path}")

        # Initialize calibrator with video and snapshot paths
        snapshot_path = os.path.join("snapshots", f"{filename}.jpg")
        calibrator = CameraCalibrator(video_path, snapshot_path)
        calibrator.image_points = image_points
        calibrator.object_points = object_points
        # Perform camera calibration
        calibrator.calibrate()

        # Save calibration data to JSON file
        calibration_file = os.path.join(CALIBRATION_DIRECTORY, f"{filename}.json")
        calibrator.save_calibration(calibration_file)

        # Return success response with file path
        return JSONResponse(content={"status": "success", "message": f"Calibration saved to {calibration_file}"})
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Route to download processed video
@app.get("/download_video")
async def download_video(video_filename: str = Query(...)):
    # Construct path to processed video
    video_path = os.path.join(PROCESSED_VIDEOS_DIRECTORY, video_filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video file {video_filename} not found")

    return FileResponse(video_path, filename=video_filename)

# Route to list available calibration files
@app.get("/list_calibration_files")
async def list_calibration_files():
    try:
        # Retrieve list of JSON calibration files
        files = [f for f in os.listdir(CALIBRATION_DIRECTORY) if f.endswith('.json')]
        return JSONResponse(content={"files": files})
    except Exception as e:
        print(f"Error listing calibration files: {str(e)}")
        # Raise HTTP exception on error
        raise HTTPException(status_code=500, detail=f"Error listing calibration files: {str(e)}")

# Route to retrieve calibration data
@app.get("/get_calibration")
async def get_calibration(calibration_file: str = Query(...)):
    # Construct path to calibration file
    calibration_path = os.path.join(CALIBRATION_DIRECTORY, calibration_file)
    if not os.path.exists(calibration_path):
        raise HTTPException(status_code=404, detail=f"Calibration file {calibration_file} not found")
    # Load and return calibration data
    with open(calibration_path, 'r') as f:
        calibration_data = json.load(f)
    return JSONResponse(content=calibration_data)

# Route to retrieve speed log data
@app.get("/get_speed_log")
async def get_speed_log(log_file: str = Query(...)):
    # Construct path to speed log file
    log_path = os.path.join(PROCESSED_VIDEOS_DIRECTORY, log_file)
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail=f"Speed log file {log_file} not found")
    # Load and return speed log data
    with open(log_path, 'r') as f:
        log_data = json.load(f)
    return JSONResponse(content=log_data)

# Route to serve the speed estimation page
@app.get("/speed_estimation", response_class=HTMLResponse)
async def speed_estimation_page(request: Request, calibration_file: str = Query(None)):
    return templates.TemplateResponse(request, "speed_estimation.html", {
        "request": request,
        "calibration_file": calibration_file
    })

# Route to process video for speed estimation
@app.post("/process_video")
async def process_video(request: ProcessVideoRequest):
    try:
        # Extract video and calibration file names from request
        video_filename = request.video_filename
        calibration_file = request.calibration_file
        video_path = os.path.join(UPLOAD_DIRECTORY, video_filename)
        calibration_path = os.path.join(CALIBRATION_DIRECTORY, calibration_file)
        output_video_path = os.path.join(PROCESSED_VIDEOS_DIRECTORY, f"processed_{video_filename}")
        converted_video_path = os.path.join(PROCESSED_VIDEOS_DIRECTORY, f"converted_{video_filename}")
        log_file_path = os.path.join(PROCESSED_VIDEOS_DIRECTORY, f"speed_log_{video_filename}.json")

        # Validate file existence
        if not os.path.exists(video_path):
            raise HTTPException(status_code=400, detail=f"Video file {video_path} not found")
        if not os.path.exists(calibration_path):
            raise HTTPException(status_code=400, detail=f"Calibration file {calibration_path} not found")

        # Initialize and configure camera calibrator
        calibrator = CameraCalibrator(video_path)
        calibrator.load_calibration(calibration_path)
        calibrator.load_image()
        # Draw distance markers for speed calculation
        calibrator.draw_distance_markers()

        # Get y-coordinates of green and red marker lines
        green_line_y = calibrator.marker_lines.get('green')
        red_line_y = calibrator.marker_lines.get('red')

        if green_line_y is None or red_line_y is None:
            raise HTTPException(status_code=500, detail="Failed to determine marker lines")

        # Initialize vehicle tracker with YOLO model and configuration
        tracker = VehicleTracker(
            yolo_model_path=MODEL_PATH,
            log_file_path=log_file_path,
            video_path=video_path,
            real_distance_meters=REAL_DISTANCE_METERS
        )
        tracker.set_lines(green_line_y, red_line_y)

        # Open input video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise HTTPException(status_code=500, detail="Failed to open input video")

        # Get video properties
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        print(f"Video properties: width={frame_width}, height={frame_height}, fps={fps}")

        # Initialize video writer for processed output
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_video_path, fourcc, fps, (frame_width, frame_height))
        if not out.isOpened():
            cap.release()
            raise HTTPException(status_code=500, detail="Failed to open VideoWriter")

        # Process video frames
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            # Track objects in the frame
            frame = tracker.track_objects(frame)
            h, w = frame.shape[:2]
            # Draw green and red marker lines
            cv2.line(frame, (0, green_line_y), (w, green_line_y), (0, 255, 0), 2)
            cv2.line(frame, (0, red_line_y), (w, red_line_y), (0, 0, 255), 2)
            out.write(frame)
            frame_count += 1
            if frame_count % 100 == 0:
                print(f"Processed {frame_count} frames")

        print(f"Total frames processed: {frame_count}")
        cap.release()
        out.release()

        # Verify output video was created
        if not os.path.exists(output_video_path):
            raise HTTPException(status_code=500, detail="Output video file was not created")
        file_size = os.path.getsize(output_video_path)
        print(f"Output video created: {output_video_path}, size={file_size} bytes")

        # Convert video to browser-compatible format using FFmpeg
        try:
            result = subprocess.run([
                "ffmpeg", "-i", output_video_path, "-c:v", "libx264", "-c:a", "aac",
                "-strict", "-2", converted_video_path
            ], check=True, capture_output=True, text=True)
            print(f"Converted video created: {converted_video_path}")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr}")
            raise HTTPException(status_code=500, detail=f"FFmpeg conversion failed: {e.stderr}")

        # Save tracking logs
        tracker.save_logs()

        # Load speed logs
        with open(log_file_path, 'r') as f:
            logs = json.load(f)

        print(f"Loaded logs: {json.dumps(logs, indent=2)}")

        if not logs:
            print("Warning: No speed logs found in the log file")

        # Insert speed reports into database for vehicles exceeding threshold
        with Database(DB_CONFIG) as db:
            for log in logs:
                print(f"Processing log for track_id {log['track_id']}: speed={log['speed_kmh']} km/h")
                # Skip vehicles below speed threshold
                if log['speed_kmh'] <= SPEED_THRESHOLD_KMH:
                    print(f"Skipping report for track_id {log['track_id']}: speed {log['speed_kmh']} km/h <= {SPEED_THRESHOLD_KMH} km/h")
                    continue

                # Calculate clip time range with padding
                track_id = log['track_id']
                start_time = log['start_time'] - 0.5
                end_time = log['end_time'] + 0.5
                duration = end_time - start_time
                if start_time < 0:
                    start_time = 0
                    duration = end_time + 0.5

                print(f"Creating clip for track_id {track_id}: start_time={start_time}, end_time={end_time}, duration={duration}")

                # Generate video clip for the report
                clip_filename = f"clip_track_{track_id}_{int(log['timestamp'])}.mp4"
                clip_path = os.path.join(VIDEO_CLIPS_DIRECTORY, clip_filename)
                clip_url = f"/video_clips/{clip_filename}"
                print(f"Saving clip with path: {clip_url}")

                try:
                    # Create video clip using FFmpeg
                    result = subprocess.run([
                        "ffmpeg", "-i", converted_video_path, "-ss", str(start_time),
                        "-t", str(duration), "-c:v", "libx264", "-c:a", "aac",
                        "-strict", "-2", clip_path
                    ], check=True, capture_output=True, text=True)
                    print(f"Created video clip: {clip_path}, size={os.path.getsize(clip_path)} bytes")
                except subprocess.CalledProcessError as e:
                    print(f"FFmpeg clip error: {e.stderr}")
                    continue

                # Verify clip was created successfully
                if not os.path.exists(clip_path) or os.path.getsize(clip_path) == 0:
                    print(f"Clip {clip_path} is empty or not created")
                    continue

                # Insert report into database
                db.insert_report(
                    track_id=track_id,
                    speed_kmh=log['speed_kmh'],
                    duration_s=log['duration_s'],
                    timestamp=log['timestamp'],
                    clip_path=clip_url,
                    video_filename=video_filename
                )
                print(f"Inserted report for track_id {track_id} with clip_path: {clip_url}")

        # Return paths to processed video and log file
        return JSONResponse(content={
            "status": "success",
            "video_path": f"/processed_videos/converted_{video_filename}",
            "log_path": f"/processed_videos/speed_log_{video_filename}.json"
        })
    except Exception as e:
        print(f"Error processing video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")