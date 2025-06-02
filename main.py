from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import os
import shutil

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIRECTORY = "uploaded_videos"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

# Route to serve the main page
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})

# Route to handle file uploads
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Define the file path for saving the uploaded file
    file_location = os.path.join(UPLOAD_DIRECTORY, file.filename)
    try:
        # Save the uploaded file to the specified location
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)
        print(f"Uploaded file: {file_location}")
        return JSONResponse(content={"info": "File uploaded successfully"})
    except Exception as e:
        print(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")
    
