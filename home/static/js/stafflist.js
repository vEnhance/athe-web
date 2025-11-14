$(".staff-container-hidden").click(function () {
  var parent = event.target;
  while (
    !parent.classList.contains("staff-container-hidden") &&
    !parent.classList.contains("staff-container-visible")
  ) {
    parent = $(parent).parent().get(0);
  }
  var left = $(parent).children()[0];
  var image = $(left).children()[1];
  left = $(left).children()[2];
  var right = $(parent).children()[1];
  if ($(right).is(":visible")) {
    parent.classList = new Array("staff-container-hidden");
    right.classList = new Array("staff-right-hidden");
    $(image).attr("src", "../athe_icons/maximize.svg");
    left.classList = new Array("staff-name-hidden");
  } else {
    parent.classList = new Array("staff-container-visible");
    right.classList = new Array("staff-right-visible");
    $(image).attr("src", "../athe_icons/minimize.svg");
    left.classList = new Array("staff-name-visible");
  }
});
