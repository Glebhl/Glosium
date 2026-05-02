export function initLessonSetupTabs() {
  const bottomShell = document.querySelector(".bottom-shell");
  const tabElements = Array.from(document.querySelectorAll("[data-setup-tab]"));
  const panelElements = Array.from(document.querySelectorAll("[data-setup-panel]"));
  let activePanel = "cards";

  function showPanel(panelName) {
    activePanel = panelName;

    tabElements.forEach(function (tabElement) {
      tabElement.classList.toggle("is-active", tabElement.dataset.setupTab === panelName);
    });

    panelElements.forEach(function (panelElement) {
      panelElement.classList.toggle("is-active", panelElement.dataset.setupPanel === panelName);
    });
  }

  tabElements.forEach(function (tabElement) {
    tabElement.addEventListener("click", function () {
      showPanel(tabElement.dataset.setupTab);
    });
  });

  showPanel(activePanel);
}
