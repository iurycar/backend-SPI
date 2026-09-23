import { state } from './state.js';
import * as api from './api.js';
import * as cvs from './canvas.js';
import * as sb from './sidebar.js';

const { canvas, viewportWrapper } = cvs.getCanvasElements();

// Controles de Split
const chkAutoValidation = document.getElementById('chkAutoValidation');
const manualSplitSelector = document.getElementById('manualSplitSelector');
const btnSelectTrain = document.getElementById('btnSelectTrain');
const btnSelectVal = document.getElementById('btnSelectVal');

// Controles de Zoom & Pan
const btnZoomIn = document.getElementById('btnZoomIn');
const btnZoomOut = document.getElementById('btnZoomOut');
const btnFitScreen = document.getElementById('btnFitScreen');
const btnResetZoom = document.getElementById('btnResetZoom');
const btnPanTool = document.getElementById('btnPanTool');
const btnCursorMode = document.getElementById('btnCursorMode');

// Modal de Configuração
const modal = document.getElementById('configModal');
const inputSource = document.getElementById('inputSourceDir');
const inputTarget = document.getElementById('inputTargetDir');

// Tema Claro/Escuro
const btnThemeToggle = document.getElementById('btnThemeToggle');
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'dark') {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
}

btnThemeToggle.onclick = () => {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
};

// Funções de Carregamento
async function init() {
    initTheme();
    state.classes = await api.fetchClasses();
    sb.renderClassesList();

    const cfg = await api.fetchConfig();
    inputSource.value = cfg.source_dir;
    inputTarget.value = cfg.target_dir;

    await fetchTotalCount();
}

async function fetchTotalCount() {
    state.totalCount = await api.fetchSamplesCount();
    document.getElementById('totalPhotosCount').innerText = state.totalCount;

    const counter = document.getElementById('counter');
    const startInput = document.getElementById('inputRangeStart');
    const endInput = document.getElementById('inputRangeEnd');

    if (state.totalCount > 0) {
        if (!startInput.value) startInput.value = 1;
        if (!endInput.value) endInput.value = Math.min(state.totalCount, 100);
        counter.innerText = `Aguardando seleção do lote (1 a ${state.totalCount})`;
    } else {
        counter.innerText = "Nenhuma foto encontrada no diretório";
    }
}

async function loadBatch() {
    if (state.totalCount === 0) {
        alert("Não há fotos disponíveis na pasta configurada.");
        return;
    }

    const start = parseInt(document.getElementById('inputRangeStart').value);
    let end = parseInt(document.getElementById('inputRangeEnd').value);

    if (isNaN(start) || isNaN(end) || start < 1 || end < start) {
        alert("Preencha um intervalo válido.");
        return;
    }

    end = Math.min(end, state.totalCount);
    document.getElementById('inputRangeEnd').value = end;

    document.getElementById('counter').innerText = `Carregando amostras ${start} até ${end}...`;
    state.samples = await api.fetchSamples(start, end);
    api.clearImageCache();

    if (state.samples.length === 0) {
        document.getElementById('counter').innerText = "Nenhuma foto carregada para este intervalo.";
        cvs.renderCanvas();
        sb.renderSidebar();
        return;
    }

    state.detectionsPage = 1;

    loadSample(0);
}

document.getElementById('btnApplyRange').onclick = loadBatch;

async function loadSample(index) {
    if (index < 0 || index >= state.samples.length) return;
    state.currentIndex = index;
    sb.unselectBox();

    const sample = state.samples[state.currentIndex];
    document.getElementById('counter').innerText = `Foto ${state.currentIndex + 1} de ${state.samples.length} carregadas (${sample.image_file})`;

    state.currentBoxes = await api.fetchLabels(sample.label_file);

    try {
        state.loadedImage = await api.fetchCachedImage(sample.image_file);
        cvs.fitToScreen();
        sb.renderSidebar();
        api.preloadNextImage(state.samples, state.currentIndex);
    } catch (err) {
        console.error("Erro ao renderizar imagem:", err);
    }
}

