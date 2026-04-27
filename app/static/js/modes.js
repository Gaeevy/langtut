/**
 * Learning mode interaction logic.
 *
 * Handles UI for question modes:
 *   - pick_translation / pick_one : click one of four option buttons
 *   - build_word  : click letter tiles to assemble a word (keyboard shortcuts;
 *                   drag to reorder tiles in the target row)
 *   - build_sentence : click word tiles; drag to reorder in target
 *   - type_example_guided : free typing; only correct next character is accepted
 *
 * All modes submit via the standard answer form with a hidden `user_answer` field.
 * type_answer uses a plain text input and needs no JS here.
 */

(function () {
    'use strict';

    const mode = window.questionMode;

    /** Strip combining marks for loose letter matching (Portuguese diacritics). */
    function stripDiacritics(ch) {
        return ch.normalize('NFD').replace(/\p{M}/gu, '');
    }

    function charsLooselyEqual(a, b) {
        return stripDiacritics(a).toLowerCase() === stripDiacritics(b).toLowerCase();
    }

    function keyMatchesNextGlyph(key, glyph) {
        if (glyph === ' ') {
            return key === ' ';
        }
        if (glyph.length !== 1) {
            return key === glyph;
        }
        if (/\p{L}/u.test(glyph)) {
            return charsLooselyEqual(key, glyph);
        }
        return key === glyph;
    }

    if (mode === 'pick_one' || mode === 'pick_translation') {
        initPickOne();
    } else if (mode === 'build_word' || mode === 'build_sentence') {
        initBuild();
    } else if (mode === 'type_example_guided') {
        initGuidedSentenceTyping();
    }

    // ------------------------------------------------------------------
    // Pick One
    // ------------------------------------------------------------------

    function initPickOne() {
        const form = document.getElementById('mode-form');
        const answerInput = document.getElementById('user-answer-input');
        const buttons = document.querySelectorAll('.pick-one-btn');

        function selectButton(btn) {
            if (!btn) return;
            buttons.forEach(function (b) { b.classList.remove('selected'); });
            btn.classList.add('selected');
            answerInput.value = btn.dataset.value;
            form.requestSubmit();
        }

        buttons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                selectButton(btn);
            });
        });

        document.addEventListener('keydown', function (e) {
            if (e.ctrlKey || e.metaKey || e.altKey) return;
            const t = e.target;
            if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return;
            const n = parseInt(e.key, 10);
            if (n < 1 || n > 4) return;
            const idx = n - 1;
            if (idx >= buttons.length) return;
            e.preventDefault();
            selectButton(buttons[idx]);
        });
    }

    // ------------------------------------------------------------------
    // Guided sentence (levels 6-7)
    // ------------------------------------------------------------------

    function initGuidedSentenceTyping() {
        const text = window.guidedSentenceText;
        if (!text) return;

        const glyphs = Array.from(text);
        const form = document.getElementById('mode-form');
        const hidden = document.getElementById('user-answer-input');
        const target = document.getElementById('guided-target');
        const resetBtn = document.getElementById('guided-reset');
        const submitBtn = document.getElementById('guided-submit');
        if (!form || !hidden || !target) return;

        if (glyphs.length === 0) {
            if (submitBtn) submitBtn.disabled = true;
            return;
        }

        const slots = Array.from(target.querySelectorAll('.guided-slot'));
        let pos = 0;
        let built = '';

        function placeholderFor(glyph) {
            return glyph === ' ' ? '\u00a0' : '\u00b7';
        }

        function setSubmitState() {
            if (submitBtn) {
                submitBtn.disabled = (pos !== glyphs.length);
            }
        }

        function shake() {
            target.classList.add('guided-shake');
            window.setTimeout(function () {
                target.classList.remove('guided-shake');
            }, 400);
        }

        function reset() {
            pos = 0;
            built = '';
            hidden.value = '';
            glyphs.forEach(function (g, i) {
                slots[i].textContent = placeholderFor(g);
                slots[i].classList.remove('guided-revealed');
                slots[i].classList.add('guided-pending');
            });
            setSubmitState();
        }

        function onKeyDown(e) {
            if (e.ctrlKey || e.metaKey || e.altKey) return;
            const t = e.target;
            if (t && (t.tagName === 'TEXTAREA' || (t.tagName === 'INPUT' && t.type !== 'hidden'))) {
                return;
            }

            if (e.key === 'Enter') {
                if (submitBtn && !submitBtn.disabled) {
                    e.preventDefault();
                    form.requestSubmit();
                }
                return;
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                reset();
                return;
            }
            if (e.key === 'Backspace') {
                if (pos <= 0) return;
                e.preventDefault();
                pos -= 1;
                built = built.slice(0, -1);
                hidden.value = built;
                const g = glyphs[pos];
                slots[pos].textContent = placeholderFor(g);
                slots[pos].classList.remove('guided-revealed');
                slots[pos].classList.add('guided-pending');
                setSubmitState();
                return;
            }

            if (pos >= glyphs.length) return;
            if (e.key.length !== 1) return;

            const next = glyphs[pos];
            if (keyMatchesNextGlyph(e.key, next)) {
                e.preventDefault();
                built += next;
                hidden.value = built;
                slots[pos].textContent = next;
                slots[pos].classList.add('guided-revealed');
                slots[pos].classList.remove('guided-pending');
                pos += 1;
                setSubmitState();
            } else {
                e.preventDefault();
                shake();
            }
        }

        document.addEventListener('keydown', onKeyDown);
        if (resetBtn) {
            resetBtn.addEventListener('click', reset);
        }
        if (submitBtn) {
            submitBtn.addEventListener('click', function () {
                if (pos !== glyphs.length) return;
                form.requestSubmit();
            });
        }
        setSubmitState();
    }

    // ------------------------------------------------------------------
    // Build Word / Build Sentence
    // ------------------------------------------------------------------

    function initBuild() {
        const form = document.getElementById('mode-form');
        const answerInput = document.getElementById('user-answer-input');
        const targetArea = document.getElementById('build-target');
        const sourceArea = document.getElementById('build-source');
        const resetBtn = document.getElementById('build-reset');
        const submitBtn = document.getElementById('build-submit');

        const targetTiles = [];

        function syncTilesFromDom() {
            targetTiles.length = 0;
            targetArea.querySelectorAll('.build-tile').forEach(function (t) {
                targetTiles.push(t);
            });
            updateAnswer();
        }

        function moveTileFromSourceToTarget(tile) {
            if (!tile || tile.parentElement !== sourceArea) return;
            targetArea.appendChild(tile);
            targetArea.classList.add('has-tiles');
            const ph = document.getElementById('target-placeholder');
            if (ph) ph.style.display = 'none';
            syncTilesFromDom();
        }

        function moveTileFromTargetToSource(tile) {
            if (!tile || tile.parentElement !== targetArea) return;
            sourceArea.appendChild(tile);
            if (targetArea.querySelectorAll('.build-tile').length === 0) {
                targetArea.classList.remove('has-tiles');
                const ph = document.getElementById('target-placeholder');
                if (ph) ph.style.display = '';
            }
            syncTilesFromDom();
        }

        function clearBuild() {
            const all = Array.from(targetArea.querySelectorAll('.build-tile'));
            all.forEach(function (tile) { sourceArea.appendChild(tile); });
            targetArea.classList.remove('has-tiles');
            const ph = document.getElementById('target-placeholder');
            if (ph) ph.style.display = '';
            syncTilesFromDom();
        }

        // Move tile from source to target (click)
        sourceArea.addEventListener('click', function (e) {
            const tile = e.target.closest('.build-tile');
            if (!tile || tile.parentElement !== sourceArea) return;

            moveTileFromSourceToTarget(tile);
        });

        // Pointer: reorder in target, or click-to-return to source
        const DRAG_THRESHOLD = 6;
        let dragState = null;

        function removeDropIndicator() {
            const old = targetArea.querySelector('.drop-indicator');
            if (old) old.remove();
        }

        function updateDropIndicator(clientX, draggedTile) {
            removeDropIndicator();
            const siblings = Array.from(targetArea.querySelectorAll('.build-tile')).filter(function (t) {
                return t !== draggedTile;
            });
            const indicator = document.createElement('span');
            indicator.className = 'drop-indicator';
            indicator.setAttribute('aria-hidden', 'true');

            let inserted = false;
            for (let i = 0; i < siblings.length; i++) {
                const r = siblings[i].getBoundingClientRect();
                const mid = r.left + r.width / 2;
                if (clientX < mid) {
                    targetArea.insertBefore(indicator, siblings[i]);
                    inserted = true;
                    break;
                }
            }
            if (!inserted) {
                targetArea.appendChild(indicator);
            }
        }

        function finishPointerSession(e) {
            if (!dragState) return;
            const tile = dragState.tile;
            const wasDragging = dragState.dragging;
            const st = dragState;
            dragState = null;

            try {
                tile.releasePointerCapture(st.pointerId);
            } catch (err) { /* ignore */ }

            document.removeEventListener('pointermove', onDocPointerMove);
            document.removeEventListener('pointerup', onDocPointerUp);
            document.removeEventListener('pointercancel', onDocPointerUp);

            if (wasDragging) {
                const indicator = targetArea.querySelector('.drop-indicator');
                const insertBeforeNode = indicator ? indicator.nextSibling : null;
                if (indicator) indicator.remove();

                tile.classList.remove('dragging');
                tile.style.transform = '';

                if (insertBeforeNode) {
                    targetArea.insertBefore(tile, insertBeforeNode);
                } else {
                    targetArea.appendChild(tile);
                }
                syncTilesFromDom();
            } else {
                const dx = e.clientX - st.startX;
                const dy = e.clientY - st.startY;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < DRAG_THRESHOLD) {
                    moveTileFromTargetToSource(tile);
                }
            }
        }

        function onDocPointerMove(e) {
            if (!dragState || e.pointerId !== dragState.pointerId) return;
            const dx = e.clientX - dragState.startX;
            const dy = e.clientY - dragState.startY;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (!dragState.dragging && dist >= DRAG_THRESHOLD) {
                dragState.dragging = true;
                dragState.tile.classList.add('dragging');
            }

            if (dragState.dragging) {
                dragState.tile.style.transform = 'translate(' + dx + 'px,' + dy + 'px)';
                updateDropIndicator(e.clientX, dragState.tile);
            }
        }

        function onDocPointerUp(e) {
            if (!dragState || e.pointerId !== dragState.pointerId) return;
            finishPointerSession(e);
        }

        targetArea.addEventListener('pointerdown', function (e) {
            const tile = e.target.closest('.build-tile');
            if (!tile || tile.parentElement !== targetArea) return;
            if (e.button !== 0) return;

            dragState = {
                tile: tile,
                startX: e.clientX,
                startY: e.clientY,
                dragging: false,
                pointerId: e.pointerId
            };
            try {
                tile.setPointerCapture(e.pointerId);
            } catch (err) { /* ignore */ }

            document.addEventListener('pointermove', onDocPointerMove);
            document.addEventListener('pointerup', onDocPointerUp);
            document.addEventListener('pointercancel', onDocPointerUp);
        });

        // Reset button
        if (resetBtn) {
            resetBtn.addEventListener('click', function () {
                clearBuild();
            });
        }

        // Submit button
        if (submitBtn) {
            submitBtn.addEventListener('click', function () {
                if (targetTiles.length === 0) return;
                updateAnswer();
                form.requestSubmit();
            });
        }

        function updateAnswer() {
            const separator = (mode === 'build_word') ? '' : ' ';
            answerInput.value = targetTiles.map(function (t) {
                return t.dataset.value;
            }).join(separator);

            if (submitBtn) {
                submitBtn.disabled = (targetTiles.length === 0);
            }
        }

        if (mode === 'build_word') {
            initBuildWordKeyboard({
                sourceArea: sourceArea,
                targetArea: targetArea,
                moveTileFromSourceToTarget: moveTileFromSourceToTarget,
                moveLastFromTargetToSource: function () {
                    if (targetTiles.length === 0) return;
                    const last = targetTiles[targetTiles.length - 1];
                    moveTileFromTargetToSource(last);
                },
                clearBuild: clearBuild,
                getTargetLength: function () { return targetTiles.length; },
                submit: function () {
                    if (targetTiles.length === 0) return;
                    updateAnswer();
                    form.requestSubmit();
                },
                shakeSource: function () {
                    sourceArea.classList.add('shake');
                    window.setTimeout(function () {
                        sourceArea.classList.remove('shake');
                    }, 400);
                }
            });
        }

        function initBuildWordKeyboard(opts) {
            function onKeyDown(e) {
                if (e.ctrlKey || e.metaKey || e.altKey) return;
                const t = e.target;
                if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return;

                if (e.key === 'Backspace') {
                    e.preventDefault();
                    opts.moveLastFromTargetToSource();
                    return;
                }
                if (e.key === 'Enter') {
                    if (opts.getTargetLength() > 0) {
                        e.preventDefault();
                        opts.submit();
                    }
                    return;
                }
                if (e.key === 'Escape') {
                    e.preventDefault();
                    opts.clearBuild();
                    return;
                }

                if (e.key.length !== 1) return;

                const tiles = opts.sourceArea.querySelectorAll('.build-tile');
                let found = null;
                for (let i = 0; i < tiles.length; i++) {
                    const val = tiles[i].dataset.value || '';
                    if (val.length && charsLooselyEqual(val, e.key)) {
                        found = tiles[i];
                        break;
                    }
                }
                if (found) {
                    e.preventDefault();
                    opts.moveTileFromSourceToTarget(found);
                } else {
                    opts.shakeSource();
                }
            }

            document.addEventListener('keydown', onKeyDown);
        }
    }

})();
