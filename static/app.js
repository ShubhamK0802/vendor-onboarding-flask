// Submit page only: tabs, resubmission prefill, and the live run view (polls the server while the checks run).
const $ = (s) => document.querySelector(s);

if ($('#stages')) {
  const ICON = { pass: '✓', flagged: '!', skipped: '–' };

  document.querySelectorAll('.tab-btn').forEach((btn) => btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('on', b === btn));
    document.querySelectorAll('.tab').forEach((t) => (t.hidden = t.id !== btn.dataset.tab));
  }));

  $('#parent').addEventListener('change', async (e) => {
    $('#parent-note').hidden = !e.target.value;
    if (!e.target.value) return;
    const values = await (await fetch(`/api/prefill/${e.target.value}`)).json();
    for (const [name, value] of Object.entries(values)) $(`#tab-form [name=${name}]`).value = value;
    $('#tab-form [name=bank_account_number]').value = '';
    document.querySelector('[data-tab=tab-form]').click();
  });

  const show = (stages) => {
    $('#stages').innerHTML = stages.map((s) =>
      `<li><span class="dot ${s.status}">${ICON[s.status]}</span><div><b>${s.name}</b> <span class="muted">${s.status}${s.detail ? ' · ' + s.detail : ''}</span></div></li>`).join('');
  };

  async function run(form) {
    const buttons = document.querySelectorAll('form.tab button.primary');
    const data = new FormData(form);
    data.set('mode', form.dataset.mode);
    data.set('parent', $('#parent').value);
    $('#error').hidden = true;
    const reply = await fetch('/api/submit', { method: 'POST', body: data });
    const started = await reply.json();
    if (!reply.ok) { $('#error').textContent = started.error; $('#error').hidden = false; return; }

    buttons.forEach((b) => (b.disabled = true));
    $('#placeholder').hidden = true;
    $('#outcome').innerHTML = '';
    $('#result-title').textContent = 'Checking vendor…';
    for (;;) {
      const progress = await (await fetch(`/api/progress/${started.token}`)).json();
      show(progress.stages);
      if (progress.done) {
        if (progress.error) { $('#outcome').textContent = progress.error; $('#result-title').textContent = 'Live run view'; }
        else {
          $('#outcome').innerHTML = await (await fetch(`/run/${progress.run_id}`)).text();
          $('#result-title').textContent = 'Result';
        }
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    buttons.forEach((b) => (b.disabled = false));
    $('#parent').querySelectorAll('option').forEach((o) => { if (o.value === $('#parent').value && o.value) o.remove(); });
    $('#parent').value = '';
    $('#parent-note').hidden = true;
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
