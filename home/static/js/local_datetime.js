/**
 * local_datetime.js
 *
 * For any <time class="local-datetime" datetime="..."> elements rendered by
 * the local_datetime template filter, this script:
 *   - Shows a Bootstrap tooltip with the user's local time on hover
 *   - Toggles between server time and local time on click
 */
document.addEventListener("DOMContentLoaded", function () {
  const elements = document.querySelectorAll("time.local-datetime");

  elements.forEach(function (el) {
    const isoString = el.getAttribute("datetime");
    if (!isoString) return;

    const serverText = el.textContent.trim();

    const dt = new Date(isoString);
    const localText = dt.toLocaleString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });

    // Visual hint that the element is interactive
    el.style.cursor = "pointer";
    el.style.textDecoration = "underline dotted";
    el.style.textUnderlineOffset = "3px";

    // Set up Bootstrap tooltip showing local time
    el.setAttribute("data-bs-toggle", "tooltip");
    el.setAttribute("data-bs-placement", "top");
    el.setAttribute("data-bs-title", "Your time: " + localText);

    let tooltip = new bootstrap.Tooltip(el);
    let showingLocal = false;

    el.addEventListener("click", function () {
      tooltip.hide();
      tooltip.dispose();

      if (showingLocal) {
        el.textContent = serverText;
        el.setAttribute("data-bs-title", "Your time: " + localText);
      } else {
        el.textContent = localText;
        el.setAttribute("data-bs-title", "Server time: " + serverText);
      }
      showingLocal = !showingLocal;

      tooltip = new bootstrap.Tooltip(el);
    });
  });
});
