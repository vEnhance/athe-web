document.addEventListener("DOMContentLoaded", function () {
  document
    .querySelectorAll('[data-bs-toggle="tooltip"]')
    .forEach(function (el) {
      bootstrap.Tooltip.getOrCreateInstance(el);
    });
});
