/*
 * Click-and-drag painting for the availability grid.
 *
 * The grid is a plain table of checkboxes and works without any of this. The
 * script spares students 64 separate clicks: sweep the mouse over a range to
 * paint it, or click a day heading to take the whole column.
 *
 * A mouse press paints the cell itself, so the browser's own toggle would undo
 * it; that one is suppressed in the click handler below. Touch is left alone
 * instead, so a tap toggles natively and a swipe still scrolls the page.
 */
(function () {
  "use strict";

  function isSlot(element) {
    return Boolean(element) && element.classList.contains("availability-slot");
  }

  function setUp(grid) {
    var painting = false;
    var paintTo = true;
    var touching = false;

    function paint(slot) {
      if (isSlot(slot) && slot.checked !== paintTo) {
        slot.checked = paintTo;
      }
    }

    grid.addEventListener("pointerdown", function (event) {
      touching = event.pointerType === "touch";
      if (touching || !isSlot(event.target)) {
        return;
      }
      // Take the press ourselves so dragging doesn't select the whole table.
      event.preventDefault();
      painting = true;
      paintTo = !event.target.checked;
      paint(event.target);
      event.target.focus();
    });

    grid.addEventListener("pointermove", function (event) {
      if (painting) {
        paint(document.elementFromPoint(event.clientX, event.clientY));
      }
    });

    grid.addEventListener("click", function (event) {
      // detail is 0 for keyboard-generated clicks, which must still toggle.
      if (isSlot(event.target) && event.detail !== 0 && !touching) {
        event.preventDefault();
      }
    });

    document.addEventListener("pointerup", function () {
      painting = false;
    });
    document.addEventListener("pointercancel", function () {
      painting = false;
    });

    // Day headings toggle their whole column: on unless it is already full.
    grid
      .querySelectorAll("[data-availability-day]")
      .forEach(function (heading) {
        var column = Number(heading.dataset.availabilityDay);
        heading.classList.add("availability-day-toggle");
        heading.title = "Select or clear this whole day";
        heading.addEventListener("click", function () {
          var slots = Array.prototype.map.call(
            grid.querySelectorAll("tbody tr"),
            function (row) {
              return row.querySelectorAll(".availability-slot")[column];
            },
          );
          var fill = slots.some(function (slot) {
            return !slot.checked;
          });
          slots.forEach(function (slot) {
            slot.checked = fill;
          });
        });
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-availability-grid]").forEach(setUp);
  });
})();
