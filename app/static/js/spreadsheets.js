/**
 * Spreadsheet toolbar combobox: filter sheets, activate, paste URL to add, loading state.
 */
(function () {
    'use strict';

    function getToolbar() {
        return document.getElementById('spreadsheet-toolbar');
    }

    function parseData() {
        const el = document.getElementById('spreadsheet-toolbar-data');
        if (!el || !el.textContent) {
            return { spreadsheets: [] };
        }
        try {
            return JSON.parse(el.textContent);
        } catch {
            return { spreadsheets: [] };
        }
    }

    function norm(s) {
        return (s || '').trim().toLowerCase();
    }

    function exactNameMatch(raw, items) {
        const r = norm(raw);
        if (!r) return null;
        for (let i = 0; i < items.length; i += 1) {
            const it = items[i];
            const name = norm(it.spreadsheet_name || '');
            const label = norm(displayLabel(it));
            if ((name && r === name) || (label && r === label)) {
                return it;
            }
        }
        return null;
    }

    function looksLikeSpreadsheetRef(raw) {
        const value = (raw || '').trim();
        if (!value) return false;
        if (value.includes('docs.google.com/spreadsheets')) return true;
        if (value.includes('/spreadsheets/d/')) return true;
        return /^[A-Za-z0-9_-]{20,}$/.test(value);
    }

    function displayLabel(it) {
        if (!it) return '';
        return it.spreadsheet_name || it.spreadsheet_id || '';
    }

    function initSpreadsheetToolbar() {
        const toolbar = getToolbar();
        if (!toolbar) return;

        const validateUrl = toolbar.dataset.validateUrl;
        const activateUrl = toolbar.dataset.activateUrl;
        const data = parseData();
        const input = document.getElementById('spreadsheet-combobox-input');
        const listbox = document.getElementById('spreadsheet-combobox-listbox');
        const statusEl = document.getElementById('spreadsheet-toolbar-status');
        const progressEl = document.getElementById('spreadsheet-toolbar-progress');
        const externalLink = document.getElementById('spreadsheet-open-external');
        const settingsLink = document.getElementById('spreadsheet-open-settings');

        if (!input || !listbox) return;

        const state = {
            items: data.spreadsheets || [],
            visibleRows: [],
            highlight: -1,
            listOpen: false,
            filtering: false,
            suspendClose: false,
        };

        function getActiveFromState() {
            let active = state.items.find(function (x) {
                return x.is_active;
            });
            if (!active && state.items.length) {
                active = state.items[0];
            }
            return active || null;
        }

        function setExternalFromItem(it) {
            if (!externalLink) return;
            if (!it || !it.spreadsheet_id) {
                externalLink.setAttribute('href', '#');
                externalLink.classList.add('d-none');
                return;
            }
            const url = 'https://docs.google.com/spreadsheets/d/' + it.spreadsheet_id;
            externalLink.setAttribute('href', url);
            externalLink.classList.remove('d-none');
        }

        function syncInputFromActive() {
            const active = getActiveFromState();
            state.filtering = false;
            input.value = displayLabel(active);
            setExternalFromItem(active);
            toolbar.dataset.activeId = active ? active.spreadsheet_id : '';
        }

        function setToolbarLoading(loading, message) {
            toolbar.classList.toggle('is-loading', loading);
            input.disabled = loading;
            input.setAttribute('aria-busy', loading ? 'true' : 'false');
            if (settingsLink) {
                settingsLink.setAttribute('tabindex', loading ? '-1' : '0');
                settingsLink.setAttribute('aria-disabled', loading ? 'true' : 'false');
            }
            if (externalLink) {
                externalLink.setAttribute('tabindex', loading ? '-1' : '0');
                externalLink.setAttribute('aria-disabled', loading ? 'true' : 'false');
            }
            if (progressEl) {
                progressEl.hidden = !loading;
                progressEl.setAttribute('aria-hidden', loading ? 'false' : 'true');
            }
            if (statusEl) {
                statusEl.textContent = loading ? message || '' : '';
                statusEl.className =
                    'form-text small mt-1 spreadsheet-toolbar-status' +
                    (loading ? ' text-muted' : '');
            }
        }

        function showError(msg) {
            if (!statusEl) return;
            statusEl.textContent = msg;
            statusEl.className = 'form-text small mt-1 spreadsheet-toolbar-status text-danger';
        }

        function clearStatus() {
            if (!statusEl) return;
            statusEl.textContent = '';
            statusEl.className = 'form-text small mt-1 spreadsheet-toolbar-status';
        }

        function buildVisibleRows() {
            const raw = input.value;
            const q = state.filtering ? norm(raw) : '';
            const all = state.items;
            let filtered = all;
            if (q) {
                filtered = all.filter(function (it) {
                    return norm(displayLabel(it)).includes(q);
                });
            }
            const rows = filtered.map(function (it) {
                return { type: 'item', item: it };
            });
            const trimmed = raw.trim();
            if (
                state.filtering &&
                trimmed &&
                looksLikeSpreadsheetRef(trimmed) &&
                !exactNameMatch(trimmed, all)
            ) {
                rows.push({ type: 'add', query: trimmed });
            }
            state.visibleRows = rows;
            if (state.highlight >= rows.length) {
                state.highlight = rows.length ? rows.length - 1 : -1;
            }
        }

        function renderListDOM() {
            listbox.innerHTML = '';
            const rows = state.visibleRows;
            for (let i = 0; i < rows.length; i += 1) {
                const row = rows[i];
                const li = document.createElement('li');
                li.setAttribute('role', 'option');
                li.className = 'spreadsheet-combobox-option';
                li.dataset.rowIndex = String(i);
                if (row.type === 'item') {
                    li.textContent = displayLabel(row.item);
                    li.dataset.spreadsheetId = row.item.spreadsheet_id;
                } else {
                    li.classList.add('spreadsheet-combobox-option-add');
                    li.textContent = 'Add spreadsheet: ' + row.query;
                }
                if (i === state.highlight) {
                    li.classList.add('is-active');
                    li.setAttribute('aria-selected', 'true');
                } else {
                    li.setAttribute('aria-selected', 'false');
                }
                li.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    state.suspendClose = true;
                });
                li.addEventListener('click', function () {
                    state.suspendClose = false;
                    commitRow(row);
                });
                listbox.appendChild(li);
            }
            if (!rows.length && state.listOpen && !input.value.trim()) {
                const hint = document.createElement('li');
                hint.className = 'spreadsheet-combobox-option spreadsheet-combobox-option-hint';
                hint.setAttribute('role', 'presentation');
                hint.textContent =
                    state.items.length === 0
                        ? 'Paste a Google Sheets URL or ID and press Enter'
                        : 'No matches';
                listbox.appendChild(hint);
            }
        }

        function openList() {
            state.listOpen = true;
            listbox.hidden = false;
            input.setAttribute('aria-expanded', 'true');
            buildVisibleRows();
            if (state.visibleRows.length) {
                if (state.highlight < 0 || state.highlight >= state.visibleRows.length) {
                    state.highlight = 0;
                }
            } else {
                state.highlight = -1;
            }
            renderListDOM();
        }

        function closeList() {
            state.listOpen = false;
            listbox.hidden = true;
            input.setAttribute('aria-expanded', 'false');
            state.highlight = -1;
        }

        function setHighlight(idx) {
            buildVisibleRows();
            const n = state.visibleRows.length;
            if (n === 0) {
                state.highlight = -1;
                renderListDOM();
                return;
            }
            let next = idx;
            while (next < 0) next += n;
            while (next >= n) next -= n;
            state.highlight = next;
            renderListDOM();
            const activeLi = listbox.querySelector('.spreadsheet-combobox-option.is-active');
            if (activeLi && activeLi.scrollIntoView) {
                activeLi.scrollIntoView({ block: 'nearest' });
            }
        }

        function activateSpreadsheet(spreadsheetId) {
            if (!spreadsheetId || !activateUrl) return;
            setToolbarLoading(true, 'Switching spreadsheet…');
            clearStatus();
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
                        setToolbarLoading(true, 'Loading…');
                        window.location.reload();
                    } else {
                        setToolbarLoading(false, '');
                        showError(data.error || 'Could not switch spreadsheet.');
                    }
                })
                .catch(function (err) {
                    setToolbarLoading(false, '');
                    showError(err.message || 'Network error.');
                });
        }

        function validateNewSpreadsheet(raw) {
            if (!raw || !validateUrl) return;
            setToolbarLoading(true, 'Validating spreadsheet…');
            clearStatus();
            fetch(validateUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ spreadsheet_url: raw }),
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (data) {
                    if (data.success) {
                        setToolbarLoading(true, 'Loading…');
                        window.location.reload();
                    } else {
                        setToolbarLoading(false, '');
                        showError(data.error || 'Validation failed.');
                    }
                })
                .catch(function (err) {
                    setToolbarLoading(false, '');
                    showError(err.message || 'Network error.');
                });
        }

        function commitRow(row) {
            if (!row) return;
            if (row.type === 'item') {
                closeList();
                activateSpreadsheet(row.item.spreadsheet_id);
            } else {
                closeList();
                validateNewSpreadsheet(row.query);
            }
        }

        function commitEnter() {
            buildVisibleRows();
            const rows = state.visibleRows;
            const raw = input.value.trim();
            if (state.highlight >= 0 && state.highlight < rows.length) {
                commitRow(rows[state.highlight]);
                return;
            }
            const exact = exactNameMatch(raw, state.items);
            if (exact) {
                closeList();
                activateSpreadsheet(exact.spreadsheet_id);
                return;
            }
            if (rows.length === 1) {
                commitRow(rows[0]);
                return;
            }
            if (looksLikeSpreadsheetRef(raw)) {
                closeList();
                validateNewSpreadsheet(raw);
                return;
            }
            if (raw) {
                showError('No matching spreadsheet found.');
            }
        }

        input.addEventListener('focus', function () {
            clearStatus();
            state.filtering = false;
            input.value = '';
            openList();
        });

        input.addEventListener('click', function () {
            if (input.disabled || state.listOpen) return;
            clearStatus();
            state.filtering = false;
            input.value = '';
            openList();
        });

        input.addEventListener('input', function () {
            clearStatus();
            state.filtering = true;
            if (!state.listOpen) {
                state.listOpen = true;
                listbox.hidden = false;
                input.setAttribute('aria-expanded', 'true');
            }
            buildVisibleRows();
            if (state.visibleRows.length) {
                if (state.highlight < 0 || state.highlight >= state.visibleRows.length) {
                    state.highlight = 0;
                }
            } else {
                state.highlight = -1;
            }
            renderListDOM();
            const rows = state.visibleRows;
            const preview =
                state.highlight >= 0 && state.highlight < rows.length && rows[state.highlight].type === 'item'
                    ? rows[state.highlight].item
                    : null;
            if (preview) {
                setExternalFromItem(preview);
            } else {
                setExternalFromItem(getActiveFromState());
            }
        });

        input.addEventListener('keydown', function (e) {
            if (input.disabled) return;
            if (e.key === 'Escape') {
                e.preventDefault();
                closeList();
                state.filtering = false;
                syncInputFromActive();
                clearStatus();
                setExternalFromItem(getActiveFromState());
                return;
            }
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (!state.listOpen) {
                    openList();
                    return;
                }
                setHighlight(state.highlight + 1);
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (!state.listOpen) {
                    state.listOpen = true;
                    listbox.hidden = false;
                    input.setAttribute('aria-expanded', 'true');
                    buildVisibleRows();
                    if (state.visibleRows.length) {
                        state.highlight = state.visibleRows.length - 1;
                    } else {
                        state.highlight = -1;
                    }
                    renderListDOM();
                    return;
                }
                setHighlight(state.highlight - 1);
                return;
            }
            if (e.key === 'Enter') {
                e.preventDefault();
                commitEnter();
            }
        });

        input.addEventListener('blur', function () {
            window.setTimeout(function () {
                if (state.suspendClose) {
                    state.suspendClose = false;
                    input.focus();
                    return;
                }
                closeList();
                state.filtering = false;
                syncInputFromActive();
            }, 150);
        });

        document.addEventListener('click', function (e) {
            if (!toolbar.contains(e.target)) {
                closeList();
                state.filtering = false;
                syncInputFromActive();
            }
        });

        syncInputFromActive();
        setExternalFromItem(getActiveFromState());
    }

    document.addEventListener('DOMContentLoaded', initSpreadsheetToolbar);
})();
