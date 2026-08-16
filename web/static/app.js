// 小小推理家 · 答题交互
const $ = (id) => document.getElementById(id);

let childId = null;
let childName = null;
let currentQ = null;
let hintStep = 0;
let answered = false;
let earnedStars = 0;

// ---------- 儿童选择 ----------
async function loadChildren() {
  const res = await fetch('/api/children');
  const kids = await res.json();
  const list = $('childList');
  list.innerHTML = '';
  kids.forEach(k => {
    const b = document.createElement('button');
    b.className = 'child-pill';
    b.textContent = '🧒 ' + k.name;
    b.onclick = () => startAs(k.id, k.name);
    list.appendChild(b);
  });
}

async function createChild() {
  const name = $('newName').value.trim();
  if (!name) { $('newName').focus(); return; }
  const res = await fetch('/api/children', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  const data = await res.json();
  if (data.error) { alert(data.error); return; }
  startAs(data.id, data.name);
}

function startAs(id, name) {
  childId = id;
  childName = name;
  $('who').textContent = '🧒 ' + name;
  $('login').classList.add('hidden');
  $('quiz').classList.remove('hidden');
  nextQuestion();
}

// ---------- 出题 ----------
async function nextQuestion() {
  answered = false;
  hintStep = 0;
  $('hints').innerHTML = '';
  $('feedback').classList.add('hidden');
  $('nextBtn').classList.add('hidden');
  $('hintBtn').disabled = false;

  const res = await fetch('/api/next', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ child_id: childId }),
  });
  if (!res.ok) { alert('题库空了，请先用 CLI 生成题目。'); return; }
  currentQ = await res.json();
  renderQuestion(currentQ);
}

function renderQuestion(q) {
  $('qType').textContent = q.type_name;
  $('qDiff').textContent = '难度 ' + q.stars;
  $('qTitle').textContent = q.story.title;
  $('qStory').textContent = q.story.text;

  const st = $('statements');
  st.innerHTML = '';
  q.statements.forEach(s => {
    const div = document.createElement('div');
    div.className = 'bubble';
    div.innerHTML = `<span class="speaker">${s.speaker}：</span>${s.text}`;
    st.appendChild(div);
  });

  const cs = $('constraints');
  cs.innerHTML = '';
  q.constraints.forEach(c => {
    const div = document.createElement('div');
    div.className = 'rule';
    div.textContent = '⭐ ' + c;
    cs.appendChild(div);
  });

  $('qPrompt').textContent = q.question_prompt;

  const opts = $('options');
  opts.innerHTML = '';
  q.options.forEach((text, i) => {
    const b = document.createElement('button');
    b.className = 'option';
    b.textContent = text;
    b.onclick = () => submitAnswer(i, b);
    opts.appendChild(b);
  });
}

// ---------- 判题 ----------
async function submitAnswer(choice, btn) {
  if (answered) return;
  answered = true;
  const res = await fetch('/api/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // 身份由服务端 session 绑定，无需（也不应）在请求里带 child_id
    body: JSON.stringify({ question_id: currentQ.id, choice }),
  });
  const r = await res.json();

  // 标记选项
  const buttons = [...document.querySelectorAll('.option')];
  buttons.forEach((b, i) => {
    b.disabled = true;
    if (i === r.correct_index) b.classList.add('correct');
    else if (i === choice) b.classList.add('wrong');
  });

  const fb = $('feedback');
  fb.classList.remove('hidden');
  if (r.correct) {
    earnedStars++;
    $('qStars').textContent = '⭐'.repeat(Math.min(earnedStars, 10));
    fb.className = 'feedback good';
    fb.textContent = '🎉 答对啦！你真棒！\n\n' + r.explanation;
  } else {
    fb.className = 'feedback bad';
    fb.textContent = '💪 再想想～正确答案是：' + r.correct_text + '\n\n' + r.explanation;
  }
  $('nextBtn').classList.remove('hidden');
}

// ---------- 提示 ----------
async function showHint() {
  if (!currentQ || answered) return;
  if (hintStep >= currentQ.hint_count) { $('hintBtn').disabled = true; return; }
  const res = await fetch(`/api/hint/${currentQ.id}?step=${hintStep}`);
  const data = await res.json();
  if (data.hint) {
    const div = document.createElement('div');
    div.className = 'hint';
    div.textContent = '💡 ' + data.hint;
    $('hints').appendChild(div);
    hintStep++;
    if (!data.has_more) $('hintBtn').disabled = true;
  }
}

// ---------- 启动 ----------
$('createBtn').onclick = createChild;
$('newName').addEventListener('keydown', e => { if (e.key === 'Enter') createChild(); });
$('hintBtn').onclick = showHint;
$('nextBtn').onclick = nextQuestion;
loadChildren();
