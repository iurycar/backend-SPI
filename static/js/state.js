export const state = {
    totalCount: 0,
    samples: [],
    classes: [],
    currentIndex: 0,
    currentBoxes: [],
    loadedImage: new Image(),
    
    // Zoom e Pan
    panX: 0,
    panY: 0,
    currentZoom: 1.0,
    minZoom: 0.1,
    maxZoom: 5.0,
    
    // Interações
    selectedClassForDrawing: null,
    selectedBox: null,
    hoveredBox: null,
    isDrawing: false,
    isDraggingBox: false,
    isPanMode: false,
    isPanning: false,
    dragOffset: { x: 0, y: 0 },
    drawStart: { x: 0, y: 0 },
    currentMouseImgPos: { x: 0, y: 0 },
    panStart: { x: 0, y: 0 },
    activeHandle: null,
    
    // Split
    manualSelectedSplit: 'train',

    // Paginação das detecções do frame
    detectionsPage: 1,
    detectionsPerPage: 15
};

export const HANDLE_SIZE = 8;

export const DEFAULT_PALETTE = {
    0: [34, 197, 94],
    1: [239, 68, 68],
    2: [0, 98, 255],
    3: [255, 0, 136],
    4: [6, 182, 212],
    5: [255, 180, 0],
    6: [255, 0, 0],
    7: [0, 0, 255],
    8: [225, 0, 255],
    9: [255, 255, 148],
    10: [255, 128, 0],
    11: [255, 150, 80],
    12: [128, 0, 128]
};

export const customColors = JSON.parse(localStorage.getItem('custom_class_colors') || '{}');

export function getClassColor(classId) {
    if (customColors[classId]) return customColors[classId];
    return DEFAULT_PALETTE[classId] || [148, 163, 184];
}