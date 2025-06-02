// Get DOM elements for the drop area, upload button, and file name display
let dropArea = document.getElementById('drop-area')
let uploadBtn = document.getElementById('uploadBtn')
let fileNameDisplay = document.getElementById('file-name')

// Variable to store the selected file
let selectedFile = null

// Prevent default behavior for drag-and-drop events
;['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false)
})

// Function to prevent default browser behavior for drag-and-drop events
function preventDefaults(e) {
    e.preventDefault()
    e.stopPropagation()
}

// Add highlight class when dragging file over drop area
dropArea.addEventListener('dragenter', () => dropArea.classList.add('highlight'))

// Remove highlight class when dragging file leaves drop area
dropArea.addEventListener('dragleave', () => dropArea.classList.remove('highlight'))

// Handle file drop: remove highlight and store the dropped file
dropArea.addEventListener('drop', e => {
    dropArea.classList.remove('highlight')
    const files = e.dataTransfer.files
    storeFile(files[0])
})

// Function to store the selected file and update UI
function storeFile(file) {
    if (!file) return
    selectedFile = file
    fileNameDisplay.innerText = `Selected file: ${file.name}`
    uploadBtn.disabled = false // Enable upload button
}

// Handle upload button click: send file to server
uploadBtn.addEventListener('click', () => {
    if (!selectedFile) return
    const formData = new FormData()
    formData.append('file', selectedFile)

    // Send POST request to upload endpoint
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) throw new Error('Upload failed')
        // Redirect to calibration page with filename as query parameter
        window.location.href = `/calibration?filename=${encodeURIComponent(selectedFile.name)}`
    })
    .catch(error => {
        alert('Error while uploading file')
        console.error(error)
    })
})