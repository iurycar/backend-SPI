import { state, HANDLE_SIZE, getClassColor } from './state.js';

const viewportWrapper = document.getElementById('viewportWrapper');
const canvas = document.getElementById('viewport');
const ctx = canvas.getContext('2d');
const zoomLevelDisplay = document.getElementById('zoomLevelDisplay');

export function getCanvasElements() {
    return { canvas, ctx, viewportWrapper };
}

export function resizeCanvasToContainer() {
    if (!viewportWrapper) return;
    const rect = viewportWrapper.getBoundingClientRect();
    
    // Math.floor previne oscilação de subpixels decimais que esticam o layout
    const newWidth = Math.floor(rect.width);
    const newHeight = Math.floor(rect.height);

    if (newWidth > 0 && newHeight > 0) {
        if (canvas.width !== newWidth || canvas.height !== newHeight) {
            canvas.width = newWidth;
            canvas.height = newHeight;
        }
    }
}

export function screenToImage(screenX, screenY) {
    return {
        x: (screenX - state.panX) / state.currentZoom,
        y: (screenY - state.panY) / state.currentZoom
    };
}

export function fitToScreen() {
    if (!state.loadedImage.width || !state.loadedImage.height || !viewportWrapper) return;
    
    resizeCanvasToContainer();

    const padding = 32;
    const availableW = Math.max(10, canvas.width - padding);
    const availableH = Math.max(10, canvas.height - padding);

    const scaleX = availableW / state.loadedImage.width;
    const scaleY = availableH / state.loadedImage.height;
    state.currentZoom = Math.min(scaleX, scaleY);

    state.panX = (canvas.width - (state.loadedImage.width * state.currentZoom)) / 2;
    state.panY = (canvas.height - (state.loadedImage.height * state.currentZoom)) / 2;

    clampPan();
    updateZoomDisplay();
    renderCanvas();
}

export function applyZoom(newZoom, mouseX = canvas.width / 2, mouseY = canvas.height / 2) {
    const clamped = Math.min(Math.max(newZoom, state.minZoom), state.maxZoom);
    if (clamped === state.currentZoom) return;

    state.panX = mouseX - (mouseX - state.panX) * (clamped / state.currentZoom);
    state.panY = mouseY - (mouseY - state.panY) * (clamped / state.currentZoom);
    state.currentZoom = clamped;

    clampPan(); // Trava os limites após zoom
    updateZoomDisplay();
    renderCanvas();
}

function updateZoomDisplay() {
    if (zoomLevelDisplay) {
        zoomLevelDisplay.innerText = `${Math.round(state.currentZoom * 100)}%`;
    }
}

export function getBoxCoords(b) {
    const w = b.width * state.loadedImage.width;
    const h = b.height * state.loadedImage.height;
    const x = (b.x_center * state.loadedImage.width) - (w / 2);
    const y = (b.y_center * state.loadedImage.height) - (h / 2);
    return { x, y, w, h };
}

export function getBoxAt(imgPos) {
    for (let i = state.currentBoxes.length - 1; i >= 0; i--) {
        const b = state.currentBoxes[i];
        if (!b.valid) continue;
        const { x, y, w, h } = getBoxCoords(b);
        if (imgPos.x >= x && imgPos.x <= x + w && imgPos.y >= y && imgPos.y <= y + h) {
            return b;
        }
    }
    return null;
}

export function getHandleUnderMouse(imgPos, b) {
    const { x, y, w, h } = getBoxCoords(b);
    const handles = {
        tl: { x, y },
        tr: { x: x + w, y },
        bl: { x, y: y + h },
        br: { x: x + w, y: y + h }
    };
    const tolerance = (HANDLE_SIZE * 1.5) / state.currentZoom;

    for (const [key, pt] of Object.entries(handles)) {
        if (Math.abs(imgPos.x - pt.x) <= tolerance && Math.abs(imgPos.y - pt.y) <= tolerance) {
            return key;
        }
    }
    return null;
}

export function drawHandle(hx, hy) {
    const size = HANDLE_SIZE / state.currentZoom;
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2 / state.currentZoom;
    ctx.fillRect(hx - size / 2, hy - size / 2, size, size);
    ctx.strokeRect(hx - size / 2, hy - size / 2, size, size);
}

