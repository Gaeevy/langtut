/**
 * Settings page: debounced rename + language autosave + remove spreadsheet.
 */
(function () {
    'use strict';

    function showToast(title, message, type) {
        const toastEl = document.getElementById('settings-toast');
        const toastBody = document.getElementById('toast-body');
        const toastTitle = document.getElementById('toast-title');
        if (!toastEl || !toastBody || !toastTitle || typeof bootstrap === 'undefined') {
            return;
        }
        const toast = new bootstrap.Toast(toastEl);
        const icons = { success: '✓', danger: '✗', warning: '⚠', info: 'ℹ' };
        const titles = { success: 'Success', danger: 'Error', warning: 'Warning', info: 'Info' };
        toastEl.className = 'toast border-' + type;
        toastTitle.innerHTML = (icons[type] || '') + ' ' + (titles[type] || 'Notice');
        toastBody.innerHTML = message;
        toast.show();
    }

        function setStatus(text, kind) {
        const el = document.getElementById('settings-save-status');
        if (!el) return;
        el.textContent = text;
        el.className = 'small mt-1 ';
        if (kind === 'error') {
            el.className += 'text-danger';
        } else if (kind === 'success') {
            el.className += 'text-success';
        } else if (kind === 'pending') {
            el.className += 'text-muted';
        } else {
            el.className += 'text-muted';
        }
    }

    function debounce(fn, ms) {
        let t;
        return function () {
            const args = arguments;
            clearTimeout(t);
            t = setTimeout(function () {
                fn.apply(null, args);
            }, ms);
        };
    }

    function loadLanguageSettings() {
        const orig = document.getElementById('original-language');
        const tgt = document.getElementById('target-language');
        const hint = document.getElementById('hint-language');
        if (!orig || !tgt || !hint) return;

        fetch('/api/language-settings')
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                if (data.success && data.language_settings) {
                    const s = data.language_settings;
                    orig.value = s.original;
                    tgt.value = s.target;
                    hint.value = s.hint;
                } else if (!data.success) {
                    showToast('Error', 'Could not load languages: ' + (data.error || 'unknown'), 'danger');
                }
            })
            .catch(function (err) {
                showToast('Error', err.message, 'danger');
            });
    }

    function validateLanguageSettings(languageSettings) {
        return fetch('/api/language-settings/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language_settings: languageSettings }),
        })
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                if (data.success) {
                    return {
                        valid: data.valid,
                        validation_errors: data.validation_errors || [],
                        warnings: data.warnings || [],
                    };
                }
                throw new Error(data.error || 'Validation failed');
            });
    }

    function saveLanguageSettings() {
        const orig = document.getElementById('original-language');
        const tgt = document.getElementById('target-language');
        const hint = document.getElementById('hint-language');
        if (!orig || !tgt || !hint) return;

        const languageSettings = {
            original: orig.value,
            target: tgt.value,
            hint: hint.value,
        };

        setStatus('Validating…', 'pending');
        validateLanguageSettings(languageSettings)
            .then(function (validationResult) {
                if (!validationResult.valid) {
                    let msg = 'Invalid languages:<br>';
                    validationResult.validation_errors.forEach(function (e) {
                        msg += '• ' + e.field + ': ' + e.message + '<br>';
                    });
                    showToast('Error', msg, 'danger');
                    setStatus('', 'muted');
                    return;
                }
                setStatus('Saving…', 'pending');
                return fetch('/api/language-settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ language_settings: languageSettings }),
                })
                    .then(function (r) {
                        return r.json();
                    })
                    .then(function (data) {
                        if (data.success) {
                            setStatus('Languages saved.', 'success');
                        } else {
                            showToast('Error', data.error || 'Save failed', 'danger');
                            setStatus('Save failed.', 'error');
                        }
                    });
            })
            .catch(function (err) {
                showToast('Error', err.message, 'danger');
                setStatus('', 'muted');
            });
    }

    function saveDisplayName() {
        const nameInput = document.getElementById('spreadsheet-display-name');
        const sidEl = document.getElementById('settings-spreadsheet-id');
        if (!nameInput || !sidEl) return;

        const spreadsheetId = sidEl.value;
        const newName = nameInput.value.trim();
        if (!spreadsheetId) return;

        setStatus('Saving name…', 'pending');
        fetch('/settings/rename-spreadsheet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                spreadsheet_id: spreadsheetId,
                new_name: newName || ' ',
            }),
        })
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                if (data.success) {
                    setStatus('Name saved.', 'success');
                } else {
                    showToast('Error', data.error || 'Rename failed', 'danger');
                    setStatus('Could not save name.', 'error');
                }
            })
            .catch(function (err) {
                showToast('Error', err.message, 'danger');
                setStatus('', 'muted');
            });
    }

    const debouncedSaveName = debounce(saveDisplayName, 500);

    function confirmRemove() {
        const sidEl = document.getElementById('settings-spreadsheet-id');
        if (!sidEl || !sidEl.value) return;
        if (
            !window.confirm(
                'Remove this spreadsheet from the app? You can link it again later. ' +
                    'Your Google Sheet will not be deleted.'
            )
        ) {
            return;
        }
        fetch('/settings/remove-spreadsheet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ spreadsheet_id: sidEl.value }),
        })
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                if (data.success) {
                    window.location.href = '/';
                } else {
                    showToast('Error', data.error || 'Remove failed', 'danger');
                }
            })
            .catch(function (err) {
                showToast('Error', err.message, 'danger');
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        loadLanguageSettings();

        const nameInput = document.getElementById('spreadsheet-display-name');
        if (nameInput) {
            nameInput.addEventListener('input', debouncedSaveName);
        }

        ['original-language', 'target-language', 'hint-language'].forEach(function (id) {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', saveLanguageSettings);
            }
        });

        const removeBtn = document.getElementById('settings-remove-spreadsheet');
        if (removeBtn) {
            removeBtn.addEventListener('click', confirmRemove);
        }
    });
})();
