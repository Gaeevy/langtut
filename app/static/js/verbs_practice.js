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

        function markPersonSolved(person, answer) {
            const input = document.querySelector('.verbs-answer-input[data-person="' + person + '"]');
            const row = document.querySelector('.verbs-practice-row[data-person="' + person + '"]');
            if (!input || !row) return;

            input.value = answer;
            input.disabled = true;
            row.classList.add("is-correct");
            solved[person] = true;
            updateScore();
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
                nextBtn.classList.toggle("d-none", totalCorrect !== 5);
            }
        }

        function checkInput(input) {
            const person = input.dataset.person;
            const expected = expectedByPerson[person];
            if (!expected) return;
            if (normalize(input.value) === normalize(expected)) {
                markPersonSolved(person, expected);
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
                markPersonSolved(person, expected);
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
    }

    document.addEventListener("DOMContentLoaded", initVerbsPractice);
})();
