/**
 * Spreadsheet toolbar: switch active sheet, add + validate, open external link.
 */
(function () {
    'use strict';

    function getToolbar(root) {
        return root && root.id === 'spreadsheet-toolbar' ? root : document.getElementById('spreadsheet-toolbar');
    }

    function setExternalHref(selectEl, externalLink) {
        if (!selectEl || !externalLink) return;
        const opt = selectEl.options[selectEl.selectedIndex];
        const url = opt ? opt.getAttribute('data-sheet-url') : null;
        if (url) {
            externalLink.setAttribute('href', url);
        }
    }

    function initSpreadsheetToolbar(root) {
        const toolbar = getToolbar(root);
        if (!toolbar) return;

        const validateUrl = toolbar.dataset.validateUrl;
        const activateUrl = toolbar.dataset.activateUrl;
        const selectEl = document.getElementById('spreadsheet-selector');
        const externalLink = document.getElementById('spreadsheet-open-external');
        const addInput = document.getElementById('spreadsheet-add-input');
        const addSubmit = document.getElementById('spreadsheet-add-submit');
        const addFeedback = document.getElementById('spreadsheet-add-feedback');
        const addSpinner = toolbar.querySelector('.spreadsheet-add-spinner');
        const addLabel = toolbar.querySelector('.spreadsheet-add-label');

        if (selectEl && externalLink) {
            setExternalHref(selectEl, externalLink);
            selectEl.addEventListener('change', function () {
                setExternalHref(selectEl, externalLink);
                const spreadsheetId = selectEl.value;
                if (!spreadsheetId || !activateUrl) return;

                if (addFeedback) {
                    addFeedback.textContent = '';
                }
                fetch(activateUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ spreadsheet_id: spreadsheetId }),
                })
                    .then(function (r) {
                        return r.json();
                    })
                    .then(function (data) {
                        if (data.success) {
                            window.location.reload();
                        } else {
                            if (addFeedback) {
                                addFeedback.className = 'form-text small mt-1 text-danger';
                                addFeedback.textContent = data.error || 'Could not switch spreadsheet.';
                            }
                        }
                    })
                    .catch(function (err) {
                        if (addFeedback) {
                            addFeedback.className = 'form-text small mt-1 text-danger';
                            addFeedback.textContent = err.message || 'Network error.';
                        }
                    });
            });
        } else if (externalLink && !selectEl) {
            externalLink.classList.add('d-none');
        }

        function setAddLoading(loading) {
            if (!addSubmit) return;
            addSubmit.disabled = loading;
            if (addSpinner) addSpinner.classList.toggle('d-none', !loading);
            if (addLabel) addLabel.classList.toggle('d-none', loading);
        }

        function submitNewSpreadsheet() {
            if (!addInput || !validateUrl) return;
            const raw = addInput.value.trim();
            if (!raw) {
                if (addFeedback) {
                    addFeedback.className = 'form-text small mt-1 text-warning';
                    addFeedback.textContent = 'Paste a spreadsheet URL or ID.';
                }
                return;
            }

            if (addFeedback) {
                addFeedback.className = 'form-text small mt-1 text-muted';
                addFeedback.textContent = 'Validating…';
            }
            setAddLoading(true);

            fetch(validateUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ spreadsheet_url: raw }),
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (data) {
                    setAddLoading(false);
                    if (data.success) {
                        if (addFeedback) {
                            addFeedback.className = 'form-text small mt-1 text-success';
                            addFeedback.textContent = 'Saved. Loading…';
                        }
                        window.location.reload();
                    } else {
                        if (addFeedback) {
                            addFeedback.className = 'form-text small mt-1 text-danger';
                            addFeedback.textContent = data.error || 'Validation failed.';
                        }
                    }
                })
                .catch(function (err) {
                    setAddLoading(false);
                    if (addFeedback) {
                        addFeedback.className = 'form-text small mt-1 text-danger';
                        addFeedback.textContent = err.message || 'Network error.';
                    }
                });
        }

        if (addSubmit) {
            addSubmit.addEventListener('click', submitNewSpreadsheet);
        }
        if (addInput) {
            addInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    submitNewSpreadsheet();
                }
            });
        }
    }
    document.addEventListener('DOMContentLoaded', function () {
        initSpreadsheetToolbar(null);
    });
})();
