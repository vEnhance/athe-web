/*
 * The ranking applet: drag classes into order, or move them with the arrows.
 *
 * Preference order is simply the document order of the hidden inputs, so all
 * this does is move <li> elements around; nothing is serialized. Without the
 * script the list still submits in its rendered order and the "Not for me"
 * boxes still exclude classes, so the form stays usable.
 */
(function () {
  "use strict";

  function setUp(applet) {
    var rankList = applet.querySelector("[data-rank-list]");
    var excludedList = applet.querySelector("[data-excluded-list]");
    var emptyNote = applet.querySelector("[data-excluded-empty]");

    function refresh() {
      if (emptyNote) {
        emptyNote.hidden = excludedList.children.length > 0;
      }
      applet.querySelectorAll("[data-course-item]").forEach(function (item) {
        var excluded = item.parentElement === excludedList;
        item.querySelectorAll("[data-move]").forEach(function (button) {
          button.hidden = excluded;
        });
        item.draggable = !excluded;
      });
    }

    function move(item, offset) {
      var sibling =
        offset < 0 ? item.previousElementSibling : item.nextElementSibling;
      if (!sibling) {
        return;
      }
      if (offset < 0) {
        rankList.insertBefore(item, sibling);
      } else {
        rankList.insertBefore(sibling, item);
      }
    }

    function addControls(item) {
      var controls = document.createElement("span");
      controls.className = "course-preference-controls";
      [
        ["▲", "Move up", -1],
        ["▼", "Move down", 1],
      ].forEach(function (spec) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-sm btn-outline-secondary";
        button.textContent = spec[0];
        button.title = spec[1];
        button.setAttribute("aria-label", spec[1] + ": " + itemName(item));
        button.dataset.move = String(spec[2]);
        button.addEventListener("click", function () {
          move(item, spec[2]);
          button.focus();
          refresh();
        });
        controls.appendChild(button);
      });
      item.insertBefore(controls, item.firstChild);
    }

    function itemName(item) {
      return item.querySelector(".course-preference-name").textContent.trim();
    }

    applet.querySelectorAll("[data-course-item]").forEach(function (item) {
      addControls(item);

      var checkbox = item.querySelector('input[type="checkbox"]');
      checkbox.addEventListener("change", function () {
        (checkbox.checked ? excludedList : rankList).appendChild(item);
        refresh();
        checkbox.focus();
      });

      item.addEventListener("dragstart", function (event) {
        item.classList.add("course-preference-dragging");
        event.dataTransfer.effectAllowed = "move";
        // Firefox ignores drags that carry no data.
        event.dataTransfer.setData("text/plain", "");
      });
      item.addEventListener("dragend", function () {
        item.classList.remove("course-preference-dragging");
        refresh();
      });
    });

    rankList.addEventListener("dragover", function (event) {
      var dragging = applet.querySelector(".course-preference-dragging");
      if (!dragging) {
        return;
      }
      event.preventDefault();
      var next = Array.prototype.find.call(
        rankList.children,
        function (sibling) {
          var box = sibling.getBoundingClientRect();
          return event.clientY < box.top + box.height / 2;
        },
      );
      rankList.insertBefore(dragging, next || null);
    });

    refresh();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-course-preferences]").forEach(setUp);
  });
})();
