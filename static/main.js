const video = document.getElementById('video');
const message = document.getElementById('message');

// Dynamically detect host/IP based on how the page is accessed
const HOST = window.location.hostname || 'localhost';
const STREAM_URL = `http://${HOST}:8889/stream/`;

// Attempt to load the stream
video.src = STREAM_URL;

video.addEventListener('canplay', () => {
    message.style.display = 'none';
    video.play().catch(e => console.log("Autoplay blocked:", e));
});

video.addEventListener('error', (e) => {
    message.textContent = "Failed to load video stream";
    console.error("Video error:", e);
});
