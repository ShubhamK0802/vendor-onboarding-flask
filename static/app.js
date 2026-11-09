// Submit page only: tabs and the live verification progress (polls the server while the checks run).
const $ = (s) => document.querySelector(s);

if ($('#stages')) {
  const ICON = { pass: '✓', flagged: '!', skipped: '–' };

  document.querySelectorAll('.tab-btn').forEach((btn) => btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('on', b === btn));
    document.querySelectorAll('.tab').forEach((t) => (t.hidden = t.id !== btn.dataset.tab));
  }));

  const show = (stages) => {
    $('#stages').innerHTML = stages.map((s) =>
      `<li><span class="dot ${s.status}">${ICON[s.status]}</span><div><b>${s.name}</b> <span class="muted">${s.status}${s.detail ? ' · ' + s.detail : ''}</span></div></li>`).join('');
  };

  async function run(form) {
    const buttons = document.querySelectorAll('form.tab button.primary');
    const data = new FormData(form);
    data.set('mode', form.dataset.mode);
    const picked = form.querySelector('input[type=file]');
    if (picked && picked.files.length) data.set('mode', 'json');  // a file chosen on this tab is the one to process, not the selected sample
    $('#error').hidden = true;
    buttons.forEach((b) => (b.disabled = true));
    $('#placeholder').hidden = true;
    $('#outcome').innerHTML = '';
    $('#stages').innerHTML = '<li><span class="dot skipped">…</span><div><b>Submitting application</b> <span class="muted">please wait; the first demo request can take a few seconds</span></div></li>';
    $('#result-title').textContent = 'Starting verification…';

    try {
      const reply = await fetch('/api/submit', { method: 'POST', body: data });
      const started = await reply.json();
      if (!reply.ok) throw new Error(started.error || 'The application could not be submitted');

      $('#result-title').textContent = 'Verifying vendor…';
      let progress = started.progress || null;
      if (progress && progress.stages.length) {  // the whole run came back in one response (serverless host): replay the stages one by one
        for (let i = 1; i <= progress.stages.length; i++) { show(progress.stages.slice(0, i)); await new Promise((resolve) => setTimeout(resolve, 180)); }
      }
      for (;;) {
        if (!progress) progress = await (await fetch(`/api/progress/${started.token}`)).json();
        show(progress.stages);
        if (progress.done) {
          if (progress.error) { $('#outcome').textContent = progress.error; $('#result-title').textContent = 'Verification progress'; }
          else {
            $('#outcome').innerHTML = started.result_html || await (await fetch(`/run/${progress.run_id}`)).text();
            $('#result-title').textContent = 'Result';
          }
          break;
        }
        progress = null;
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
    } catch (error) {
      $('#stages').innerHTML = '';
      $('#result-title').textContent = 'Verification progress';
      $('#error').textContent = error.message || 'The application could not be submitted. Please try again.';
      $('#error').hidden = false;
    } finally {
      buttons.forEach((b) => (b.disabled = false));
    }
  }

  document.querySelectorAll('form.tab').forEach((form) => form.addEventListener('submit', (e) => { e.preventDefault(); run(form); }));
}

// Reviewer desk: remember the reviewer's name, and put it into whichever button they press (claim, release or decide).
const nameBox = $('#reviewer-name');
if (nameBox) {
  try { nameBox.value = localStorage.getItem('reviewer') || ''; } catch (e) { /* storage blocked: fine */ }
  document.querySelectorAll('form.needs-name').forEach((form) => form.addEventListener('submit', () => {
    form.querySelector('[name=reviewer]').value = nameBox.value.trim();
    try { localStorage.setItem('reviewer', nameBox.value.trim()); } catch (e) { /* ignore */ }
  }));
}

// Reviewer desk: clicking anywhere on a queue row opens that submission.
document.querySelectorAll('tr[data-href]').forEach((row) => row.addEventListener('click', (e) => {
  if (!e.target.closest('a, button')) location.href = row.dataset.href;
}));
