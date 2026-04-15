/**
 * Card page JavaScript
 *
 * Handles card interactions, keyboard navigation, TTS prefetching,
 * and AJAX answer submission with in-page feedback rendering.
 *
 * The AJAX approach keeps everything on the same page, which preserves
 * the audio context across answer→feedback transitions. This is critical
 * for Chrome iOS where audio.play() is blocked without a user gesture
 * on each new page load.
 */

let unlockAttempted = false;

// ---- Audio Unlock ----

async function unlockAudioOnFirstInteraction() {
    if (unlockAttempted || !window.ttsManager) return;
    if (window.ttsManager.isUnlocked()) {
        unlockAttempted = true;
        return;
    }
    unlockAttempted = true;
    try {
        await window.ttsManager.unlockAudio();
    } catch (error) {
        console.error('Audio unlock error:', error);
    }
}

// ---- Review Mode Helpers ----

function flipCard() {
    if (window.cardMode === 'review' && window.reviewFlipUrl) {
        window.location.href = window.reviewFlipUrl;
    }
}

function toggleEquivalent() {
    const content = document.getElementById('equivalent-content');
    const button = document.querySelector('.equivalent-toggle button');
    if (!content || !button) return;

    if (content.style.display === 'none' || content.style.display === '') {
        content.style.display = 'block';
        button.innerHTML = '<i class="bi bi-eye-slash"></i> Hide hint';
    } else {
        content.style.display = 'none';
        button.innerHTML = '<i class="bi bi-eye"></i> Show hint';
    }
}

// ---- TTS Prefetching ----

async function prefetchCardTTS() {
    if (!window.ttsManager) return;

    const ready = await window.ttsManager.waitForService();
    if (!ready) return;

    await window.ttsManager.speakCard(
        window.cardData.word,
        window.cardData.example,
        false,
        window.cardContext.spreadsheetId,
        window.cardContext.sheetGid
    );
}

// ---- AJAX Answer Submission ----

/**
 * Play card audio directly from the TTS cache.
 * Called within the user gesture context so Chrome iOS allows playback.
 */
function playCardAudioFromCache() {
    const tts = window.ttsManager;
    if (!tts || !tts.isEnabled()) return false;

    const { word, example } = window.cardData;
    if (!word) return false;

    const wordAudio = tts.audioCache.get(tts.getCacheKey(word));
    if (!wordAudio) return false;

    const exampleAudio = example
        ? tts.audioCache.get(tts.getCacheKey(example))
        : null;

    tts.playAudio(wordAudio)
        .then(() => exampleAudio && tts.playAudio(exampleAudio))
        .catch(err => console.warn('Cache audio playback failed:', err));

    return true;
}

/**
 * Submit answer via AJAX, play audio, render feedback in-page.
 */
async function submitAnswerAjax(userAnswer) {
    const tts = window.ttsManager;

    // Unlock audio within user gesture context (creates primed element on Chrome iOS)
    if (tts && !tts.isUnlocked()) {
        await tts.unlockAudio();
    }

    // Play audio from prefetch cache immediately (still in gesture context)
    const audioStarted = playCardAudioFromCache();

    const response = await fetch('/learn/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_answer: userAnswer })
    });

    if (!response.ok) throw new Error(`Server error: ${response.status}`);

    const data = await response.json();

    if (!data.success) {
        window.location.href = '/';
        return;
    }

    renderFeedback(data);

    // If cache missed, play via primed element (works on Chrome iOS even after async)
    if (!audioStarted && tts && tts.isEnabled()) {
        try {
            const ready = await tts.waitForService(3000);
            if (ready) {
                tts.speakCard(
                    data.card.word, data.card.example, true,
                    data.spreadsheet_id, data.sheet_gid
                );
            }
        } catch (err) {
            console.warn('Fallback audio playback failed:', err);
        }
    }

    // Update URL so a page refresh loads the server-rendered feedback page
    const correctParam = data.correct ? 'yes' : 'no';
    history.replaceState(null, '', `/learn/feedback/${correctParam}`);
}

// ---- Feedback Rendering ----

function escapeHtml(str) {
    if (!str) return '';
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
}

