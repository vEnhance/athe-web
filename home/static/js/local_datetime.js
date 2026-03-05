/**
 * local_datetime.js
 *
 * For any <span class="local-datetime" data-utc="..."> elements rendered by
 * the local_datetime template filter, this script:
 *   - Shows a Bootstrap tooltip with the user's local time on hover
 *   - Toggles between server time and local time on click
 */
document.addEventListener("DOMContentLoaded", function () {
  const spans = document.querySelectorAll(".local-datetime");

  spans.forEach(function (span) {
    const utcString = span.getAttribute("data-utc");
    if (!utcString) return;

    const serverText = span.textContent.trim();

    const dt = new Date(utcString);
    const localText = dt.toLocaleString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });

    // Visual hint that the element is interactive
    span.style.cursor = "pointer";
    span.style.textDecoration = "underline dotted";
    span.style.textUnderlineOffset = "3px";

    // Set up Bootstrap tooltip showing local time
    span.setAttribute("data-bs-toggle", "tooltip");
    span.setAttribute("data-bs-placement", "top");
    span.setAttribute("data-bs-title", "Your time: " + localText);

    let tooltip = new bootstrap.Tooltip(span);
    let showingLocal = false;

    span.addEventListener("click", function () {
      tooltip.hide();
      tooltip.dispose();

      if (showingLocal) {
        span.textContent = serverText;
        span.setAttribute("data-bs-title", "Your time: " + localText);
      } else {
        span.textContent = localText;
        span.setAttribute("data-bs-title", "Server time: " + serverText);
      }
      showingLocal = !showingLocal;

      tooltip = new bootstrap.Tooltip(span);
    });
  });
});