// Modal de Configuração
document.getElementById('btnOpenConfig').onclick = () => modal.classList.remove('hidden');
document.getElementById('btnCloseConfig').onclick = () => modal.classList.add('hidden');
document.getElementById('btnCancelConfig').onclick = () => modal.classList.add('hidden');

document.getElementById('btnSaveConfig').onclick = async () => {
    const { ok, data } = await api.saveConfig(inputSource.value, inputTarget.value);
    if (ok) {
        modal.classList.add('hidden');
        state.samples = [];
        api.clearImageCache();
        cvs.renderCanvas();
        sb.renderSidebar();
        await fetchTotalCount();
    } else {
        alert(data.error || "Erro ao salvar diretórios");
    }
};

// Cursor Mode
btnCursorMode.onclick = () => {
    state.selectedClassForDrawing = null;
    btnCursorMode.className = "w-full py-2 px-3 rounded-lg border text-xs font-semibold flex items-center justify-between transition bg-neutral-200 dark:bg-neutral-800 border-neutral-400 dark:border-neutral-600 text-neutral-900 dark:text-white mb-2";
    sb.renderClassesList();
    if (!state.isPanMode) canvas.style.cursor = 'default';
};

// Gestão de Zoom e Pan
btnZoomIn.onclick = () => cvs.applyZoom(state.currentZoom * 1.25);
btnZoomOut.onclick = () => cvs.applyZoom(state.currentZoom * 0.8);
btnResetZoom.onclick = () => cvs.applyZoom(1.0);
btnFitScreen.onclick = () => cvs.fitToScreen();

viewportWrapper.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const factor = e.deltaY < 0 ? 1.15 : 0.85;
    cvs.applyZoom(state.currentZoom * factor, e.clientX - rect.left, e.clientY - rect.top);
}, { passive: false });

window.addEventListener('resize', cvs.resizeCanvasToContainer);

function togglePanMode(active) {
    state.isPanMode = (active !== undefined) ? active : !state.isPanMode;

    if (state.isPanMode) {
        if (btnPanTool) btnPanTool.className = "px-3 py-1 bg-amber-500 text-white text-xs font-semibold rounded transition flex items-center gap-1 shadow-sm";
        canvas.style.cursor = 'grab';
        sb.unselectBox();
    } else {
        if (btnPanTool) btnPanTool.className = "px-3 py-1 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-neutral-800 dark:text-neutral-200 text-xs font-semibold rounded transition flex items-center gap-1";
        canvas.style.cursor = state.selectedClassForDrawing ? 'crosshair' : 'default';
    }
}

if (btnPanTool) btnPanTool.onclick = () => togglePanMode();

window.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && !e.repeat && e.target.tagName !== 'INPUT') {
        e.preventDefault();
        togglePanMode(true);
    }
});

window.addEventListener('keyup', (e) => {
    if (e.code === 'Space' && e.target.tagName !== 'INPUT') {
        e.preventDefault();
        togglePanMode(false);
    }
});

// Eventos do Mouse no Canvas Virtual
canvas.addEventListener('mousedown', (e) => {
    const rect = canvas.getBoundingClientRect();
    const screenX = e.clientX - rect.left;
    const screenY = e.clientY - rect.top;

    if (state.isPanMode || e.button === 1) {
        state.isPanning = true;
        state.panStart = { x: screenX - state.panX, y: screenY - state.panY };
        canvas.style.cursor = 'grabbing';
        e.preventDefault();
        return;
    }

    const imgPos = cvs.screenToImage(screenX, screenY);

    if (state.selectedBox) {
        const handle = cvs.getHandleUnderMouse(imgPos, state.selectedBox);
        if (handle) {
            state.activeHandle = handle;
            return;
        }
    }

    if (state.selectedClassForDrawing) {
        const clampedX = Math.max(0, Math.min(state.loadedImage.width, imgPos.x));
        const clampedY = Math.max(0, Math.min(state.loadedImage.height, imgPos.y));
        state.isDrawing = true;
        state.drawStart = { x: clampedX, y: clampedY };
        state.currentMouseImgPos = { x: clampedX, y: clampedY };
        return;
    }

    const hit = cvs.getBoxAt(imgPos);
    if (hit) {
        sb.selectBox(hit);
        state.isDraggingBox = true;
        const coords = cvs.getBoxCoords(hit);
        state.dragOffset = { x: imgPos.x - coords.x, y: imgPos.y - coords.y };
    } else {
        sb.unselectBox();
    }
});

