/**
 * Verbs index behavior:
 * - persist selected tense in localStorage
 * - apply stored tense when URL has no explicit tense_id
 */
(function () {
    "use strict";

    const STORAGE_KEY = "verbs:selected_tense_id";

    function initVerbsIndex() {
        const select = document.getElementById("tense_id");
        const form = document.getElementById("verbs-tense-form");
        if (!select || !form) return;

        const url = new URL(window.location.href);
        const explicitTense = url.searchParams.get("tense_id");
        const storedTense = window.localStorage.getItem(STORAGE_KEY);
        const availableValues = Array.from(select.options).map(function (option) {
            return option.value;
        });

        if (!explicitTense && storedTense && availableValues.includes(storedTense)) {
            url.searchParams.set("tense_id", storedTense);
            window.location.replace(url.toString());
            return;
        }

        if (select.value) {
            window.localStorage.setItem(STORAGE_KEY, select.value);
        }

        select.addEventListener("change", function () {
            if (select.value) {
                window.localStorage.setItem(STORAGE_KEY, select.value);
            }
            form.submit();
        });
    }

    document.addEventListener("DOMContentLoaded", initVerbsIndex);
})();
