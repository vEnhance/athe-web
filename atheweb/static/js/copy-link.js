document.addEventListener("DOMContentLoaded", function () {
  const button = document.querySelector("[data-copy-link]");
  if (!button) {
    return;
  }
  const input = button.parentElement.querySelector("input");
  button.addEventListener("click", async function () {
    try {
      await navigator.clipboard.writeText(input.value);
      button.textContent = "Copied!";
    } catch {
      // Clipboard access is refused outside a secure context, such as the
      // development server over plain HTTP.
      input.select();
      button.textContent = "Press Ctrl+C";
    }
    setTimeout(function () {
      button.textContent = "Copy";
    }, 3000);
  });
});