window.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const screenX = e.clientX - rect.left;
    const screenY = e.clientY - rect.top;

    if (state.isPanning) {
        state.panX = screenX - state.panStart.x;
        state.panY = screenY - state.panStart.y;
        cvs.clampPan();
        cvs.renderCanvas();
        return;
    }

    if (state.isPanMode) {
        canvas.style.cursor = 'grab';
        return;
    }

    const imgPos = cvs.screenToImage(screenX, screenY);
    state.currentMouseImgPos = {
        x: Math.max(0, Math.min(state.loadedImage.width, imgPos.x)),
        y: Math.max(0, Math.min(state.loadedImage.height, imgPos.y))
    };

    if (state.activeHandle && state.selectedBox) {
        cvs.resizeBox(state.selectedBox, state.activeHandle, state.currentMouseImgPos);
        cvs.renderCanvas();
        return;
    }

    if (state.isDraggingBox && state.selectedBox) {
        cvs.moveBox(state.selectedBox, state.currentMouseImgPos);
        cvs.renderCanvas();
        return;
    }

    if (state.isDrawing) {
        cvs.renderCanvas();
        return;
    }

    if (e.target === canvas) {
        if (state.selectedBox) {
            const handle = cvs.getHandleUnderMouse(imgPos, state.selectedBox);
            if (handle) {
                canvas.style.cursor = (handle === 'tl' || handle === 'br') ? 'nwse-resize' : 'nesw-resize';
                return;
            }
        }

        if (!state.selectedClassForDrawing) {
            const hit = cvs.getBoxAt(imgPos);
            canvas.style.cursor = hit ? (state.selectedBox && state.selectedBox.box_id === hit.box_id ? 'move' : 'pointer') : 'default';

            if (!state.selectedBox && hit !== state.hoveredBox) {
                state.hoveredBox = hit;
                cvs.renderCanvas();
            }
        }
    }
});

window.addEventListener('mouseup', (e) => {
    if (state.isPanning) {
        state.isPanning = false;
        canvas.style.cursor = state.isPanMode ? 'grab' : (state.selectedClassForDrawing ? 'crosshair' : 'default');
        return;
    }

    if (state.activeHandle) {
        state.activeHandle = null;
        sb.renderSidebar();
        return;
    }

    if (state.isDraggingBox) {
        state.isDraggingBox = false;
        sb.renderSidebar();
        return;
    }

    if (state.isDrawing) {
        state.isDrawing = false;
        const minX = Math.min(state.drawStart.x, state.currentMouseImgPos.x);
        const maxX = Math.max(state.drawStart.x, state.currentMouseImgPos.x);
        const minY = Math.min(state.drawStart.y, state.currentMouseImgPos.y);
        const maxY = Math.max(state.drawStart.y, state.currentMouseImgPos.y);
        const w = maxX - minX;
        const h = maxY - minY;

        const minSize = 16; // Tamanho mínimo da caixa em pixels

        if (w >= minSize && h >= minSize && state.selectedClassForDrawing) {
            const newBox = {
                box_id: Date.now(),
                class_id: state.selectedClassForDrawing.id,
                class_name: state.selectedClassForDrawing.name,
                x_center: (minX + w / 2) / state.loadedImage.width,
                y_center: (minY + h / 2) / state.loadedImage.height,
                width: w / state.loadedImage.width,
                height: h / state.loadedImage.height,
                confidence: null,
                valid: true,
                isManual: true
            };
            state.currentBoxes.push(newBox);
            // Garante que o painel mostre a página onde a nova caixa foi parar
            state.detectionsPage = Math.ceil(state.currentBoxes.length / state.detectionsPerPage);
            sb.selectBox(newBox);
        }
        cvs.renderCanvas();
        sb.renderSidebar();
    }
});

