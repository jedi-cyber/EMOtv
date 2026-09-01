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

const stopCameraButton = document.getElementById('stop-camera');
const startCameraButton = document.getElementById('start-camera');
const cameraStatus = document.getElementById('camera-status');

async function controlCamera(action) {
    let response = await fetch(`/control/${action}`, {
        method: 'POST',
        cache: 'no-store',
    });

    // Compatibilidad con servidores anteriores que solo exponen GET.
    if (response.status === 404) {
        response = await fetch(`/control?action=${action}`, {
            cache: 'no-store',
        });
    }

    if (!response.ok) {
        throw new Error(`No se pudo ${action} la cámara.`);
    }
}

startCameraButton.addEventListener('click', async () => {
    startCameraButton.disabled = true;
    cameraStatus.textContent = 'Encendiendo cámara...';

    try {
        await controlCamera('start');
        document.getElementById('video').src = `/video_feed?ts=${Date.now()}`;
        cameraStatus.textContent = 'Cámara encendida.';
    } catch (error) {
        console.error(error);
        cameraStatus.textContent = 'No se pudo encender la cámara.';
    } finally {
        startCameraButton.disabled = false;
    }
});

stopCameraButton.addEventListener('click', async () => {
    stopCameraButton.disabled = true;
    cameraStatus.textContent = 'Apagando cámara...';

    try {
        await controlCamera('stop');
        document.getElementById('video').removeAttribute('src');
        cameraStatus.textContent = 'Cámara apagada.';
    } catch (error) {
        console.error(error);
        stopCameraButton.disabled = false;
        cameraStatus.textContent = 'No se pudo apagar la cámara.';
    }
});

console.log('EMOtv Web Interface cargada.');
