"use strict";
const form = document.querySelector('.fault-filters');
const search = document.querySelector('#fault-search');
const category = document.querySelector('#fault-category');
const difficulty = document.querySelector('#fault-difficulty');
const groups = [...document.querySelectorAll('.fault-group')];
function filterFaults() {
  const query = search.value.trim().toLowerCase();
  let types = 0;
  let categories = 0;
  groups.forEach(group => {
    const eligible = (!category.value || category.value === group.dataset.category) &&
      (!difficulty.value || difficulty.value === group.dataset.difficulty);
    let visible = 0;
    group.querySelectorAll('.fault-item').forEach(item => {
      const match = eligible && `${item.dataset.name} ${group.dataset.category}`.toLowerCase().includes(query);
      item.hidden = !match;
      if (match) visible++;
    });
    group.hidden = visible === 0;
    if (visible) categories++;
    types += visible;
  });
  document.querySelector('#fault-summary').textContent = `${types} fault ${types === 1 ? 'type' : 'types'} across ${categories} ${categories === 1 ? 'category' : 'categories'}`;
  document.querySelector('#fault-empty').hidden = types !== 0;
}
form.hidden = false;
form.addEventListener('submit', event => event.preventDefault());
form.addEventListener('input', filterFaults);
form.addEventListener('change', filterFaults);
form.addEventListener('reset', () => setTimeout(filterFaults, 0));
