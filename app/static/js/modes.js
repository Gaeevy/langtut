/**
 * Learning mode interaction logic.
 *
 * Handles UI for question modes:
 *   - pick_translation / pick_one : click one of four option buttons
 *   - build_word  : click letter tiles to assemble a word
 *   - build_sentence : click word tiles to assemble a sentence
 *
 * All modes submit via the standard answer form with a hidden `user_answer` field.
 * type_answer uses a plain text input and needs no JS here.
 */

(function () {
    'use strict';

    const mode = window.questionMode;

    if (mode === 'pick_one' || mode === 'pick_translation') {
        initPickOne();
    } else if (mode === 'build_word' || mode === 'build_sentence') {
        initBuild();
    }

    // ------------------------------------------------------------------
    // Pick One
    // ------------------------------------------------------------------

    function initPickOne() {
        const form = document.getElementById('mode-form');
        const answerInput = document.getElementById('user-answer-input');
        const buttons = document.querySelectorAll('.pick-one-btn');

        buttons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                // Visually mark selected
                buttons.forEach(function (b) { b.classList.remove('selected'); });
                btn.classList.add('selected');

                // Fill hidden input and submit (requestSubmit triggers the submit event
                // so card.js can intercept it for AJAX + audio autoplay)
                answerInput.value = btn.dataset.value;
                form.requestSubmit();
            });
        });
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

        // Track tiles currently in the target area (in order)
        let targetTiles = [];

        // Move tile from source to target
        sourceArea.addEventListener('click', function (e) {
            const tile = e.target.closest('.build-tile');
            if (!tile || tile.parentElement !== sourceArea) return;

            targetArea.appendChild(tile);
            targetTiles.push(tile);
            targetArea.classList.add('has-tiles');
            updateAnswer();
        });

        // Move tile back from target to source
        targetArea.addEventListener('click', function (e) {
            const tile = e.target.closest('.build-tile');
            if (!tile || tile.parentElement !== targetArea) return;

            sourceArea.appendChild(tile);
            targetTiles = targetTiles.filter(function (t) { return t !== tile; });
            if (targetTiles.length === 0) {
                targetArea.classList.remove('has-tiles');
            }
            updateAnswer();
        });

        // Reset button
        if (resetBtn) {
            resetBtn.addEventListener('click', function () {
                // Move all tiles back to source in original order
                const all = Array.from(targetArea.querySelectorAll('.build-tile'));
                all.forEach(function (tile) { sourceArea.appendChild(tile); });
                targetTiles = [];
                targetArea.classList.remove('has-tiles');
                updateAnswer();
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

            // Enable/disable submit
            if (submitBtn) {
                submitBtn.disabled = (targetTiles.length === 0);
            }
        }
    }

})();
