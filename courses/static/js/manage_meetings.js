/*
 * Client-side helpers for the "Manage Meetings" formset.
 *
 * Two things live here:
 *   - Adding blank meeting rows by cloning the hidden empty-form template.
 *   - A "recurring schedule" generator that fills in a whole term's worth of
 *     evenly spaced rows at once, so a leader with a weekly class doesn't have
 *     to type fifteen dates by hand.
 *
 * The generator is pure convenience: it only populates the same formset rows
 * the "+ Add another meeting" button creates, so the server sees an ordinary
 * formset POST and nothing is saved until the form is submitted.
 */
(function () {
  "use strict";

  /*
   * All arithmetic below works on the "YYYY-MM-DDTHH:MM" strings that
   * <input type="datetime-local"> uses, which the server reads as wall-clock
   * time in the site's time zone. Dates are stepped through UTC so that
   * neither the browser's time zone nor a daylight-saving shift in it can
   * nudge the time of day: a 4:00pm class stays a 4:00pm class across the
   * autumn change.
   */
  const LOCAL_DATETIME_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/;

  function parseDateTime(value) {
    const match = LOCAL_DATETIME_RE.exec(value || "");
    if (!match) return null;
    return {
      year: Number(match[1]),
      month: Number(match[2]),
      day: Number(match[3]),
      hour: Number(match[4]),
      minute: Number(match[5]),
    };
  }

  function parseDate(value) {
    return parseDateTime((value || "") + "T00:00");
  }

  function addDays(parts, days) {
    const stepped = new Date(
      Date.UTC(parts.year, parts.month - 1, parts.day + days),
    );
    return {
      year: stepped.getUTCFullYear(),
      month: stepped.getUTCMonth() + 1,
      day: stepped.getUTCDate(),
      hour: parts.hour,
      minute: parts.minute,
    };
  }

  function pad(number) {
    return String(number).padStart(2, "0");
  }

  function formatDateTime(parts) {
    return (
      parts.year +
      "-" +
      pad(parts.month) +
      "-" +
      pad(parts.day) +
      "T" +
      pad(parts.hour) +
      ":" +
      pad(parts.minute)
    );
  }

  /** Whole days from `from` to `to`, both plain date-time parts. */
  function daysBetween(from, to) {
    const MS_PER_DAY = 24 * 60 * 60 * 1000;
    const start = Date.UTC(from.year, from.month - 1, from.day);
    const end = Date.UTC(to.year, to.month - 1, to.day);
    return Math.round((end - start) / MS_PER_DAY);
  }

  function formatDateForHumans(parts) {
    return new Date(
      Date.UTC(parts.year, parts.month - 1, parts.day),
    ).toLocaleDateString(undefined, {
      timeZone: "UTC",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    // === Delete checkbox visual feedback ===
    function setupDeleteCheckbox(checkbox) {
      if (!checkbox) return;
      checkbox.addEventListener("change", function () {
        const row = this.closest(".formset-row");
        row.classList.toggle("to-delete", this.checked);
      });
      // Set initial state if already checked
      if (checkbox.checked) {
        checkbox.closest(".formset-row").classList.add("to-delete");
      }
    }

    document
      .querySelectorAll('input[name$="-DELETE"]')
      .forEach(setupDeleteCheckbox);

    // === Adding blank rows ===
    const addButton = document.getElementById("add-form-btn");
    const template = document.getElementById("empty-form-template");
    const totalFormsInput = document.getElementById("id_form-TOTAL_FORMS");
    const container = document.getElementById("new-meetings-section");

    /** Clone the empty form template into a new row; returns the row. */
    function addForm() {
      const formCount = parseInt(totalFormsInput.value, 10);
      const newForm = template.content.cloneNode(true);

      // Replace __prefix__ with form index in all attributes
      newForm.querySelectorAll("*").forEach((el) => {
        ["name", "id", "for"].forEach((attr) => {
          const value = el.getAttribute(attr);
          if (value && value.includes("__prefix__")) {
            el.setAttribute(attr, value.replace(/__prefix__/g, formCount));
          }
        });
      });

      const formRow = newForm.querySelector(".formset-row");
      formRow.dataset.formIndex = formCount;

      // Insert before button
      container.insertBefore(newForm, addButton);

      // Update the total forms count
      totalFormsInput.value = formCount + 1;

      setupDeleteCheckbox(formRow.querySelector('input[name$="-DELETE"]'));

      return formRow;
    }

    addButton.addEventListener("click", function () {
      addForm();
    });

    // === Recurring schedule generator ===
    const panel = document.getElementById("recurring-panel");
    if (!panel) return;

    const startInput = document.getElementById("recurring-start");
    const intervalSelect = document.getElementById("recurring-interval");
    const countInput = document.getElementById("recurring-count");
    const titleInput = document.getElementById("recurring-title");
    const generateButton = document.getElementById("recurring-generate-btn");
    const feedback = document.getElementById("recurring-feedback");

    const maxMeetings = parseInt(panel.dataset.maxMeetings, 10) || 52;
    const semesterEnd = parseDate(panel.dataset.semesterEnd);

    // Suggestions stop as soon as the leader types their own value.
    let startIsSuggested = true;
    let countIsSuggested = true;
    startInput.addEventListener("input", function () {
      startIsSuggested = false;
    });
    countInput.addEventListener("input", function () {
      countIsSuggested = false;
    });

    function interval() {
      return parseInt(intervalSelect.value, 10);
    }

    /** The latest start time already entered, so we can continue the series. */
    function lastExistingMeeting() {
      let latest = null;
      document
        .querySelectorAll('input[name$="-start_time"]')
        .forEach(function (input) {
          const parts = parseDateTime(input.value);
          if (!parts) return;
          if (!latest || formatDateTime(parts) > formatDateTime(latest)) {
            latest = parts;
          }
        });
      return latest;
    }

    /** Prefill the first date with the meeting after the last one entered. */
    function suggestStart() {
      if (!startIsSuggested) return;
      const last = lastExistingMeeting();
      startInput.value = last ? formatDateTime(addDays(last, interval())) : "";
    }

    /** Prefill the count with however many meetings fit before term ends. */
    function suggestCount() {
      if (!countIsSuggested) return;
      const start = parseDateTime(startInput.value);
      if (!start || !semesterEnd) return;
      const span = daysBetween(start, semesterEnd);
      if (span < 0) return;
      const fits = Math.floor(span / interval()) + 1;
      countInput.value = Math.min(fits, maxMeetings);
    }

    function refreshSuggestions() {
      suggestStart();
      suggestCount();
    }

    intervalSelect.addEventListener("change", refreshSuggestions);
    startInput.addEventListener("change", suggestCount);
    refreshSuggestions();

    function report(message, isError) {
      feedback.textContent = message;
      feedback.className = isError ? "text-danger mt-2" : "text-success mt-2";
    }

    generateButton.addEventListener("click", function () {
      const start = parseDateTime(startInput.value);
      if (!start) {
        report("Pick the date and time of the first meeting first.", true);
        startInput.focus();
        return;
      }

      const count = parseInt(countInput.value, 10);
      if (!count || count < 1) {
        report("Enter how many meetings to generate.", true);
        countInput.focus();
        return;
      }
      if (count > maxMeetings) {
        report("That's more than " + maxMeetings + " meetings.", true);
        countInput.focus();
        return;
      }

      const step = interval();
      const titleTemplate = titleInput.value.trim();
      let last = start;

      for (let i = 0; i < count; i++) {
        last = addDays(start, i * step);
        const row = addForm();
        row.querySelector('input[name$="-start_time"]').value =
          formatDateTime(last);
        if (titleTemplate) {
          row.querySelector('input[name$="-title"]').value =
            titleTemplate.replace(/\{n\}/g, String(i + 1));
        }
      }

      report(
        "Added " +
          count +
          (count === 1 ? " meeting: " : " meetings: ") +
          formatDateForHumans(start) +
          (count === 1 ? "" : " through " + formatDateForHumans(last)) +
          ". Edit or delete any of them below, then save.",
        false,
      );

      // Continue the series if the leader generates a second batch.
      startIsSuggested = true;
      countIsSuggested = true;
      refreshSuggestions();
    });
  });
})();
