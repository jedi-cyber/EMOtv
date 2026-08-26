// script.js
const ws = new WebSocket(`ws://${window.location.host}/ws/emotions`);
ws.onmessage = function(event) {
    try {
        const data = JSON.parse(event.data);
        document.getElementById('emotion-display').textContent =
            `${data.emotion} (${(data.confidence * 100).toFixed(1)}%)`;
        document.getElementById('fps').textContent = data.fps.toFixed(1);
        document.getElementById('faces').textContent = data.faces;
    } catch (e) {
        console.error('Error parsing WebSocket data:', e);
    }
};

setInterval(() => {
    fetch('/stats')
        .then(res => res.json())
        .then(data => {
            document.getElementById('cpu').textContent = data.cpu_percent.toFixed(1) + '%';
            document.getElementById('ram').textContent = data.ram_mb.toFixed(1) + ' MB';
        })
        .catch(console.error);
}, 2000);

console.log('EMOtv Web Interface cargada.');