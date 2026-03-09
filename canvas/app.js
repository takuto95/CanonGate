const drawCanvas = document.getElementById('draw-canvas');
const bgCanvas = document.getElementById('bg-canvas');
const ctx = drawCanvas.getContext('2d');
const bgCtx = bgCanvas.getContext('2d');

let drawing = false;
let currentTool = 'draw';
let color = '#00ddee';
let size = 5;
let ws;

function resize() {
    drawCanvas.width = window.innerWidth;
    drawCanvas.height = window.innerHeight;
    bgCanvas.width = window.innerWidth;
    bgCanvas.height = window.innerHeight;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
}
window.addEventListener('resize', resize);
resize();

// UI Controls
document.getElementById('btn-draw').onclick = (e) => setTool('draw', e.target);
document.getElementById('btn-erase').onclick = (e) => setTool('erase', e.target);
document.getElementById('btn-clear').onclick = () => {
    ctx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
};
document.getElementById('color-picker').onchange = (e) => color = e.target.value;
document.getElementById('size-picker').onchange = (e) => size = e.target.value;

function setTool(tool, btn) {
    currentTool = tool;
    document.querySelectorAll('#tools button').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
}

// Drawing Logic
function getPos(e) {
    const rect = drawCanvas.getBoundingClientRect();
    let clientX, clientY;
    if (e.touches && e.touches.length > 0) {
        clientX = e.touches[0].clientX;
        clientY = e.touches[0].clientY;
    } else {
        clientX = e.clientX;
        clientY = e.clientY;
    }

    // Scale correction for tablet devices where CSS pixel size might not match internal canvas drawing size
    const scaleX = drawCanvas.width / rect.width;
    const scaleY = drawCanvas.height / rect.height;

    return {
        x: (clientX - rect.left) * scaleX,
        y: (clientY - rect.top) * scaleY
    };
}

function startDraw(e) {
    drawing = true;
    const pos = getPos(e);
    ctx.beginPath();
    ctx.moveTo(pos.x, pos.y);
    ctx.lineWidth = size;
    ctx.strokeStyle = currentTool === 'erase' ? '#0a0a14' : color;
    if (currentTool === 'erase') {
        ctx.globalCompositeOperation = 'destination-out';
    } else {
        ctx.globalCompositeOperation = 'source-over';
    }
    e.preventDefault();
}

function doDraw(e) {
    if (!drawing) return;
    const pos = getPos(e);
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
    e.preventDefault();
}

function stopDraw(e) {
    if (!drawing) return;
    drawing = false;
    ctx.closePath();
    e.preventDefault();
}

drawCanvas.addEventListener('mousedown', startDraw);
drawCanvas.addEventListener('mousemove', doDraw);
drawCanvas.addEventListener('mouseup', stopDraw);
drawCanvas.addEventListener('mouseout', stopDraw);

drawCanvas.addEventListener('touchstart', startDraw, { passive: false });
drawCanvas.addEventListener('touchmove', doDraw, { passive: false });
drawCanvas.addEventListener('touchend', stopDraw, { passive: false });

// WebSocket Connection to CanonGate
function connectWS() {
    const wsHost = (window.location.protocol === 'file:') ? 'localhost' : window.location.hostname;
    ws = new WebSocket(`ws://${wsHost}:8082`);

    ws.onopen = () => {
        document.getElementById('status').innerText = 'Connected: Canon Online';
        document.getElementById('status').style.color = '#00ff00';
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'canvas_bg_update') {
                // Receive generated image from AI
                const img = new Image();
                img.onload = () => {
                    bgCtx.clearRect(0, 0, bgCanvas.width, bgCanvas.height);
                    bgCtx.drawImage(img, 0, 0, bgCanvas.width, bgCanvas.height);
                    showToast("New image received from Canon");
                };
                img.src = msg.image_b64;
            } else if (msg.type === 'hub_toast') {
                showToast(msg.message);
            }
        } catch (e) { console.error('WS Error:', e); }
    };

    ws.onclose = () => {
        document.getElementById('status').innerText = 'Disconnected: Reconnecting...';
        document.getElementById('status').style.color = 'red';
        setTimeout(connectWS, 2000);
    };
}
connectWS();

// Generate Request
document.getElementById('btn-generate').onclick = () => {
    const prompt = document.getElementById('prompt-input').value;
    if (!prompt) {
        showToast("Please enter a prompt!");
        return;
    }

    // Combine bg + draw or just send draw layer
    // For rough sketch to img2img, sending the transparent drawing layer is fine.
    // Or we merge them onto a temp canvas to send a solid black background.
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = drawCanvas.width;
    tempCanvas.height = drawCanvas.height;
    const tCtx = tempCanvas.getContext('2d');

    // Fill white or black depending on controlnet needs
    tCtx.fillStyle = '#000000';
    tCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
    // Draw bg if exists? We skip bg for now to just send the sketch.
    tCtx.drawImage(drawCanvas, 0, 0);

    const image_b64 = tempCanvas.toDataURL('image/png');

    if (ws && ws.readyState === WebSocket.OPEN) {
        const btn = document.getElementById('btn-generate');
        const oldText = btn.innerText;
        btn.innerText = "SENDING...";
        btn.style.opacity = '0.7';

        ws.send(JSON.stringify({
            type: 'canvas_generate',
            prompt: prompt,
            image_b64: image_b64
        }));
        showToast("Sending sketch to Canon...");

        setTimeout(() => {
            btn.innerText = oldText;
            btn.style.opacity = '1';
        }, 2000);
    }
};

function showToast(text) {
    const toast = document.getElementById('toast');
    toast.innerText = text;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}
