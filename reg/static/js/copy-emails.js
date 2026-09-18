document.addEventListener("DOMContentLoaded", function () {
  const button = document.querySelector("[data-emails]");
  if (!button) {
    return;
  }
  const label = button.textContent;
  button.addEventListener("click", async function () {
    try {
      await navigator.clipboard.writeText(button.dataset.emails);
      button.textContent = "Copied!";
    } catch {
      // Clipboard access is refused outside a secure context, and over plain
      // HTTP the development server is exactly that.
      button.textContent = "Copying failed; select the list below instead.";
      document.querySelector("[data-testid='email-list']").hidden = false;
    }
    setTimeout(function () {
      button.textContent = label;
    }, 3000);
  });
});
