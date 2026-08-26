/*
 * Click-and-drag painting for the availability grid.
 *
 * The grid is a plain table of checkboxes and works without any of this; the
 * script only spares students 64 individual clicks by letting them sweep over
 * a range, or click a day heading to take the whole column.
 */
(function () {
  "use strict";

  function slotsOf(grid) {
    return Array.prototype.slice.call(
      grid.querySelectorAll("input.availability-slot"),
    );
  }

  function setUp(grid) {
    var painting = false;
    var paintTo = true;

    function paint(slot) {
      if (slot && slot.checked !== paintTo) {
        slot.checked = paintTo;
      }
    }

    function slotAt(event) {
      var element = document.elementFromPoint(event.clientX, event.clientY);
      return element && element.classList.contains("availability-slot")
        ? element
        : null;
    }

    grid.addEventListener("pointerdown", function (event) {
      var slot = event.target;
      if (!slot.classList || !slot.classList.contains("availability-slot")) {
        return;
      }
      // Take the click ourselves so the drag doesn't select the whole table,
      // then toggle by hand since preventDefault() suppresses the native one.
      event.preventDefault();
      painting = true;
      paintTo = !slot.checked;
      paint(slot);
      slot.focus();
    });

    grid.addEventListener("pointermove", function (event) {
      if (painting) {
        paint(slotAt(event));
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
          var slots = slotsOf(grid).filter(function (slot) {
            return (
              slot.closest("tr").querySelectorAll(".availability-slot")[
                column
              ] === slot
            );
          });
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
