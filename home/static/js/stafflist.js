// Staff list toggle functionality
document.addEventListener("DOMContentLoaded", function () {
  const staffContainers = document.querySelectorAll(
    ".staff-container-hidden, .staff-container-visible"
  );

  staffContainers.forEach(function (container) {
    container.addEventListener("click", function () {
      const left = container.querySelector(".staff-left");
      const icon = left.querySelectorAll("img")[1]; // Second img is the icon
      const nameBox = left.querySelector(
        ".staff-name-hidden, .staff-name-visible"
      );
      const right = container.querySelector(
        ".staff-right-hidden, .staff-right-visible"
      );

      if (
        right.classList.contains("staff-right-visible") ||
        window.getComputedStyle(right).display !== "none"
      ) {
        // Hide biography
        container.className = "staff-container-hidden";
        right.className = "staff-right-hidden";
        icon.src = icon.src.replace("minimize.svg", "maximize.svg");
        nameBox.className = "staff-name-hidden";
      } else {
        // Show biography
        container.className = "staff-container-visible";
        right.className = "staff-right-visible";
        icon.src = icon.src.replace("maximize.svg", "minimize.svg");
        nameBox.className = "staff-name-visible";
      }
    });
  });
});
