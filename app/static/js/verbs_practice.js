/**
 * Interactive verbs practice with live validation.
 */
(function () {
    "use strict";

    function normalize(value) {
        return (value || "").trim().toLocaleLowerCase();
    }

    function initVerbsPractice() {
        const root = document.querySelector(".verbs-practice-page");
        const answersDataEl = document.getElementById("verbs-answers-data");
        if (!root || !answersDataEl) return;

        const expectedByPerson = JSON.parse(answersDataEl.textContent || "{}");
        const progressUrl = root.dataset.progressUrl;
        const nextBaseUrl = root.dataset.nextUrl;
        const infinitiveId = Number(root.dataset.infinitiveId);
        const tenseId = Number(root.dataset.tenseId);

        const scoreEl = document.getElementById("verbs-live-score");
        const footerProgressEl = document.getElementById("verbs-footer-progress");
        const nextBtn = document.getElementById("verbs-next-btn");
        const inputs = Array.from(document.querySelectorAll(".verbs-answer-input"));
        const personButtons = Array.from(document.querySelectorAll(".verbs-person-btn"));

        const solved = {};
        let saving = false;
        let enterNextBound = false;

        function differsForPerson(person) {
            const check = document.querySelector(
                '.verbs-row-check[data-person="' + person + '"]'
            );
            if (!check) return true;
            return check.getAttribute("data-differs") === "true";
        }

        function focusNextUnsolvedAfter(person) {
            const rows = Array.from(document.querySelectorAll(".verbs-practice-row"));
            let seen = false;
            for (let i = 0; i < rows.length; i += 1) {
                const row = rows[i];
                if (row.dataset.person === String(person)) {
                    seen = true;
                    continue;
                }
                if (!seen) continue;
                const inp = row.querySelector(".verbs-answer-input");
                if (inp && !inp.disabled) {
                    inp.focus();
                    return;
                }
            }
        }

        function bindEnterToNextWhenComplete() {
            if (enterNextBound || !nextBtn) return;
            enterNextBound = true;
            document.addEventListener("keydown", function (e) {
                if (e.key !== "Enter" || e.ctrlKey || e.metaKey || e.altKey) return;
                if (nextBtn.classList.contains("d-none")) return;
                const t = e.target;
                if (t && t.tagName === "INPUT" && !t.disabled) return;
                if (t && t.tagName === "TEXTAREA" && !t.disabled) return;
                e.preventDefault();
                nextBtn.click();
            });
        }

        function markPersonSolved(person, answer, opts) {
            const options = opts || {};
            const fromTyping = Boolean(options.fromTyping);

            const input = document.querySelector('.verbs-answer-input[data-person="' + person + '"]');
            const row = document.querySelector('.verbs-practice-row[data-person="' + person + '"]');
            const check = document.querySelector('.verbs-row-check[data-person="' + person + '"]');
            if (!input || !row || !check) return;

            input.value = answer;
            input.disabled = true;
            row.classList.add("is-correct");
            check.classList.remove("verbs-row-check--irregular", "verbs-row-check--regular");
            const irregular = differsForPerson(person);
            if (irregular) {
                check.classList.add("verbs-row-check--irregular");
                check.textContent = "\u2605";
                check.setAttribute("aria-label", "Correct: irregular or spelling-changed form");
            } else {
                check.classList.add("verbs-row-check--regular");
                check.textContent = "\u2713";
                check.setAttribute("aria-label", "Correct: follows regular conjugation pattern");
            }
            check.removeAttribute("aria-hidden");
            solved[person] = true;
            updateScore();

            if (fromTyping) {
                window.setTimeout(function () {
                    focusNextUnsolvedAfter(person);
                }, 0);
            }
        }

        function updateScore() {
            const totalCorrect = Object.keys(solved).filter(function (person) {
                return solved[person];
            }).length;
            if (scoreEl) {
                scoreEl.textContent = "Score: " + totalCorrect + "/5";
            }
            if (footerProgressEl) {
                footerProgressEl.textContent = totalCorrect + "/5 correct";
            }
            if (nextBtn) {
                const allDone = totalCorrect === 5;
                nextBtn.classList.toggle("d-none", !allDone);
                if (allDone) {
                    bindEnterToNextWhenComplete();
                }
            }
        }

        function checkInput(input) {
            const person = input.dataset.person;
            const expected = expectedByPerson[person];
            if (!expected) return;
            if (normalize(input.value) === normalize(expected)) {
                markPersonSolved(person, expected, { fromTyping: true });
            }
        }

        inputs.forEach(function (input) {
            input.addEventListener("input", function () {
                if (!input.disabled) {
                    checkInput(input);
                }
            });
        });

        personButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                const person = button.dataset.person;
                const expected = expectedByPerson[person];
                if (!expected) return;
                markPersonSolved(person, expected, { fromTyping: false });
            });
        });

        if (nextBtn) {
            nextBtn.addEventListener("click", function () {
                if (saving) return;
                saving = true;
                nextBtn.disabled = true;

                fetch(progressUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        infinitive_id: infinitiveId,
                        tense_id: tenseId,
                        completed: true,
                    }),
                })
                    .then(function (response) {
                        return response.json();
                    })
                    .then(function () {
                        const nextUrl = new URL(nextBaseUrl, window.location.origin);
                        nextUrl.searchParams.set("tense_id", String(tenseId));
                        window.location.href = nextUrl.toString();
                    })
                    .catch(function () {
                        saving = false;
                        nextBtn.disabled = false;
                    });
            });
        }

        updateScore();
        if (inputs.length > 0) {
            inputs[0].focus();
        }
    }

    document.addEventListener("DOMContentLoaded", initVerbsPractice);
})();
