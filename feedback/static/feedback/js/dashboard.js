// Dashboard charts. Data comes from the JSON API (feedback/views.py,
// api_dataset_summary); the same numbers are also in the page's tables, so the
// page still works if Chart.js or the API is unavailable.
(function () {
  if (typeof Chart === 'undefined' || !window.UNDONE_SUMMARY_URL) return;

  fetch(window.UNDONE_SUMMARY_URL, { credentials: 'same-origin' })
    .then(function (res) {
      if (!res.ok) throw new Error('Summary API returned ' + res.status);
      return res.json();
    })
    .then(function (data) {
      var themeCanvas = document.getElementById('themeChart');
      if (themeCanvas && data.themes.length) {
        new Chart(themeCanvas, {
          type: 'bar',
          data: {
            labels: data.themes.map(function (t) { return t.name; }),
            datasets: [{ label: '% of responses', data: data.themes.map(function (t) { return t.percent; }), backgroundColor: '#2f5bd3' }]
          },
          options: { indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, max: 100, ticks: { callback: function (v) { return v + '%'; } } } } }
        });
      }
      var monthCanvas = document.getElementById('monthChart');
      if (monthCanvas && data.months.length) {
        new Chart(monthCanvas, {
          type: 'line',
          data: {
            labels: data.months.map(function (m) { return m.month; }),
            datasets: [{ label: 'Cancellations', data: data.months.map(function (m) { return m.count; }), borderColor: '#2f5bd3', tension: 0.2 }]
          },
          options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
        });
      }
    })
    .catch(function (err) { console.warn('Undone dashboard charts unavailable:', err); });
})();