// Split Manual vs Auto
chkAutoValidation.addEventListener('change', (e) => {
    if (e.target.checked) {
        manualSplitSelector.classList.add('hidden');
        manualSplitSelector.classList.remove('flex');
    } else {
        manualSplitSelector.classList.remove('hidden');
        manualSplitSelector.classList.add('flex');
    }
});

function setManualSplit(mode) {
    state.manualSelectedSplit = mode;
    const active = "h-full px-2.5 rounded-md bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white text-xs font-semibold shadow-sm transition";
    const inactive = "h-full px-2.5 rounded-md text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white text-xs transition";

    btnSelectTrain.className = mode === 'train' ? active : inactive;
    btnSelectVal.className = mode === 'val' ? active : inactive;
}

btnSelectTrain.onclick = () => setManualSplit('train');
btnSelectVal.onclick = () => setManualSplit('val');

// Salvar Amostras
async function handleSaveAndAdvance(applyAugmentation = false) {
    if (state.samples.length === 0) return;
    const sample = state.samples[state.currentIndex];

    const btnAug = document.getElementById('btnSalvarComAugment');
    const originalText = btnAug.innerText;
    if (applyAugmentation) {
        btnAug.innerText = 'Processando...';
        btnAug.disabled = true;
    }

    const allowValidationSplit = chkAutoValidation.checked;

    try {
        await api.saveAndMoveSample({
            id: sample.id,
            image_file: sample.image_file,
            label_file: sample.label_file,
            boxes: state.currentBoxes,
            apply_augmentation: applyAugmentation,
            allow_validation_split: allowValidationSplit,
            split: allowValidationSplit ? null : state.manualSelectedSplit
        });

        api.evictImageCache(sample.image_file);
        state.samples.splice(state.currentIndex, 1);
        state.totalCount = Math.max(0, state.totalCount - 1);
        document.getElementById('totalPhotosCount').innerText = state.totalCount;

        if (state.samples.length === 0) {
            document.getElementById('counter').innerText = "Lote concluído! Selecione um novo intervalo acima.";
            cvs.renderCanvas();
            sb.renderSidebar();
        } else {
            loadSample(Math.min(state.currentIndex, state.samples.length - 1));
        }
    } catch (err) {
        console.error("Erro ao salvar amostra:", err);
        alert("Erro ao salvar amostra.");
    } finally {
        if (applyAugmentation) {
            btnAug.innerText = originalText;
            btnAug.disabled = false;
        }
    }
}

document.getElementById('btnSalvarAvancar').onclick = () => handleSaveAndAdvance(false);
document.getElementById('btnSalvarComAugment').onclick = () => handleSaveAndAdvance(true);

document.getElementById('btnPrev').onclick = () => {
    if (state.currentIndex > 0) loadSample(state.currentIndex - 1);
};
document.getElementById('btnNext').onclick = () => {
    if (state.currentIndex < state.samples.length - 1) loadSample(state.currentIndex + 1);
};

document.getElementById('btnDescartarAmostra').onclick = async () => {
    if (confirm("Deseja apagar definitivamente esta imagem e labels da pasta de origem?")) {
        const sample = state.samples[state.currentIndex];
        await api.deleteSample(sample.id);

        api.evictImageCache(sample.image_file);
        state.samples.splice(state.currentIndex, 1);
        state.totalCount = Math.max(0, state.totalCount - 1);
        document.getElementById('totalPhotosCount').innerText = state.totalCount;

        if (state.samples.length === 0) {
            document.getElementById('counter').innerText = "Lote concluído! Selecione um novo intervalo acima.";
            cvs.renderCanvas();
            sb.renderSidebar();
        } else {
            loadSample(Math.min(state.currentIndex, state.samples.length - 1));
        }
    }
};

init();