function renderFeedback(data) {
    const { correct, card, level_change, question_mode, task_index, task_total } = data;

    const messages = {
        pick_one:       correct ? 'Good pick!'              : 'Wrong choice \u2014 the correct translation is shown below.',
        build_sentence: correct ? 'Sentence correct!'       : 'Not quite \u2014 the correct sentence is shown below.',
        build_word:     correct ? 'Word spelled correctly!'  : 'Not quite \u2014 the correct word is shown below.',
        type_answer:    correct ? 'Correct!'                 : 'Not quite \u2014 the correct word is shown below.'
    };
    const feedbackMsg = messages[question_mode] || messages.type_answer;

    let levelDotsHtml = '';
    for (let i = 0; i < 8; i++) {
        let cls = 'level-dot';
        if (i < card.level) cls += ' completed';
        else if (i === card.level) cls += ' current';
        levelDotsHtml += `<div class="${cls}" data-level="${i}"></div>`;
    }

    const difficultyHtml = correct ? `
        <div class="difficulty-rating mt-4">
            <p class="small text-muted mb-2">How was this card?</p>
            <div class="btn-group" role="group">
                <a href="/learn/rate/${task_index}/easy" class="btn btn-success btn-sm">\uD83D\uDE0A Easy</a>
                <a href="/learn/rate/${task_index}/difficult" class="btn btn-warning btn-sm">\uD83D\uDE30 Difficult</a>
            </div>
        </div>` : '';

    const exHtml = card.example
        ? `<p class="card-example text-muted fst-italic mb-3" style="font-size:1.1rem;line-height:1.4">${escapeHtml(card.example)}</p>`
        : '';
    const exTransHtml = card.example_translation
        ? `<p class="card-example-translation small text-muted fst-italic mb-3" style="opacity:.8"><em>${escapeHtml(card.example_translation)}</em></p>`
        : '';

    const pct = task_total ? Math.round((task_index / task_total) * 100) : 0;

    const html = `
        <div class="text-center mb-4">
            <div class="progress-container">
                <div class="progress" style="height:10px">
                    <div class="progress-bar pastel-progress-study" role="progressbar"
                         style="width:${pct}%" aria-valuenow="${task_index}" aria-valuemin="0" aria-valuemax="${task_total}"></div>
                </div>
                <div class="d-flex justify-content-between mt-1">
                    <small>Task ${task_index + 1} of ${task_total}</small>
                    <small>${pct}% done</small>
                </div>
            </div>
        </div>
        <div class="text-center">
            <div class="feedback-indicator mb-3">
                <div class="${correct ? 'success' : 'error'}-indicator">
                    <i class="bi bi-${correct ? 'check-circle' : 'x-circle'}-fill"></i>
                </div>
            </div>
            <p class="text-muted small mb-2">${feedbackMsg}</p>
            <div class="language-card feedback-card ${correct ? 'correct-card' : 'incorrect-card'} mb-4">
                <div class="row">
                    <div class="col-md-12 text-center">
                        <div class="word-with-audio mb-3">
                            <h2 class="card-word-main text-dark fw-bold mb-2">${escapeHtml(card.word)}</h2>
                            <button type="button" class="btn btn-primary btn-sm" id="speak-card-btn" title="Listen to pronunciation">
                                <i class="bi bi-volume-up"></i>
                            </button>
                        </div>
                        <p class="card-translation h5 text-secondary mb-3">${escapeHtml(card.translation)}</p>
                        ${exHtml}
                        ${exTransHtml}
                        <div class="level-progress-container">
                            <div class="level-tooltip">Level ${card.level}</div>
                            <div class="level-progress">${levelDotsHtml}</div>
                        </div>
                        ${difficultyHtml}
                    </div>
                </div>
            </div>
            <div class="d-grid gap-2 mt-3">
                <a href="/learn/next_card" class="btn btn-primary">Next Card</a>
            </div>
        </div>`;

    document.querySelector('.card-container').innerHTML = html;

    // Wire up the speak button
    const speakBtn = document.getElementById('speak-card-btn');
    if (speakBtn && window.ttsManager) {
        speakBtn.addEventListener('click', async () => {
            if (!window.ttsManager.isUnlocked()) await window.ttsManager.unlockAudio();
            const ready = await window.ttsManager.waitForService();
            if (ready) {
                window.ttsManager.speakCard(
                    card.word, card.example, true,
                    data.spreadsheet_id, data.sheet_gid
                );
            }
        });
    }

    // Animate level-dot change
    if (level_change) {
        const dots = document.querySelectorAll('.level-dot');
        const dot = dots[card.level];
        if (dot) {
            dot.classList.add('level-changed');
            setTimeout(() => dot.classList.remove('level-changed'), 1000);
        }
    }
}

// ---- Form Interception ----

function setupAjaxSubmission() {
    if (window.cardMode !== 'learn') return;

    const form = document.getElementById('mode-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        let userAnswer;
        if (window.questionMode === 'type_answer') {
            const textInput = form.querySelector('input[type="text"][name="user_answer"]');
            userAnswer = textInput ? textInput.value.trim() : '';
        } else {
            const hiddenInput = document.getElementById('user-answer-input');
            userAnswer = hiddenInput ? hiddenInput.value.trim() : '';
        }

        if (!userAnswer) return;

        // Disable all submit controls to prevent double-tap
        form.querySelectorAll('button, input[type="submit"]').forEach(b => { b.disabled = true; });

        try {
            await submitAnswerAjax(userAnswer);
        } catch (error) {
            console.error('AJAX submission failed, falling back to form POST:', error);
            form.submit(); // direct call bypasses the event listener
        }
    });
}

// ---- Keyboard Navigation (review mode) ----

function setupKeyboardNavigation() {
    document.addEventListener('keydown', (event) => {
        if (window.cardMode !== 'review') return;
        switch (event.key) {
            case 'ArrowLeft':
                event.preventDefault();
                document.getElementById('nav-prev')?.click();
                break;
            case 'ArrowRight':
                event.preventDefault();
                document.getElementById('nav-next')?.click();
                break;
            case ' ':
                event.preventDefault();
                flipCard();
                break;
        }
    });
}

// ---- Initialization ----

function initCardPage() {
    if (window.cardMode === 'learn') {
        const answerInput = document.querySelector('input[type="text"][name="user_answer"]');
        if (answerInput) answerInput.focus();
    }

    setupKeyboardNavigation();

    // First-click audio unlock for mobile
    const unlockOnce = () => unlockAudioOnFirstInteraction();
    document.addEventListener('click', unlockOnce, { once: true });
    document.addEventListener('touchstart', unlockOnce, { once: true });

    prefetchCardTTS();
    setupAjaxSubmission();
}

document.addEventListener('DOMContentLoaded', initCardPage);
