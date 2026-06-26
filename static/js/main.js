/**
 * Main JavaScript — Modal + General UI
 * Interactive Teaching Platform
 */

(function () {
    'use strict';

    // ── Modal Elements ──
    const modal       = document.getElementById('contentModal');
    const modalTitle  = document.getElementById('modalTitle');
    const modalBody   = document.getElementById('modalBody');
    const modalClose  = document.getElementById('modalClose');

    if (!modal) return;

    // ── Open Modal ──
    function openModal(contentId) {
        // Get API URL from data script tag if available, else build manually
        const dataEl = document.getElementById('interactiveData');
        let apiUrl;

        if (dataEl) {
            const data = JSON.parse(dataEl.textContent);
            apiUrl = data.apiUrl.replace('/0/', `/${contentId}/`);
        } else {
            apiUrl = `/api/content/${contentId}/`;
        }

        // Show loading state
        modalTitle.textContent = 'Loading…';
        modalBody.innerHTML = `
            <div class="flex flex-col items-center justify-center gap-3 py-12 text-slate-600">
                <div class="h-9 w-9 animate-spin rounded-full border-4 border-slate-200 border-t-blue-600"></div>
                <p>Loading content…</p>
            </div>`;

        modal.classList.remove('hidden');
        modal.classList.add('flex');
        document.body.style.overflow = 'hidden';
        modalClose.focus();

        // Fetch content
        fetch(apiUrl)
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json();
            })
            .then(data => renderModal(data))
            .catch(err => {
                modalTitle.textContent = 'Error';
                modalBody.innerHTML = `
                    <div class="modal-error">
                        <i class="fa-solid fa-circle-exclamation"></i>
                        <p>Failed to load content. ${err.message}</p>
                    </div>`;
            });
    }

    // ── Render Modal Content ──
    function renderModal(data) {
        modalTitle.textContent = data.title || 'Content';

        let html = '';

        switch (data.content_type) {
            case 'text':
                html = `<div class="prose prose-slate max-w-none">${data.text_content || '<em>No text content.</em>'}</div>`;
                break;

            case 'image':
                if (data.image_url) {
                    html = `
                        <div class="rounded-xl bg-slate-50 p-3">
                            <img src="${data.image_url}" alt="${escHtml(data.title)}" class="mx-auto max-h-[65vh] rounded-lg" loading="lazy">
                        </div>`;
                } else {
                    html = noContentHtml('image');
                }
                break;

            case 'audio':
                if (data.audio_url) {
                    html = `
                        <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
                            <p class="mb-4 text-slate-600">
                                <i class="fa-solid fa-headphones"></i> Click play to listen:
                            </p>
                            <audio controls class="w-full" autoplay>
                                <source src="${data.audio_url}">
                                Your browser does not support audio.
                            </audio>
                        </div>`;
                } else {
                    html = noContentHtml('audio');
                }
                break;

            case 'video':
                if (data.video_url) {
                    html = `
                        <div class="overflow-hidden rounded-xl border border-slate-200 bg-black">
                            <video controls class="max-h-[65vh] w-full" autoplay muted>
                                <source src="${data.video_url}">
                                Your browser does not support video.
                            </video>
                        </div>`;
                } else {
                    html = noContentHtml('video');
                }
                break;

            case 'youtube':
                if (data.youtube_embed_url) {
                    const youtubeUrl = new URL(data.youtube_embed_url);
                    youtubeUrl.searchParams.set('autoplay', '1');
                    youtubeUrl.searchParams.set('playsinline', '1');
                    youtubeUrl.searchParams.set('rel', '0');
                    youtubeUrl.searchParams.set('origin', window.location.origin);
                    youtubeUrl.searchParams.set('widget_referrer', window.location.href);

                    html = `
                        <div class="aspect-video overflow-hidden rounded-xl border border-slate-200">
                            <iframe
                                src="${youtubeUrl.toString()}"
                                title="${escHtml(data.title)}"
                                class="h-full w-full"
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                referrerpolicy="strict-origin-when-cross-origin"
                                allowfullscreen>
                            </iframe>
                        </div>`;
                } else {
                    html = noContentHtml('youtube');
                }
                break;

            default:
                html = `<p>Unknown content type: ${escHtml(data.content_type)}</p>`;
        }

        modalBody.innerHTML = html;
    }

    function noContentHtml(type) {
        return `
            <div class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-rose-700">
                <i class="fa-solid fa-circle-exclamation"></i>
                <p>No ${type} content has been uploaded yet.</p>
            </div>`;
    }

    function escHtml(str) {
        return String(str).replace(/[&<>"']/g, m => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[m]));
    }

    // ── Close Modal ──
    function closeModal() {
        modal.classList.remove('flex');
        modal.classList.add('hidden');
        document.body.style.overflow = '';

        // Stop any playing media
        modal.querySelectorAll('audio, video, iframe').forEach(el => {
            if (el.tagName === 'IFRAME') {
                el.src = el.src; // reload to stop YT
            } else {
                el.pause();
            }
        });

        modalBody.innerHTML = `<div class="flex flex-col items-center justify-center gap-3 py-12 text-slate-600"><div class="h-9 w-9 animate-spin rounded-full border-4 border-slate-200 border-t-blue-600"></div><p>Loading content…</p></div>`;
        modalTitle.textContent = '';
    }

    modalClose.addEventListener('click', closeModal);

    modal.addEventListener('click', function (e) {
        if (e.target === modal) closeModal();
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !modal.classList.contains('hidden')) closeModal();
    });

    // ── Attach click events to interactive elements ──
    function getInteractiveId(el) {
        return el.getAttribute('data-content-id') || el.getAttribute('data-media-id');
    }

    function attachInteractiveClicks() {
        // Support both the current `data-content-id` markup and older
        // `data-media-id` markup stored in existing lesson content.
        document.querySelectorAll('[data-content-id], [data-media-id]').forEach(el => {
            el.addEventListener('click', function (e) {
                e.preventDefault();
                const id = getInteractiveId(this);
                if (id) openModal(id);
            });
        });
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', attachInteractiveClicks);
    } else {
        attachInteractiveClicks();
    }

    // Expose for dynamic content
    window.openInteractiveModal = openModal;

})();

// ── Student dashboard enhancements: animated progress bars + client-side filter
(function () {
    'use strict';

    function animateProgressBars() {
        document.querySelectorAll('.progress-fill').forEach(el => {
            const target = parseInt(el.getAttribute('data-progress') || '0', 10);
            let cur = 0;
            el.style.width = '0%';
            const step = Math.max(1, Math.round(target / 30));
            const id = setInterval(() => {
                cur = Math.min(target, cur + step);
                el.style.width = cur + '%';
                if (cur >= target) clearInterval(id);
            }, 12);
        });
    }

    function attachDashboardFilter() {
        const input = document.getElementById('dashboardFilter');
        const countEl = document.getElementById('dashboardCount');
        if (!input) return;

        input.addEventListener('input', function () {
            const q = this.value.trim().toLowerCase();
            const cards = Array.from(document.querySelectorAll('.dashboard-card'));
            let visible = 0;
            cards.forEach(card => {
                const title = card.getAttribute('data-title') || '';
                const ok = !q || title.indexOf(q) !== -1;
                card.style.display = ok ? '' : 'none';
                if (ok) visible++;
            });
            if (countEl) countEl.textContent = visible;
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            animateProgressBars();
            attachDashboardFilter();
        });
    } else {
        animateProgressBars();
        attachDashboardFilter();
    }

})();
