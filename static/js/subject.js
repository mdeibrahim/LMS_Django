(function () {
    const dataEl = document.getElementById('interactiveData');
    if (!dataEl) return;

    let apiUrl = '';
    try {
        apiUrl = JSON.parse(dataEl.textContent).apiUrl || '';
    } catch (error) {
        return;
    }
    if (!apiUrl) return;

    const resolveUrl = (contentId) => apiUrl.replace(/0\/?$/, `${contentId}/`);

    function ensureModal() {
        let modal = document.getElementById('interactiveModal');
        if (modal) return modal;

        modal = document.createElement('div');
        modal.id = 'interactiveModal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="interactiveModalTitle">
                <div class="modal-header">
                    <h3 class="modal-title" id="interactiveModalTitle">Loading...</h3>
                    <button class="modal-close" type="button" aria-label="Close"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <div class="modal-body"></div>
            </div>
        `;
        document.body.appendChild(modal);

        modal.addEventListener('click', (event) => {
            if (event.target === modal || event.target.closest('.modal-close')) {
                closeModal();
            }
        });

        return modal;
    }

    function openModal() {
        ensureModal().classList.add('modal--active');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        const modal = ensureModal();
        modal.classList.remove('modal--active');
        document.body.style.overflow = '';
    }

    function renderBody(item) {
        if (item.content_type === 'text') {
            return `<div class="modal-text-content">${item.text_content || '<p>No text content available.</p>'}</div>`;
        }
        if (item.content_type === 'image' && item.image_url) {
            return `<div class="modal-image-wrap"><img class="modal-image" src="${item.image_url}" alt="${item.title}"></div>`;
        }
        if (item.content_type === 'audio' && item.audio_url) {
            return `<div class="modal-audio-wrap"><audio class="modal-audio" controls src="${item.audio_url}"></audio></div>`;
        }
        if (item.content_type === 'video' && item.video_url) {
            return `<div class="modal-video-wrap"><video class="modal-video" controls src="${item.video_url}"></video></div>`;
        }
        if (item.content_type === 'youtube' && item.youtube_embed_url) {
            return `<div class="modal-youtube-wrap"><iframe src="${item.youtube_embed_url}" allowfullscreen title="${item.title}"></iframe></div>`;
        }
        if (item.content_type === 'pdf' && item.file_url) {
            return `<div class="modal-pdf-wrap"><iframe src="${item.file_url}" title="${item.title}" style="width:100%;min-height:70vh;border:0;border-radius:16px;"></iframe></div>`;
        }
        if ((item.content_type === 'attachment' || item.content_type === 'external_link' || item.content_type === 'embed') && (item.external_url || item.file_url || item.embed_url)) {
            const href = item.external_url || item.file_url || item.embed_url;
            return `<div class="modal-link-wrap"><a class="toolbar-btn" href="${href}" target="_blank" rel="noopener noreferrer">Open resource</a></div>`;
        }
        return `<div class="modal-error"><i class="fa-solid fa-circle-exclamation"></i><p>Content preview is not available.</p></div>`;
    }

    async function loadContent(contentId) {
        const modal = ensureModal();
        openModal();
        modal.querySelector('.modal-title').textContent = 'Loading...';
        modal.querySelector('.modal-body').innerHTML = '<div class="modal-loading"><div class="spinner"></div><p>Loading interactive content...</p></div>';

        try {
            const response = await fetch(resolveUrl(contentId), {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin',
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || data.error || 'Failed to load content.');
            }
            modal.querySelector('.modal-title').textContent = data.title || 'Preview';
            modal.querySelector('.modal-body').innerHTML = renderBody(data);
        } catch (error) {
            modal.querySelector('.modal-title').textContent = 'Preview unavailable';
            modal.querySelector('.modal-body').innerHTML = `<div class="modal-error"><i class="fa-solid fa-circle-exclamation"></i><p>${error.message}</p></div>`;
        }
    }

    document.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-content-id]');
        if (trigger) {
            event.preventDefault();
            loadContent(trigger.dataset.contentId);
            return;
        }

        const highlight = event.target.closest('.highlight-link');
        if (highlight && highlight.dataset.contentId) {
            event.preventDefault();
            loadContent(highlight.dataset.contentId);
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeModal();
        }
    });

    document.querySelectorAll('.accordion-trigger').forEach((button) => {
        button.addEventListener('click', () => {
            const item = button.closest('.accordion-item');
            const body = item.querySelector('.accordion-body');
            const isOpen = button.getAttribute('aria-expanded') === 'true';
            button.setAttribute('aria-expanded', String(!isOpen));
            item.classList.toggle('accordion-item--open', !isOpen);
            body.hidden = isOpen;
        });
    });
})();
