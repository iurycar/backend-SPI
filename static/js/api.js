const imageMemoryCache = new Map();

export async function fetchClasses() {
    const res = await fetch('/api/classes');
    return await res.json();
}

export async function fetchConfig() {
    const res = await fetch('/api/config');
    return await res.json();
}

export async function saveConfig(source_dir, target_dir) {
    const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_dir, target_dir })
    });
    return { ok: res.ok, data: await res.json() };
}

export async function fetchSamplesCount() {
    const res = await fetch('/api/samples/count');
    const data = await res.json();
    return data.total || 0;
}

export async function fetchSamples(start, end) {
    const res = await fetch(`/api/samples?start=${start}&end=${end}`);
    return await res.json();
}

export async function fetchLabels(labelFile) {
    const res = await fetch(`/api/labels/${labelFile}`);
    return await res.json();
}

export function fetchCachedImage(filename) {
    return new Promise((resolve, reject) => {
        if (imageMemoryCache.has(filename)) {
            resolve(imageMemoryCache.get(filename));
            return;
        }
        const img = new Image();
        img.src = `/api/image/${filename}`;
        img.onload = () => {
            imageMemoryCache.set(filename, img);
            resolve(img);
        };
        img.onerror = reject;
    });
}

export function preloadNextImage(samples, currentIndex) {
    if (currentIndex + 1 < samples.length) {
        const nextFile = samples[currentIndex + 1].image_file;
        if (!imageMemoryCache.has(nextFile)) {
            const preloadImg = new Image();
            preloadImg.src = `/api/image/${nextFile}`;
            preloadImg.onload = () => imageMemoryCache.set(nextFile, preloadImg);
        }
    }
}

export function evictImageCache(filename) {
    imageMemoryCache.delete(filename);
}

export function clearImageCache() {
    imageMemoryCache.clear();
}

export async function saveAndMoveSample(payload) {
    const res = await fetch('/api/save-and-move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    return await res.json();
}

export async function deleteSample(id) {
    const res = await fetch(`/api/sample/${id}`, { method: 'DELETE' });
    return await res.json();
}