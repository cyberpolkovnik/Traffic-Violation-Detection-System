document.addEventListener("DOMContentLoaded", function() {
    const processButton = document.getElementById('process-video');
    const videoSource = document.getElementById('video-source');
    const videoPlayer = document.getElementById('processed-video');
    const speedTableBody = document.getElementById('speed-table-body');
    const playPauseButton = document.getElementById('play-pause');
    const slowDownButton = document.getElementById('slow-down');
    const speedUpButton = document.getElementById('speed-up');

    // Log calibration and video filenames for debugging
    console.log('CALIBRATION_FILE:', CALIBRATION_FILE);
    console.log('VIDEO_FILENAME:', VIDEO_FILENAME);

    // Disable video control buttons until video is loaded
    playPauseButton.disabled = true;
    slowDownButton.disabled = true;
    speedUpButton.disabled = true;

    // Toggle play/pause state of the video
    playPauseButton.addEventListener('click', () => {
        if (videoPlayer.paused) {
            videoPlayer.play().catch(error => {
                console.error('Video playback error:', error);
                alert('Failed to play video.');
            });
            playPauseButton.textContent = 'Pause';
        } else {
            videoPlayer.pause();
            playPauseButton.textContent = 'Play';
        }
    });

    // Decrease video playback speed by half
    slowDownButton.addEventListener('click', () => {
        videoPlayer.playbackRate *= 0.5;
        console.log('Playback rate:', videoPlayer.playbackRate);
    });

    // Double video playback speed
    speedUpButton.addEventListener('click', () => {
        videoPlayer.playbackRate *= 2;
        console.log('Playback rate:', videoPlayer.playbackRate);
    });

    // Reset play button text when video ends
    videoPlayer.addEventListener('ended', () => {
        playPauseButton.textContent = 'Play';
    });

    // Handle video processing request
    processButton.addEventListener('click', () => {
        // Validate required files
        if (!CALIBRATION_FILE || !VIDEO_FILENAME) {
            alert('Calibration file or video not specified');
            return;
        }

        // Disable button and show processing state
        processButton.disabled = true;
        processButton.textContent = 'Processing...';

        // Send video processing request to server
        fetch('/process_video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                video_filename: VIDEO_FILENAME,
                calibration_file: CALIBRATION_FILE
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Process video response:', data);
            if (data.status === 'success') {
                // Verify video file accessibility
                fetch(data.video_path, { method: 'HEAD' })
                    .then(videoResponse => {
                        if (videoResponse.ok) {
                            // Set video source and load video
                            videoSource.src = data.video_path;
                            console.log('Setting video source to:', data.video_path);
                            videoPlayer.load();
                            videoPlayer.style.display = 'block';
                            videoPlayer.play().catch(error => {
                                console.error('Video playback error:', error);
                                alert('Failed to play video. Check format or browser console.');
                            });
                            videoPlayer.addEventListener('error', () => {
                                console.error('Video element error:', videoPlayer.error);
                            });
                            // Enable control buttons once video is loaded
                            videoPlayer.addEventListener('loadeddata', () => {
                                console.log('Video loaded successfully');
                                playPauseButton.disabled = false;
                                slowDownButton.disabled = false;
                                speedUpButton.disabled = false;
                                playPauseButton.textContent = 'Pause';
                            });
                        } else {
                            console.error('Video file not accessible:', data.video_path);
                            alert('Video not found on server');
                        }
                    })
                    .catch(error => {
                        console.error('Error checking video file:', error);
                        alert('Error verifying video');
                    });

                // Fetch and display speed log data
                fetch(`/get_speed_log?log_file=speed_log_${VIDEO_FILENAME}.json`)
                    .then(response => response.json())
                    .then(logs => {
                        speedTableBody.innerHTML = '';
                        // Populate table with speed log entries
                        logs.forEach(log => {
                            const tr = document.createElement('tr');
                            tr.innerHTML = `
                                <td>${log.track_id}</td>
                                <td>${log.speed_kmh}</td>
                                <td>${log.duration_s}</td>
                            `;
                            speedTableBody.appendChild(tr);
                        });
                    })
                    .catch(error => {
                        console.error('Error loading speed logs:', error);
                        alert('Error loading speed logs.');
                    });
            } else {
                alert(`Data error: ${data.detail || 'Unknown error.'}`);
            }
        })
        .catch(error => {
            console.error('Error processing video:', error);
            alert('Error processing video.');
        })
        .finally(() => {
            // Re-enable process button after completion
            processButton.disabled = false;
            processButton.textContent = 'Process Video';
        });
    });
});