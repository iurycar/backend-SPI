import { state, getClassColor, customColors } from './state.js';
import { renderCanvas } from './canvas.js';

const classListEl = document.getElementById('classList');
const btnCursorMode = document.getElementById('btnCursorMode');

function rgbToHex([r, g, b]) {
    return "#" + [r, g, b].map(x => {
        const hex = x.toString(16);
        return hex.length === 1 ? "0" + hex : hex;
    }).join('');
}

function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? [
        parseInt(result[1], 16),
        parseInt(result[2], 16),
        parseInt(result[3], 16)
    ] : [148, 163, 184];
}

export function selectBox(box) {
    state.selectedBox = box;
    state.hoveredBox = null;
    renderCanvas();
    renderSidebar();
}

export function unselectBox() {
    state.selectedBox = null;
    state.hoveredBox = null;
    state.isDraggingBox = false;
    renderCanvas();
    renderSidebar();
}

export function renderClassesList() {
    if (!classListEl) return;
    classListEl.innerHTML = '';
    state.classes.forEach(cls => {
        const colorRgb = getClassColor(cls.id);
        const isSelected = state.selectedClassForDrawing && state.selectedClassForDrawing.id === cls.id;
        
        const row = document.createElement('div');
        row.className = `w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg border text-xs font-medium transition ${
            isSelected 
            ? 'bg-amber-500/10 border-amber-500 text-amber-600 dark:text-amber-400' 
            : 'bg-neutral-50 dark:bg-neutral-800/60 border-neutral-200 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-800 dark:text-neutral-300'
        }`;

        const selectArea = document.createElement('div');
        selectArea.className = "flex-1 flex items-center gap-2 cursor-pointer";
        selectArea.innerHTML = `
            <span id="bullet-${cls.id}" class="w-3 h-3 rounded-full flex-shrink-0" style="background-color: rgb(${colorRgb[0]}, ${colorRgb[1]}, ${colorRgb[2]})"></span>
            <span class="truncate">${cls.name}</span>
        `;
        selectArea.onclick = () => {
            state.selectedClassForDrawing = cls;
            unselectBox();
            btnCursorMode.className = "w-full py-2 px-3 rounded-lg border text-xs font-semibold flex items-center justify-between transition bg-neutral-100 dark:bg-neutral-800 border-neutral-300 dark:border-neutral-700 text-neutral-500 mb-2";
            renderClassesList();
            const canvas = document.getElementById('viewport');
            if (!state.isPanMode && canvas) canvas.style.cursor = 'crosshair';
        };

        const colorPicker = document.createElement('input');
        colorPicker.type = 'color';
        colorPicker.value = rgbToHex(colorRgb);
        colorPicker.className = 'w-5 h-5 cursor-pointer bg-transparent border-none rounded-full ml-2';
        colorPicker.title = 'Alterar cor desta classe';
        colorPicker.onclick = (e) => e.stopPropagation();
        colorPicker.oninput = (e) => {
            e.stopPropagation();
            const newRgb = hexToRgb(e.target.value);
            customColors[cls.id] = newRgb;
            localStorage.setItem('custom_class_colors', JSON.stringify(customColors));
            
            const bullet = document.getElementById(`bullet-${cls.id}`);
            if (bullet) bullet.style.backgroundColor = `rgb(${newRgb[0]}, ${newRgb[1]}, ${newRgb[2]})`;
            renderCanvas();
            renderSidebar();
        };

        row.appendChild(selectArea);
        row.appendChild(colorPicker);
        classListEl.appendChild(row);
    });
}

