/*
 * Click-and-drag painting for the availability grid.
 *
 * The grid is a plain table of checkboxes and works without any of this. The
 * script spares students 64 separate clicks: sweep the mouse over a block to
 * paint it, or click a day heading to take the whole column.
 *
 * A drag paints the whole rectangle between where it started and where the
 * pointer is now, rather than only the cells a pointermove happened to land
 * on -- move the mouse quickly and those leave gaps. The rectangle is redrawn
 * from a snapshot on every move, so pulling back over a cell releases it again
 * the way when2meet does.
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
    var rows = Array.prototype.map.call(
      grid.querySelectorAll("tbody tr"),
      function (row) {
        return Array.prototype.slice.call(
          row.querySelectorAll(".availability-slot"),
        );
      },
    );
    var cellAt = new Map();
    rows.forEach(function (row, r) {
      row.forEach(function (slot, c) {
        cellAt.set(slot, { row: r, column: c });
      });
    });

    var anchor = null;
    var paintTo = true;
    var before = null;
    var touching = false;

    function paintRectangle(corner) {
      var top = Math.min(anchor.row, corner.row);
      var bottom = Math.max(anchor.row, corner.row);
      var left = Math.min(anchor.column, corner.column);
      var right = Math.max(anchor.column, corner.column);
      rows.forEach(function (row, r) {
        row.forEach(function (slot, c) {
          var inside = r >= top && r <= bottom && c >= left && c <= right;
          slot.checked = inside ? paintTo : before[r][c];
        });
      });
    }

    grid.addEventListener("pointerdown", function (event) {
      touching = event.pointerType === "touch";
      if (touching || !isSlot(event.target)) {
        return;
      }
      // Take the press ourselves so dragging doesn't select the whole table.
      event.preventDefault();
      anchor = cellAt.get(event.target);
      paintTo = !event.target.checked;
      before = rows.map(function (row) {
        return row.map(function (slot) {
          return slot.checked;
        });
      });
      paintRectangle(anchor);
      event.target.focus();
    });

    grid.addEventListener("pointermove", function (event) {
      if (!anchor) {
        return;
      }
      var under = document.elementFromPoint(event.clientX, event.clientY);
      if (isSlot(under)) {
        paintRectangle(cellAt.get(under));
      }
    });

    grid.addEventListener("click", function (event) {
      // detail is 0 for keyboard-generated clicks, which must still toggle.
      if (isSlot(event.target) && event.detail !== 0 && !touching) {
        event.preventDefault();
      }
    });

    function stop() {
      anchor = null;
      before = null;
    }
    document.addEventListener("pointerup", stop);
    document.addEventListener("pointercancel", stop);

    // Day headings toggle their whole column: on unless it is already full.
    grid
      .querySelectorAll("[data-availability-day]")
      .forEach(function (heading) {
        var column = Number(heading.dataset.availabilityDay);
        heading.classList.add("availability-day-toggle");
        heading.title = "Select or clear this whole day";
        heading.addEventListener("click", function () {
          var slots = rows.map(function (row) {
            return row[column];
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
