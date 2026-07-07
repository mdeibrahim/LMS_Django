(function () {
    const dataEl = document.getElementById('resourceData');
    if (dataEl) {
        try {
            JSON.parse(dataEl.textContent);
        } catch (error) {
            return;
        }
    }

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
