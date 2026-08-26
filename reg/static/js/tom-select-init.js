/*
 * Turns the <select>s marked by SearchableSelect into type-to-filter dropdowns.
 *
 * Purely an enhancement: if the CDN is unreachable or the script is blocked,
 * the selects stay ordinary dropdowns and the form still works.
 */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    if (typeof TomSelect === "undefined") {
      return;
    }
    document
      .querySelectorAll("select[data-tom-select]")
      .forEach(function (select) {
        new TomSelect(select, {
          plugins: select.multiple ? ["remove_button"] : [],
          placeholder: select.dataset.placeholder || "",
          // The roster can run to a few hundred names; show every match.
          maxOptions: null,
          allowEmptyOption: false,
        });
      });
  });
})();
