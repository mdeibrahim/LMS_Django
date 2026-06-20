(function () {
    const dataEl = document.getElementById('editorData');
    if (!dataEl) return;

    const editorData = JSON.parse(dataEl.textContent);
    const initialIc = JSON.parse(document.getElementById('initialInteractiveContents')?.textContent || '[]');
    const initialAcc = JSON.parse(document.getElementById('initialAccordionSections')?.textContent || '[]');

    const state = {
        interactiveContents: initialIc,
        accordionSections: initialAcc,
        savedRange: null,
        pendingAutoLink: false,
    };

    const statusEl = document.getElementById('editorStatus');
    const titleInput = document.getElementById('editorTitleInput');
    const rteContent = document.getElementById('rteContent');
    const saveBodyBtn = document.getElementById('btn-save-body');

    const icList = document.getElementById('icList');
    const icPanel = document.getElementById('icInlinePanel');
    const icForm = document.getElementById('icForm');
    const icFormId = document.getElementById('icFormId');
    const icTitle = document.getElementById('icTitle');
    const icType = document.getElementById('icType');
    const icTextContent = document.getElementById('icTextContent');
    const icYoutubeUrl = document.getElementById('icYoutubeUrl');

    const accList = document.getElementById('accordionList');
    const accPanel = document.getElementById('accInlinePanel');
    const accForm = document.getElementById('accForm');
    const accFormId = document.getElementById('accFormId');
    const accTitle = document.getElementById('accTitle');
    const accContent = document.getElementById('accContent');
    const accIsOpen = document.getElementById('accIsOpen');

    function setStatus(message, tone) {
        statusEl.innerHTML = `<i class="fa-solid ${tone === 'error' ? 'fa-circle-exclamation' : tone === 'saving' ? 'fa-rotate' : 'fa-circle-check'}"></i> ${message}`;
        statusEl.style.color = tone === 'error' ? '#dc2626' : tone === 'saving' ? '#b45309' : '#16a34a';
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    function renderIcList() {
        if (!icList) return;
        icList.innerHTML = '';
        if (!state.interactiveContents.length) {
            icList.innerHTML = '<div class="panel-empty"><i class="fa-solid fa-puzzle-piece"></i><p>No media items yet.<br>Click <strong>+</strong> to add Text, Image, Audio, Video or YouTube.</p></div>';
            return;
        }

        state.interactiveContents.filter(Boolean).forEach((item) => {
            const card = document.createElement('div');
            card.className = `ic-item ic-item--${item.content_type}`;
            card.dataset.icId = item.id;
            card.id = `ic-card-${item.id}`;
            card.innerHTML = `
                <div class="ic-item-icon"><i class="fa-solid fa-${item.content_type === 'text' ? 'font' : item.content_type === 'image' ? 'image' : item.content_type === 'audio' ? 'headphones' : 'video'}"></i></div>
                <div class="ic-item-body">
                    <div class="ic-item-title">${escapeHtml(item.title)}</div>
                    <div class="ic-item-type">${escapeHtml(item.content_type)}</div>
                </div>
                <div class="ic-item-actions">
                    <button class="ic-action-btn ic-edit-btn" data-ic-id="${item.id}" title="Edit" type="button"><i class="fa-solid fa-pen"></i></button>
                    <button class="ic-action-btn ic-delete-btn" data-ic-id="${item.id}" title="Delete" type="button"><i class="fa-solid fa-trash"></i></button>
                </div>
            `;
            icList.appendChild(card);
        });
    }

    function renderAccList() {
        if (!accList) return;
        accList.innerHTML = '';
        if (!state.accordionSections.length) {
            accList.innerHTML = '<div class="panel-empty"><i class="fa-solid fa-layer-group"></i><p>No sidebar sections yet.<br>Click <strong>+</strong> to add collapsible sections.</p></div>';
            return;
        }

        state.accordionSections.forEach((item) => {
            const card = document.createElement('div');
            card.className = 'acc-item';
            card.dataset.secId = item.id;
            card.id = `acc-card-${item.id}`;
            card.innerHTML = `
                <div class="acc-item-icon"><i class="fa-solid fa-layer-group"></i></div>
                <div class="acc-item-body">
                    <div class="acc-item-title">${escapeHtml(item.title)}</div>
                    ${item.is_open_by_default ? '<span class="acc-badge">Open by default</span>' : ''}
                </div>
                <div class="acc-item-actions">
                    <button class="ic-action-btn acc-edit-btn" data-sec-id="${item.id}" title="Edit" type="button"><i class="fa-solid fa-pen"></i></button>
                    <button class="ic-action-btn acc-delete-btn" data-sec-id="${item.id}" title="Delete" type="button"><i class="fa-solid fa-trash"></i></button>
                </div>
            `;
            accList.appendChild(card);
        });
    }

    function toggleContentFields(type) {
        icType.value = type;
        document.querySelectorAll('#typeSelector .type-btn').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.type === type);
        });
        ['Text', 'Image', 'Audio', 'Video', 'Youtube'].forEach((name) => {
            document.getElementById(`field${name}`).hidden = name.toLowerCase() !== type;
        });
    }

    function openIcPanel(item, options = {}) {
        icPanel.hidden = false;
        document.getElementById('icInlineTitle').innerHTML = item ? '<i class="fa-solid fa-wand-magic-sparkles"></i> Edit Media Item' : '<i class="fa-solid fa-wand-magic-sparkles"></i> Add Media Item';
        icForm.reset();
        icFormId.value = item?.id || '';
        icTitle.value = item?.title || '';
        icTextContent.value = item?.text_content || '';
        icYoutubeUrl.value = item?.youtube_url || '';
        toggleContentFields(item?.content_type || 'text');
        state.pendingAutoLink = Boolean(options.autoLink);
        if (state.pendingAutoLink) {
            saveSelection();
        }
        icTitle.focus();
    }

    function closeIcPanel() {
        icPanel.hidden = true;
        state.pendingAutoLink = false;
    }

    function openAccPanel(item) {
        accPanel.hidden = false;
        document.getElementById('accInlineTitle').innerHTML = item ? '<i class="fa-solid fa-layer-group"></i> Edit Accordion Section' : '<i class="fa-solid fa-layer-group"></i> Add Accordion Section';
        accForm.reset();
        accFormId.value = item?.id || '';
        accTitle.value = item?.title || '';
        accContent.value = item?.content || '';
        accIsOpen.checked = Boolean(item?.is_open_by_default);
    }

    function closeAccPanel() {
        accPanel.hidden = true;
    }

    async function saveModuleBody() {
        setStatus('Saving...', 'saving');
        try {
            const response = await fetch(editorData.saveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': editorData.csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    title: titleInput.value.trim(),
                    body_content: rteContent.innerHTML,
                }),
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.error || 'Save failed.');
            }
            setStatus('Saved', 'success');
        } catch (error) {
            setStatus(error.message, 'error');
        }
    }

    function markDirty() {
        setStatus('Unsaved changes', 'saving');
    }

    function saveSelection() {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) return;
        const range = selection.getRangeAt(0);
        if (!rteContent.contains(range.commonAncestorContainer)) return;
        state.savedRange = range.cloneRange();
    }

    function restoreSelection() {
        if (!state.savedRange) return false;
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(state.savedRange);
        return true;
    }

    function applyMediaLink(contentId) {
        if (!contentId || !restoreSelection()) return false;
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return;

        const range = selection.getRangeAt(0);
        const text = range.toString();
        const span = document.createElement('span');
        span.className = 'highlight-link highlight-link--blue link-media-blue';
        span.dataset.contentId = contentId;
        span.textContent = text;
        range.deleteContents();
        range.insertNode(span);
        selection.removeAllRanges();
        markDirty();
        return true;
    }

    function applyHighlight() {
        if (!restoreSelection()) return;
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return;

        const highlighted = document.execCommand('hiliteColor', false, '#fde68a')
            || document.execCommand('backColor', false, '#fde68a');
        if (!highlighted) {
            return;
        }
        rteContent.focus();
        markDirty();
    }

    async function submitIcForm(event) {
        event.preventDefault();
        const formData = new FormData();
        formData.append('title', icTitle.value.trim());
        formData.append('content_type', icType.value);
        formData.append('is_inline_reference', 'false');
        formData.append('text_content', icTextContent.value);
        formData.append('youtube_url', icYoutubeUrl.value);

        ['image', 'audio', 'video'].forEach((field) => {
            const input = document.getElementById(`ic${field.charAt(0).toUpperCase() + field.slice(1)}File`);
            if (input?.files?.[0]) formData.append(field, input.files[0]);
        });

        const isEdit = Boolean(icFormId.value);
        const url = isEdit ? `${editorData.icUpdateBase}${icFormId.value}/update/` : editorData.icCreateUrl;

        const response = await fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': editorData.csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
            body: formData,
        });
        const data = await response.json();
        const resource = data?.ic || data?.resource || data;
        const requestOk = response.ok && (data?.ok === undefined || data?.ok === true);
        if (!requestOk || !resource || !resource.id || !resource.content_type) {
            throw new Error(data?.error || 'Unable to save media item.');
        }

        if (isEdit) {
            state.interactiveContents = state.interactiveContents.map((item) => item.id === resource.id ? resource : item);
        } else {
            state.interactiveContents.push(resource);
        }
        renderIcList();
        const shouldAutoLink = state.pendingAutoLink && state.savedRange && state.savedRange.toString().trim();
        closeIcPanel();
        if (shouldAutoLink) {
            const linked = applyMediaLink(resource.id);
            if (!linked) {
                setStatus('Saved media item, but could not attach it to the selected text.', 'error');
            }
        }
    }

    async function submitAccForm(event) {
        event.preventDefault();
        const payload = {
            title: accTitle.value.trim(),
            content: accContent.value,
            is_open_by_default: accIsOpen.checked,
        };
        const isEdit = Boolean(accFormId.value);
        const url = isEdit ? `${editorData.accUpdateBase}${accFormId.value}/update/` : editorData.accCreateUrl;

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': editorData.csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'Unable to save accordion section.');
        }

        if (isEdit) {
            state.accordionSections = state.accordionSections.map((item) => item.id === data.section.id ? data.section : item);
        } else {
            state.accordionSections.push(data.section);
        }
        renderAccList();
        closeAccPanel();
    }

    async function deleteIc(id) {
        const response = await fetch(`${editorData.icDeleteBase}${id}/delete/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': editorData.csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || 'Delete failed.');
        state.interactiveContents = state.interactiveContents.filter((item) => item.id !== id);
        renderIcList();
    }

    async function deleteAcc(id) {
        const response = await fetch(`${editorData.accDeleteBase}${id}/delete/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': editorData.csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || 'Delete failed.');
        state.accordionSections = state.accordionSections.filter((item) => item.id !== id);
        renderAccList();
    }

    document.querySelectorAll('[data-cmd]').forEach((button) => {
        button.addEventListener('mousedown', (event) => {
            if (event.button !== 0) return;
            saveSelection();
        });
        button.addEventListener('click', () => {
            if (button.dataset.cmd === 'highlight') {
                applyHighlight();
                return;
            }
            document.execCommand(button.dataset.cmd, false, null);
            rteContent.focus();
            markDirty();
        });
    });

    titleInput?.addEventListener('input', markDirty);
    rteContent?.addEventListener('input', markDirty);
    saveBodyBtn?.addEventListener('click', saveModuleBody);

    const insertLinkButton = document.getElementById('btn-insert-link');
    insertLinkButton?.addEventListener('mousedown', (event) => {
        if (event.button !== 0) return;
        saveSelection();
    });
    document.getElementById('btn-add-ic')?.addEventListener('click', () => openIcPanel(null));
    document.getElementById('icInlineClose')?.addEventListener('click', closeIcPanel);
    document.getElementById('icInlineCancel')?.addEventListener('click', closeIcPanel);
    icPanel?.addEventListener('click', (event) => {
        if (event.target === icPanel) {
            closeIcPanel();
        }
    });
    document.querySelectorAll('#typeSelector .type-btn').forEach((button) => {
        button.addEventListener('click', () => toggleContentFields(button.dataset.type));
    });
    icForm?.addEventListener('submit', async (event) => {
        try {
            await submitIcForm(event);
        } catch (error) {
            setStatus(error.message, 'error');
        }
    });

    icList?.addEventListener('click', async (event) => {
        const editBtn = event.target.closest('.ic-edit-btn');
        const deleteBtn = event.target.closest('.ic-delete-btn');
        if (editBtn) {
            const item = state.interactiveContents.find((entry) => entry.id === Number(editBtn.dataset.icId));
            openIcPanel(item || null, { autoLink: false });
            return;
        }
        if (deleteBtn) {
            try {
                await deleteIc(Number(deleteBtn.dataset.icId));
            } catch (error) {
                setStatus(error.message, 'error');
            }
        }
    });

    insertLinkButton?.addEventListener('click', (event) => {
        event.preventDefault();
        openIcPanel(null, { autoLink: Boolean(state.savedRange) });
    });

    document.getElementById('btn-add-accordion')?.addEventListener('click', () => openAccPanel(null));
    document.getElementById('accInlineClose')?.addEventListener('click', closeAccPanel);
    document.getElementById('accInlineCancel')?.addEventListener('click', closeAccPanel);
    accForm?.addEventListener('submit', async (event) => {
        try {
            await submitAccForm(event);
        } catch (error) {
            setStatus(error.message, 'error');
        }
    });

    accList?.addEventListener('click', async (event) => {
        const editBtn = event.target.closest('.acc-edit-btn');
        const deleteBtn = event.target.closest('.acc-delete-btn');
        if (editBtn) {
            const item = state.accordionSections.find((entry) => entry.id === Number(editBtn.dataset.secId));
            openAccPanel(item || null);
            return;
        }
        if (deleteBtn) {
            try {
                await deleteAcc(Number(deleteBtn.dataset.secId));
            } catch (error) {
                setStatus(error.message, 'error');
            }
        }
    });

    renderIcList();
    renderAccList();

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && icPanel && !icPanel.hidden) {
            closeIcPanel();
        }
    });
})();
