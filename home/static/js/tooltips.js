/**
 * Every <time datetime="..."> gets a tooltip with the viewer's local time.
 * Those rendered by the local_datetime filter also toggle between server
 * and local time on click.
 */
function localTimeText(isoString) {
  return new Date(isoString).toLocaleString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function setUpLocalDatetimeToggle(el, localText) {
  const serverText = el.textContent.trim();
  let showingLocal = false;

  el.style.cursor = "pointer";
  el.style.textDecoration = "underline dotted";
  el.style.textUnderlineOffset = "3px";

  el.addEventListener("click", function () {
    showingLocal = !showingLocal;
    el.textContent = showingLocal ? localText : serverText;
    const tooltip = bootstrap.Tooltip.getInstance(el);
    tooltip.hide();
    tooltip.setContent({
      ".tooltip-inner": showingLocal
        ? "Server time: " + serverText
        : "Your time: " + localText,
    });
  });
}

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("time[datetime]").forEach(function (el) {
    const localText = localTimeText(el.getAttribute("datetime"));
    el.setAttribute("data-bs-toggle", "tooltip");
    el.setAttribute("data-bs-title", "Your time: " + localText);
    if (el.classList.contains("local-datetime")) {
      setUpLocalDatetimeToggle(el, localText);
    }
  });

  document
    .querySelectorAll('[data-bs-toggle="tooltip"]')
    .forEach(function (el) {
      bootstrap.Tooltip.getOrCreateInstance(el);
    });
});
