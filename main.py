from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import os
import shutil
import numpy as np

from core.camera_calibration import CameraCalibrator

# Initialize FastAPI application
app = FastAPI()

# Mount directories for serving static files and snapshots
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")
templates = Jinja2Templates(directory="templates")

# Define directories for uploaded videos and calibration data
UPLOAD_DIRECTORY = "uploaded_videos"
CALIBRATION_DIRECTORY = "calibration_data"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
os.makedirs(CALIBRATION_DIRECTORY, exist_ok=True)

# Route to serve the main page
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
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

        return JSONResponse(content={"status": "success", "message": f"Calibration saved to {calibration_file}"})
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")