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

/**
 * Build segmented learn progress HTML (must match card.html structure).
 */
function buildLearnProgressHtml(data) {
    const taskIndex = data.task_index ?? 0;
    const taskTotal = data.task_total ?? 0;
    const sections = data.progress_sections;
    const pct = taskTotal ? Math.round((taskIndex / taskTotal) * 100) : 0;

    if (!sections || sections.length === 0) {
        return `
        <div class="progress-container">
            <div class="progress" style="height:10px">
                <div class="progress-bar pastel-progress-study" role="progressbar"
                     style="width:${pct}%" aria-valuenow="${taskIndex}" aria-valuemin="0" aria-valuemax="${taskTotal}"></div>
            </div>
        </div>`;
    }

    const cols = sections.map(function (s) {
        const flex = s.length != null ? s.length : 1;
        const fp = s.fill_pct != null ? s.fill_pct : 0;
        const mode = s.mode || 'type_answer';
        const lab = escapeHtml(s.label || '');
        const cur = s.is_current ? ' learn-progress-label-current' : '';
        const titleAttr = escapeHtml(s.label || '');
        return `
            <div class="learn-progress-col" style="flex:${flex} 1 0%;min-width:0">
                <div class="progress learn-segment-track" style="height:10px">
                    <div class="progress-bar learn-segment-fill learn-seg-${mode}" style="width:${fp}%"></div>
                </div>
                <small class="learn-progress-label${cur}" title="${titleAttr}">
                    <span class="learn-progress-dot learn-seg-dot-${mode}" aria-hidden="true"></span>${lab}
                </small>
            </div>`;
    }).join('');

    return `
        <div class="progress-container">
            <div class="learn-progress-track mb-1">${cols}</div>
        </div>`;
}

function renderFeedback(data) {
    const { correct, card, question_mode, task_index, task_total } = data;
    const correctnessClass = correct ? 'is-correct' : 'is-incorrect';

    const messages = {
        pick_translation: correct ? 'Nice match!' : 'Not quite \u2014 the correct translation is shown below.',
        pick_one:       correct ? 'Good pick!'              : 'Wrong choice \u2014 the correct word is shown below.',
        build_sentence: correct ? 'Sentence correct!'       : 'Not quite \u2014 the correct sentence is shown below.',
        build_word:     correct ? 'Word spelled correctly!'  : 'Not quite \u2014 the correct word is shown below.',
        write_example:  correct ? 'Example matches!'       : 'Not quite \u2014 the example is shown below.',
        type_answer:    correct ? 'Correct!'                 : 'Not quite \u2014 the correct word is shown below.'
    };
    const feedbackMsg = messages[question_mode] || messages.type_answer;

    const levelPct = (card.level != null) ? Math.round((card.level / 8) * 100) : 0;
    const levelSat = (card.level != null) ? (0.6 + card.level * 0.05).toFixed(2) : '0.85';

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

    const progressBlock = buildLearnProgressHtml(data);

    const html = `
        <div class="text-center mb-4 learn-progress-wrap">
            ${progressBlock}
        </div>
        <div class="text-center">
            <div class="feedback-indicator mb-3">
                <div class="${correct ? 'success' : 'error'}-indicator">
                    <i class="bi bi-${correct ? 'check-circle' : 'x-circle'}-fill"></i>
                </div>
            </div>
            <p class="text-muted small mb-2 feedback-text">${feedbackMsg}</p>
            <div class="language-card feedback-card mb-4 ${correctnessClass}" data-level="${card.level}" style="--level-pct: ${levelPct}%; --level-sat: ${levelSat}">
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
                        <span class="level-badge">L${card.level}</span>
                        ${difficultyHtml}
                    </div>
                </div>
            </div>
            <div class="d-grid gap-2 mt-3">
                <a href="/learn/next_card" class="btn btn-primary" id="next-card-btn">Next Card</a>
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

}

// ---- Form Interception ----

function setupAjaxSubmission() {
    if (window.cardMode !== 'learn') return;

    const form = document.getElementById('mode-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        let userAnswer;
        if (window.questionMode === 'type_answer' || window.questionMode === 'write_example') {
            const textInput = form.querySelector('input[name="user_answer"], textarea[name="user_answer"]');
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

// ---- Keyboard Navigation ----

function setupKeyboardNavigation() {
    document.addEventListener('keydown', (event) => {
        // Enter on feedback view (learn mode): advance to next card.
        if (event.key === 'Enter') {
            const nextBtn = document.getElementById('next-card-btn');
            if (nextBtn) {
                event.preventDefault();
                nextBtn.click();
                return;
            }
        }

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
        const exampleTa = document.querySelector('textarea[name="user_answer"]');
        if (answerInput) answerInput.focus();
        else if (exampleTa) exampleTa.focus();
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
