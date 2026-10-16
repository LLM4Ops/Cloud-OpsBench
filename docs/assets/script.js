"use strict";

// Progressive enhancement: both complete result tables remain available without JS.
document.querySelectorAll("table[data-results]").forEach((table) => {
  const rows = [...table.tBodies[0].rows];
  for (let metric = 0; metric < 9; metric += 1) {
    const values = rows.map((row) => Number(row.cells[metric + 1].textContent));
    const best = metric >= 7 ? Math.min(...values) : Math.max(...values);
    rows.forEach((row, index) => {
      if (values[index] === best) {
        const cell = row.cells[metric + 1];
        cell.classList.add("best");
        const strong = document.createElement("strong");
        strong.textContent = cell.textContent;
        cell.replaceChildren(strong);
      }
    });
  }
});

const buttons = [...document.querySelectorAll("[data-system]")];
const panels = [...document.querySelectorAll("[data-panel]")];
function selectSystem(system) {
  buttons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.system === system)));
  panels.forEach((panel) => { panel.hidden = panel.dataset.panel !== system; });
}
if (buttons.length && panels.length) {
  selectSystem("boutique");
  document.documentElement.classList.add("js-ready");
  buttons.forEach((button) => button.addEventListener("click", () => selectSystem(button.dataset.system)));
}

if (window.isSecureContext && navigator.clipboard?.writeText) {
  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.hidden = false;
    button.addEventListener("click", async () => {
      const original = button.textContent;
      const feedback = document.querySelector(".copy-feedback");
      try {
        await navigator.clipboard.writeText(document.getElementById(button.dataset.copy).textContent);
        button.textContent = "Copied!";
        if (feedback) feedback.textContent = "Copied to clipboard.";
      } catch {
        button.textContent = "Select & copy below";
        if (feedback) feedback.textContent = "Clipboard permission unavailable. Select and copy the text manually.";
      }
      window.setTimeout(() => { button.textContent = original; }, 2500);
    });
  });
}
