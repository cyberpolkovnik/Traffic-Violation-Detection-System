const img = new Image();
img.src = SNAPSHOT_PATH;

// Initialize canvas and context for drawing
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const pointsDiv = document.getElementById('points');
const points = [];

// Set fixed canvas dimensions
canvas.width = 1200;
canvas.height = 600;

// Scale and center image on canvas when loaded
img.onload = () => {
    const scale = Math.min(canvas.width / img.width, canvas.height / img.height);
    canvas.dataset.scale = scale;
    canvas.dataset.offsetX = (canvas.width - img.width * scale) / 2;
    canvas.dataset.offsetY = (canvas.height - img.height * scale) / 2;
    redrawCanvas();
};

// Handle canvas click to add calibration points
canvas.addEventListener('click', (e) => {
    if (!img.complete) return;
    
    const rect = canvas.getBoundingClientRect();
    const scale = parseFloat(canvas.dataset.scale);
    const offsetX = parseFloat(canvas.dataset.offsetX);
    const offsetY = parseFloat(canvas.dataset.offsetY);
    
    // Convert canvas coordinates to image coordinates
    const x = Math.round((e.clientX - rect.left - offsetX) / scale);
    const y = Math.round((e.clientY - rect.top - offsetY) / scale);
    
    // Add point if within image bounds
    if (x >= 0 && x <= img.width && y >= 0 && y <= img.height) {
        points.push({ x, y });
        redrawCanvas();
        updatePointsDiv();
        add3DInputFields(points.length - 1);
    }
});

// Redraw canvas with image and marked points
function redrawCanvas() {
    if (!img.complete) return;
    
    const scale = parseFloat(canvas.dataset.scale);
    const offsetX = parseFloat(canvas.dataset.offsetX);
    const offsetY = parseFloat(canvas.dataset.offsetY);
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, offsetX, offsetY, img.width * scale, img.height * scale);
    
    // Draw green dots for each calibration point
    points.forEach(({ x, y }) => {
        const canvasX = offsetX + x * scale;
        const canvasY = offsetY + y * scale;
        ctx.fillStyle = "lime";
        ctx.beginPath();
        ctx.arc(canvasX, canvasY, 5, 0, 2 * Math.PI);
        ctx.fill();
    });
}

// Update display of point coordinates
function updatePointsDiv() {
    pointsDiv.innerHTML = points.map((p, i) => `Point ${i + 1}: (${p.x}, ${p.y})`).join("<br>");
}

// Add input fields for 3D coordinates of a new point
function add3DInputFields(index) {
    const container = document.getElementById('coordinates-3d-fields');
    const group = document.createElement('div');
    group.className = 'coordinate-input-group';
    group.id = `coord-3d-${index}`;
    group.innerHTML = `
        <span>Point ${index + 1}:</span>
        <label>X</label><input type="number" name="x-${index}" step="any">
        <label>Y</label><input type="number" name="y-${index}" step="any">
        <label>Z</label><input type="number" name="z-${index}" step="any">
    `;
    container.appendChild(group);
}

// Reset calibration by clearing points and UI
document.getElementById('reset-calibration').addEventListener('click', () => {
    points.length = 0;
    redrawCanvas();
    updatePointsDiv();
    document.getElementById('coordinates-3d-fields').innerHTML = '';
});

// Remove the last added point and its 3D input fields
document.getElementById('undo-point').addEventListener('click', () => {
    if (points.length > 0) {
        points.pop();
        redrawCanvas();
        updatePointsDiv();
        const container = document.getElementById('coordinates-3d-fields');
        if (container.lastChild) container.removeChild(container.lastChild);
    }
});

// Show modal with list of calibration files
document.getElementById('upload-calibration').addEventListener('click', () => {
    const modal = document.getElementById('uploadModal');
    const select = document.getElementById('calibration-file-select');
    
    // Fetch and populate calibration file list
    fetch('/list_calibration_files')
        .then(response => response.json())
        .then(data => {
            select.innerHTML = '<option value="">-- Select a file --</option>';
            if (data.files && data.files.length > 0) {
                data.files.forEach(file => {
                    const option = document.createElement('option');
                    option.value = file;
                    option.textContent = file;
                    select.appendChild(option);
                });
            } else {
                select.innerHTML = '<option value="">No files available</option>';
            }
            modal.classList.remove('hidden');
        })
        .catch(error => {
            console.error('Error loading calibration files:', error);
            alert('Error loading file list');
        });
});

// Hide upload modal on cancel
document.getElementById('upload-cancel').addEventListener('click', () => {
    document.getElementById('uploadModal').classList.add('hidden');
});

// Confirm calibration file selection and redirect
document.getElementById('upload-confirm').addEventListener('click', () => {
    const select = document.getElementById('calibration-file-select');
    const calibrationFileName = select.value;
    
    if (!calibrationFileName) {
        alert('Please select a calibration file');
        return;
    }

    // Redirect to speed estimation page with selected file
    window.location.href = `/speed_estimation?calibration_file=${encodeURIComponent(calibrationFileName)}`;
    document.getElementById('uploadModal').classList.add('hidden');
});

// Handle "Next" button to save calibration data
document.getElementById('next-button').addEventListener('click', () => {
    const objectPoints = [];
    const inputs = document.querySelectorAll('#coordinates-3d-fields input');
    
    // Collect 3D coordinates from input fields
    for (let i = 0; i < inputs.length; i += 3) {
        const x = parseFloat(inputs[i].value);
        const y = parseFloat(inputs[i + 1].value);
        const z = parseFloat(inputs[i + 2].value);
        
        if (isNaN(x) || isNaN(y) || isNaN(z)) {
            alert('Please fill all 3D coordinates');
            return;
        }
        objectPoints.push([x, y, z]);
    }

    // Ensure at least 4 points for calibration
    if (points.length < 4 || objectPoints.length < 4) {
        alert('At least 4 points are required');
        return;
    }

    // Send calibration data to server
    fetch('/save_calibration', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            filename: FILENAME,
            image_points: points,
            object_points: objectPoints
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Redirect to speed estimation with calibration file
            const calibrationFileName = `${FILENAME}.json`;
            window.location.href = `/speed_estimation?calibration_file=${encodeURIComponent(calibrationFileName)}`;
        } else {
            alert('Error saving calibration');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error saving calibration');
    });
});