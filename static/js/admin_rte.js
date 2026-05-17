document.addEventListener('DOMContentLoaded', function () {
    let activeEditor = null;
    let savedRange = null;

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    function getModuleIdFromAdminUrl() {
        // matches /admin/content/module/<id>/change/
        const m = window.location.pathname.match(/\/admin\/content\/module\/(\d+)\/change\//);
        if (m) return m[1];
        return null;
    }

    function getModuleIdFromForm(editor) {
        const wrapper = editor && editor.closest('.admin-rte-wrapper');
        const cachedId = wrapper && wrapper.dataset.moduleId;
        if (cachedId) return cachedId;

        const form = editor && editor.closest('form');
        const moduleField = form && form.querySelector('[name="module"]');
        const moduleId = moduleField && moduleField.value ? moduleField.value.trim() : '';
        if (wrapper) wrapper.dataset.moduleId = moduleId;
        return moduleId;
    }

    function getSelectedText(editor) {
        const selection = window.getSelection();
        if (selection && selection.rangeCount > 0) {
            const range = selection.getRangeAt(0);
            if (editor && editor.contains(range.commonAncestorContainer)) {
                const liveText = selection.toString().trim();
                if (liveText) return liveText;
            }
        }
        return savedRange ? savedRange.toString().trim() : '';
    }

    function saveSelection(editor) {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) return;
        const range = selection.getRangeAt(0);
        if (!editor.contains(range.commonAncestorContainer)) return;
        activeEditor = editor;
        savedRange = range.cloneRange();
    }

    function restoreSelection(editor) {
        const selection = window.getSelection();
        if (!selection) return null;
        if (savedRange && editor.contains(savedRange.commonAncestorContainer)) {
            selection.removeAllRanges();
            selection.addRange(savedRange);
            return savedRange;
        }
        return null;
    }

    function inferVariant(contentType, item) {
        if (contentType === 'youtube') return 'youtube';
        if (contentType === 'video') return (item && item.youtube_embed_url) ? 'youtube' : 'video';
        if (contentType === 'audio') return 'audio';
        if (contentType === 'image') return 'image';
        if (contentType === 'text') return 'link';
        return 'link';
    }

    function placeInteractiveHighlight(editor, ic, fallbackText) {
        const selection = window.getSelection();
        const range = restoreSelection(editor);
        const span = document.createElement('span');
        const variant = inferVariant(ic.content_type, ic);
        span.className = `highlight-link highlight-link--${variant}`;
        span.dataset.contentId = String(ic.id);
        span.textContent = fallbackText || ic.title || 'Interactive content';

        if (!range || !editor.contains(range.commonAncestorContainer)) {
            editor.appendChild(span);
            editor.appendChild(document.createTextNode(' '));
            editor.focus();
            return;
        }

        range.deleteContents();
        range.insertNode(span);
        const cursorRange = document.createRange();
        cursorRange.setStartAfter(span);
        cursorRange.collapse(true);
        selection.removeAllRanges();
        selection.addRange(cursorRange);
        savedRange = cursorRange.cloneRange();
        editor.focus();
    }

    async function uploadFileToApi(file, mediaType, moduleId) {
        if (!moduleId) moduleId = getModuleIdFromAdminUrl();
        if (!moduleId) throw new Error('Please select/save the module first.');

        const form = new FormData();
        form.append('content_type', mediaType);
        form.append('title', file.name);
        form.append('is_inline_reference', 'true');
        if (mediaType === 'image') form.append('image', file);
        if (mediaType === 'audio') form.append('audio', file);
        if (mediaType === 'video') form.append('video', file);

        const resp = await fetch(`/api/module/${moduleId}/ic/create/`, {
            method: 'POST',
            body: form,
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': getCookie('csrftoken') || ''
            }
        });

        if (!resp.ok) {
            const txt = await resp.text();
            throw new Error('Upload failed: ' + txt);
        }

        const data = await resp.json();
        if (!data.ok || !data.ic) throw new Error('Upload did not return content data');
        return data.ic;
    }

    async function createInteractiveContent(payload, moduleId) {
        if (!moduleId) moduleId = getModuleIdFromAdminUrl();
        if (!moduleId) throw new Error('Please select/save the module first.');

        const resp = await fetch(`/api/module/${moduleId}/ic/create/`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || ''
            },
            body: JSON.stringify(payload)
        });

        const data = await resp.json();
        if (!resp.ok || !data.ok || !data.ic) {
            throw new Error(data.error || data.detail || 'Content create failed');
        }
        return data.ic;
    }

    function buildUrlPayload(url, selectedText) {
        const normalizedUrl = String(url || '').trim();
        const label = selectedText || normalizedUrl;
        const lowerUrl = normalizedUrl.toLowerCase();
        const escapedUrl = escapeAttr(normalizedUrl);
        const escapedLabel = escapeHtml(label);

        if (/youtu\.be\/|youtube\.com\/(watch|shorts|embed|live)/i.test(normalizedUrl)) {
            return {
                content_type: 'youtube',
                title: label,
                is_inline_reference: true,
                youtube_url: normalizedUrl
            };
        }

        if (/\.(mp4|webm|ogg)(\?.*)?$/i.test(lowerUrl)) {
            return {
                content_type: 'video',
                title: label,
                is_inline_reference: true,
                video_url: normalizedUrl
            };
        }

        if (/\.(mp3|wav|ogg|m4a)(\?.*)?$/i.test(lowerUrl)) {
            return {
                content_type: 'text',
                title: label,
                is_inline_reference: true,
                text_content: `<div class="embedded-resource embedded-resource--audio"><p><strong>${escapedLabel}</strong></p><audio controls src="${escapedUrl}"></audio></div>`
            };
        }

        if (/\.(png|jpe?g|gif|webp|svg)(\?.*)?$/i.test(lowerUrl)) {
            return {
                content_type: 'text',
                title: label,
                is_inline_reference: true,
                text_content: `<div class="embedded-resource embedded-resource--image"><img src="${escapedUrl}" alt="${escapedLabel}" style="max-width:100%;height:auto;border-radius:12px;" /></div>`
            };
        }

        return {
            content_type: 'text',
            title: label,
            is_inline_reference: true,
            text_content: `<div class="embedded-resource embedded-resource--link"><p><strong>${escapedLabel}</strong></p><p><a href="${escapedUrl}" target="_blank" rel="noopener noreferrer">${escapedUrl}</a></p></div>`
        };
    }

    function handleFileUpload(file, mediaType, editor) {
        if (!file) return;
        const moduleId = getModuleIdFromForm(editor);
        const selectedText = getSelectedText(editor) || file.name;
        uploadFileToApi(file, mediaType, moduleId).then(function (ic) {
            placeInteractiveHighlight(editor, ic, selectedText);
        }).catch(function (err) {
            alert('Upload error: ' + (err.message || err));
        });
    }

    function createToolbar() {
        const toolbar = document.createElement('div');
        toolbar.className = 'admin-rte-toolbar';

        const buttons = [
            { cmd: 'bold', icon: 'B' },
            { cmd: 'italic', icon: 'I' },
            { cmd: 'underline', icon: 'U' },
            { cmd: 'insertUnorderedList', icon: '• List' },
            { cmd: 'insertOrderedList', icon: '1. List' },
            { cmd: 'createLink', icon: 'Link' },
            { cmd: 'insertImage', icon: 'Img' },
            { cmd: 'insertAudio', icon: '♫' },
            { cmd: 'insertVideo', icon: '▶' },
            { cmd: 'insertMultimediaBlock', icon: 'Media+' },
            { cmd: 'stripMedia', icon: 'NoMedia' },
        ];

        buttons.forEach(function (b) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'admin-rte-btn';
            btn.textContent = b.icon;
            btn.dataset.cmd = b.cmd;
            btn.addEventListener('click', function () {
                const editor = toolbar.nextElementSibling;
                if (!editor) return;
                activeEditor = editor;
                saveSelection(editor);

                if (b.cmd === 'createLink') {
                    const url = prompt('Enter URL');
                    if (!url) return;
                    const moduleId = getModuleIdFromForm(editor);
                    const selectedText = getSelectedText(editor) || url;
                    createInteractiveContent(buildUrlPayload(url, selectedText), moduleId).then(function (ic) {
                        placeInteractiveHighlight(editor, ic, selectedText);
                    }).catch(function (err) {
                        alert('Link add error: ' + (err.message || err));
                    });
                    return;
                }

                if (b.cmd === 'insertImage' || b.cmd === 'insertAudio' || b.cmd === 'insertVideo') {
                    const wrapper = toolbar.parentNode;
                    const fileInputs = wrapper && wrapper._fileInputs;
                    const which = b.cmd === 'insertImage' ? 'image' : (b.cmd === 'insertAudio' ? 'audio' : 'video');

                    if (fileInputs && fileInputs[which]) {
                        fileInputs[which].click();
                        return;
                    }

                    const url = prompt('Enter media URL (absolute or /media/ path)');
                    if (!url) return;
                    const selectedText = getSelectedText(editor) || url;
                    const moduleId = getModuleIdFromForm(editor);
                    createInteractiveContent(buildUrlPayload(url, selectedText), moduleId).then(function (ic) {
                        placeInteractiveHighlight(editor, ic, selectedText);
                    }).catch(function (err) {
                        alert('Media add error: ' + (err.message || err));
                    });
                    return;
                }

                if (b.cmd === 'insertMultimediaBlock') {
                    const type = prompt('Enter media type (image, audio, video, youtube, link)', 'image');
                    if (!type) return;
                    const url = prompt('Enter media URL (absolute or /media/ path)');
                    if (!url) return;
                    const caption = prompt('Enter caption/description (optional)', getSelectedText(editor) || '');

                    let html = '';
                    const escUrl = escapeAttr(url);
                    const escCaption = escapeHtml(caption || '');

                    if (/youtube\.com|youtu\.be/.test(url)) {
                        html = `<div class="embedded-resource embedded-resource--youtube"><p><strong>${escCaption}</strong></p><iframe src="https://www.youtube.com/embed/${escUrl.split('v=')[1] || escUrl}" frameborder="0" allowfullscreen style="width:100%;height:360px;border-radius:8px;"></iframe></div>`;
                    } else if (/\.(png|jpe?g|gif|webp|svg)(\?.*)?$/i.test(url)) {
                        html = `<div class="embedded-resource embedded-resource--image"><p><strong>${escCaption}</strong></p><img src="${escUrl}" alt="${escCaption}" style="max-width:100%;height:auto;border-radius:12px;"/></div>`;
                    } else if (/\.(mp3|wav|ogg|m4a)(\?.*)?$/i.test(url)) {
                        html = `<div class="embedded-resource embedded-resource--audio"><p><strong>${escCaption}</strong></p><audio controls src="${escUrl}"></audio></div>`;
                    } else if (/\.(mp4|webm|ogg)(\?.*)?$/i.test(url)) {
                        html = `<div class="embedded-resource embedded-resource--video"><p><strong>${escCaption}</strong></p><video controls src="${escUrl}" style="max-width:100%;height:auto;border-radius:12px;"></video></div>`;
                    } else {
                        html = `<div class="embedded-resource embedded-resource--link"><p><strong>${escCaption}</strong></p><p><a href="${escUrl}" target="_blank" rel="noopener noreferrer">${escUrl}</a></p></div>`;
                    }

                    // insert HTML block at cursor
                    const range = restoreSelection(editor);
                    if (!range || !editor.contains(range.commonAncestorContainer)) {
                        editor.appendChild(document.createElement('div')).innerHTML = html;
                    } else {
                        const frag = document.createRange().createContextualFragment(html);
                        range.deleteContents();
                        range.insertNode(frag);
                    }
                    editor.focus();
                    return;
                }

                if (b.cmd === 'stripMedia') {
                    // remove embedded-resource blocks from editor
                    const blocks = editor.querySelectorAll('.embedded-resource');
                    let removed = 0;
                    blocks.forEach(function (el) {
                        el.parentNode.removeChild(el);
                        removed += 1;
                    });
                    if (removed === 0) alert('No embedded multimedia blocks found.');
                    else alert('Removed ' + removed + ' multimedia block(s).');
                    return;
                }

                document.execCommand(b.cmd, false, null);
                editor.focus();
            });
            toolbar.appendChild(btn);
        });

        return toolbar;
    }

    function escapeAttr(s) {
        return String(s).replace(/"/g, '&quot;');
    }

    function escapeHtml(text) {
        const d = document.createElement('div');
        d.textContent = text || '';
        return d.innerHTML;
    }

    document.querySelectorAll('textarea.rte-enabled').forEach(function (ta) {
        // hide original textarea but keep it for form submission
        ta.style.display = 'none';

        const wrapper = document.createElement('div');
        wrapper.className = 'admin-rte-wrapper';

        const toolbar = createToolbar();
        const editor = document.createElement('div');
        editor.className = 'admin-rte-editor';
        editor.contentEditable = 'true';
        editor.innerHTML = ta.value ? ta.value.replace(/\n/g, '<br>') : '';
        editor.addEventListener('mouseup', function () { saveSelection(editor); });
        editor.addEventListener('keyup', function () { saveSelection(editor); });
        editor.addEventListener('focus', function () {
            activeEditor = editor;
            saveSelection(editor);
        });

        // sync back to textarea before submit
        const form = ta.closest('form');
        if (form) {
            form.addEventListener('submit', function () {
                ta.value = editor.innerHTML;
            });
        }

        wrapper.appendChild(toolbar);
        wrapper.appendChild(editor);
        wrapper.dataset.moduleId = getModuleIdFromAdminUrl() || '';
        ta.parentNode.insertBefore(wrapper, ta);

        const moduleField = form && form.querySelector('[name="module"]');
        if (moduleField) {
            wrapper.dataset.moduleId = moduleField.value || wrapper.dataset.moduleId;
            moduleField.addEventListener('change', function () {
                wrapper.dataset.moduleId = moduleField.value || '';
            });
        }

        // hidden file inputs for uploads
        const fileImage = document.createElement('input');
        fileImage.type = 'file';
        fileImage.accept = 'image/*';
        fileImage.style.display = 'none';

        const fileAudio = document.createElement('input');
        fileAudio.type = 'file';
        fileAudio.accept = 'audio/*';
        fileAudio.style.display = 'none';

        const fileVideo = document.createElement('input');
        fileVideo.type = 'file';
        fileVideo.accept = 'video/*';
        fileVideo.style.display = 'none';

        document.body.appendChild(fileImage);
        document.body.appendChild(fileAudio);
        document.body.appendChild(fileVideo);

        fileImage.addEventListener('change', function (e) {
            handleFileUpload(e.target.files[0], 'image', activeEditor || editor);
            e.target.value = '';
        });
        fileAudio.addEventListener('change', function (e) {
            handleFileUpload(e.target.files[0], 'audio', activeEditor || editor);
            e.target.value = '';
        });
        fileVideo.addEventListener('change', function (e) {
            handleFileUpload(e.target.files[0], 'video', activeEditor || editor);
            e.target.value = '';
        });

        // expose file inputs via wrapper for toolbar handlers
        wrapper._fileInputs = { image: fileImage, audio: fileAudio, video: fileVideo };
    });
});
