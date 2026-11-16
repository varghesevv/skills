// Sets the saved theme before the first paint, so the page never flashes the other one.
// A file of its own, not inline code, because the Content-Security-Policy allows scripts from
// this origin only. Storage can be blocked, so a failure leaves the system setting in force.
try {
  var theme = localStorage.getItem('skills.theme')
  if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme
} catch (e) {
  // The system setting stays.
}