export function renderCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!state.loadedImage.src || !state.loadedImage.width) return;

    ctx.save();
    ctx.translate(state.panX, state.panY);
    ctx.scale(state.currentZoom, state.currentZoom);

    // Imagem base
    ctx.drawImage(state.loadedImage, 0, 0);

    // Caixas anotadas
    state.currentBoxes.forEach(b => {
        if (!b.valid) return;
        const { x, y, w, h } = getBoxCoords(b);
        const isSelected = state.selectedBox && state.selectedBox.box_id === b.box_id;
        const isHovered = state.hoveredBox && state.hoveredBox.box_id === b.box_id;
        const [r, g, bColor] = getClassColor(b.class_id);

        let fillAlpha = isSelected ? 0.35 : (isHovered ? 0.25 : 0.15);
        ctx.fillStyle = `rgba(${r}, ${g}, ${bColor}, ${fillAlpha})`;
        ctx.fillRect(x, y, w, h);

        ctx.lineWidth = (isSelected ? 3 : (isHovered ? 2.5 : 1.5)) / state.currentZoom;
        ctx.strokeStyle = isSelected ? '#f59e0b' : `rgb(${r}, ${g}, ${bColor})`;
        ctx.strokeRect(x, y, w, h);

        if (isSelected) {
            drawHandle(x, y);
            drawHandle(x + w, y);
            drawHandle(x, y + h);
            drawHandle(x + w, y + h);
        }
    });

    // Caixa sendo desenhada
    if (state.isDrawing) {
        const curW = state.currentMouseImgPos.x - state.drawStart.x;
        const curH = state.currentMouseImgPos.y - state.drawStart.y;
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 2 / state.currentZoom;
        ctx.setLineDash([4 / state.currentZoom, 4 / state.currentZoom]);
        ctx.strokeRect(state.drawStart.x, state.drawStart.y, curW, curH);
        ctx.setLineDash([]);
    }

    ctx.restore();
}

export function moveBox(box, pos) {
    const w = box.width * state.loadedImage.width;
    const h = box.height * state.loadedImage.height;

    let newX = pos.x - state.dragOffset.x;
    let newY = pos.y - state.dragOffset.y;

    newX = Math.max(0, Math.min(state.loadedImage.width - w, newX));
    newY = Math.max(0, Math.min(state.loadedImage.height - h, newY));

    box.x_center = (newX + w / 2) / state.loadedImage.width;
    box.y_center = (newY + h / 2) / state.loadedImage.height;
}

export function resizeBox(box, handle, pos) {
    let { x, y, w, h } = getBoxCoords(box);
    let x2 = x + w;
    let y2 = y + h;

    const minSize = 16; // Tamanho mínimo da caixa em pixels

    if (handle === 'tl') { x = Math.min(pos.x, x2 - minSize); y = Math.min(pos.y, y2 - minSize); }
    if (handle === 'tr') { x2 = Math.max(pos.x, x + minSize); y = Math.min(pos.y, y2 - minSize); }
    if (handle === 'bl') { x = Math.min(pos.x, x2 - minSize); y2 = Math.max(pos.y, y + minSize); }
    if (handle === 'br') { x2 = Math.max(pos.x, x + minSize); y2 = Math.max(pos.y, y + minSize); }

    const newW = x2 - x;
    const newH = y2 - y;

    box.x_center = (x + newW / 2) / state.loadedImage.width;
    box.y_center = (y + newH / 2) / state.loadedImage.height;
    box.width = newW / state.loadedImage.width;
    box.height = newH / state.loadedImage.height;
}

/**
 * Garante que a imagem não saia do enquadramento da tela.
 * Mantém sempre uma margem mínima visível (ao menos 25% da tela ocupada).
 */
export function clampPan() {
    if (!state.loadedImage.width || !state.loadedImage.height) return;

    const imgWidthScaled = state.loadedImage.width * state.currentZoom;
    const imgHeightScaled = state.loadedImage.height * state.currentZoom;

    // Se a imagem com zoom for menor que o canvas: centraliza no eixo
    // Se for maior que o canvas: impede de puxar para além das bordas (com margem de segurança)
    const marginX = Math.min(canvas.width * 0.4, 150);
    const marginY = Math.min(canvas.height * 0.4, 150);

    if (imgWidthScaled <= canvas.width) {
        state.panX = (canvas.width - imgWidthScaled) / 2;
    } else {
        const minX = canvas.width - imgWidthScaled - marginX;
        const maxX = marginX;
        state.panX = Math.min(Math.max(state.panX, minX), maxX);
    }

    if (imgHeightScaled <= canvas.height) {
        state.panY = (canvas.height - imgHeightScaled) / 2;
    } else {
        const minY = canvas.height - imgHeightScaled - marginY;
        const maxY = marginY;
        state.panY = Math.min(Math.max(state.panY, minY), maxY);
    }
}