export function renderSidebar() {
    const list = document.getElementById('detectionsList');
    if (!list) return;
    list.innerHTML = '';

    const activeBoxes = state.currentBoxes.filter(b => b.valid);
    const countEl = document.getElementById('detCount');
    if (countEl) countEl.innerText = `${activeBoxes.length} objetos`;

    const totalItems = state.currentBoxes.length;
    const totalPages = Math.max(1, Math.ceil(totalItems / state.detectionsPerPage));

    // Ajusta a página atual caso caixas tenham sido deletadas
    if (state.detectionsPage > totalPages) {
        state.detectionsPage = totalPages;
    }

    // Controles de paginação
    const paginationContainer = document.getElementById('detectionsPagination');
    const btnPrev = document.getElementById('btnDetectionsPrev');
    const btnNext = document.getElementById('btnDetectionsNext');
    const pageIndicator = document.getElementById('detectionsPageIndicator');

    if (paginationContainer) {
        if (totalPages > 1) {
            paginationContainer.classList.remove('hidden');
            paginationContainer.classList.add('flex');
            
            pageIndicator.innerText = `${state.detectionsPage} / ${totalPages}`;
            btnPrev.disabled = state.detectionsPage <= 1;
            btnNext.disabled = state.detectionsPage >= totalPages;

            btnPrev.onclick = () => {
                if (state.detectionsPage > 1) {
                    state.detectionsPage--;
                    renderSidebar();
                }
            };

            btnNext.onclick = () => {
                if (state.detectionsPage < totalPages) {
                    state.detectionsPage++;
                    renderSidebar();
                }
            };
        } else {
            paginationContainer.classList.add('hidden');
            paginationContainer.classList.remove('flex');
        }
    }

    // Fatia apenas os itens da página atual (ex: 0 a 10, 10 a 20)
    const startIndex = (state.detectionsPage - 1) * state.detectionsPerPage;
    const endIndex = startIndex + state.detectionsPerPage;
    const currentSlice = state.currentBoxes.slice(startIndex, endIndex);

    currentSlice.forEach((b) => {
        const item = document.createElement('div');
        const isSelected = state.selectedBox && state.selectedBox.box_id === b.box_id;
        const [r, g, bColor] = getClassColor(b.class_id);

        const confBadge = (b.confidence !== null && b.confidence !== undefined)
            ? `<span class="text-[10px] bg-neutral-200 dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 px-1.5 py-0.5 rounded text-neutral-800 dark:text-neutral-200 font-mono font-bold">${Math.round(b.confidence * 100)}%</span>`
            : '';

        item.className = `p-2 rounded-lg border text-xs transition flex flex-col gap-1.5 ${
            !b.valid 
            ? 'bg-neutral-100 dark:bg-neutral-900 border-neutral-200 dark:border-neutral-800 opacity-40' 
            : isSelected 
            ? 'bg-amber-500/10 border-amber-500 text-amber-600 dark:text-amber-300 shadow-sm' 
            : 'bg-neutral-50 dark:bg-neutral-800/60 border-neutral-200 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300'
        }`;

        const topRow = document.createElement('div');
        topRow.className = "flex items-center justify-between gap-2";

        const leftGroup = document.createElement('div');
        leftGroup.className = "flex items-center gap-2 flex-1 min-w-0";

        const bullet = document.createElement('span');
        bullet.className = "w-2.5 h-2.5 rounded-full flex-shrink-0";
        bullet.style.backgroundColor = `rgb(${r}, ${g}, ${bColor})`;

        const selectCls = document.createElement('select');
        selectCls.className = "bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 text-neutral-800 dark:text-neutral-200 rounded px-2 py-0.5 text-xs font-semibold focus:outline-none truncate";
        selectCls.onclick = (e) => e.stopPropagation();
        selectCls.onchange = (e) => {
            e.stopPropagation();
            const newClassId = parseInt(e.target.value);
            const foundCls = state.classes.find(c => c.id === newClassId);
            b.class_id = newClassId;
            b.class_name = foundCls ? foundCls.name : `Classe ${newClassId}`;
            renderCanvas();
            renderSidebar();
        };

        state.classes.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id;
            opt.innerText = c.name;
            if (c.id === b.class_id) opt.selected = true;
            selectCls.appendChild(opt);
        });

        leftGroup.appendChild(bullet);
        leftGroup.appendChild(selectCls);

        const rightGroup = document.createElement('div');
        rightGroup.className = "flex items-center gap-1.5 flex-shrink-0";
        if (confBadge) rightGroup.innerHTML += confBadge;

        const btnDelete = document.createElement('button');
        if (b.isManual) {
            // Para caixas criadas pelo usuário: sempre botão de apagar definitivo
            btnDelete.className = 'p-1 rounded transition text-xs font-bold hover:bg-rose-500/20 text-rose-500';
            btnDelete.title = "Excluir anotação definitivamente";
            btnDelete.innerText = "✕";

            btnDelete.onclick = (e) => {
                e.stopPropagation();

                // Remove definitivamente do array de caixas
                const idx = state.currentBoxes.findIndex(box => box.box_id === b.box_id);
                if (idx !== -1) {
                    state.currentBoxes.splice(idx, 1);
                }

                if (state.selectedBox && state.selectedBox.box_id === b.box_id) {
                    unselectBox();
                } else {
                    renderCanvas();
                    renderSidebar();
                }
            };
        } else {
            // Para predições importadas: alternância entre desativar (✕) e restaurar (↺)
            btnDelete.className = `p-1 rounded transition text-xs font-bold ${
                b.valid ? 'hover:bg-rose-500/20 text-rose-500' : 'hover:bg-emerald-500/20 text-emerald-500'
            }`;
            btnDelete.title = b.valid ? "Excluir anotação" : "Restaurar anotação";
            btnDelete.innerText = b.valid ? "✕" : "↺";

            btnDelete.onclick = (e) => {
                e.stopPropagation();
                b.valid = !b.valid;
                if (!b.valid && state.selectedBox && state.selectedBox.box_id === b.box_id) {
                    unselectBox();
                } else {
                    renderCanvas();
                    renderSidebar();
                }
            };
        }

        rightGroup.appendChild(btnDelete);
        topRow.appendChild(leftGroup);
        topRow.appendChild(rightGroup);
        item.appendChild(topRow);

        item.onclick = () => {
            if (!b.valid) return;
            selectBox(b);
        };

        list.appendChild(item);
    });
}