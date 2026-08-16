// 小小推理家 · 答题交互
const $ = (id) => document.getElementById(id);

let childId = null;
let childName = null;
let currentQ = null;
let currentLevel = null;
let selectedLevel = null;
let bankMode = 'builtin';
let externalSource = null;
let externalSources = [];
let externalLang = 'zh';
let hintStep = 0;
let answered = false;
let earnedStars = 0;
let qStartedAt = 0;

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
  $('bankpick').classList.remove('hidden');
  $('quiz').classList.add('hidden');
  $('pick').classList.add('hidden');
  loadExternalSources();
}

// ---------- 题库选择（内置 / 外部） ----------
async function loadExternalSources() {
  const res = await fetch('/api/external/sources');
  const data = await res.json();
  externalSources = data.sources || [];
}

function pickBank(mode) {
  bankMode = mode;
  $('langToggle').classList.add('hidden');
  const list = $('sourceList');
  list.classList.add('hidden');
  list.innerHTML = '';
  if (mode === 'mixed') {
    externalSource = null;
    showLevels();
    return;
  }
  if (mode === 'builtin') {
    externalSource = null;
    externalLang = 'zh';
    showLevels();
    return;
  }
  // 外部题库：先选语言（中文版 / 原文），再按来源选择
  externalLang = 'zh';
  pickLang('zh');
  $('langToggle').classList.remove('hidden');
  // 外部题库：按来源选择
  if (!externalSources.length) {
    alert('外部题库还是空的，请先用 CLI 导入：python cli.py import bigbench');
    return;
  }
  renderSourceList();
}

function renderSourceList() {
  const list = $('sourceList');
  list.innerHTML = '';
  externalSources.forEach(s => {
    const b = document.createElement('button');
    b.className = 'level-card';
    b.innerHTML = `<span class="lv-emoji">🌐</span>
      <span class="lv-name">${s.name}</span>
      <span class="lv-tag">${s.total} 题 · ${s.license}</span>`;
    b.onclick = () => {
      externalSource = s.slug;
      showLevels();
    };
    list.appendChild(b);
  });
  list.classList.remove('hidden');
}

function pickLang(lang) {
  externalLang = lang;
  $('langZhBtn').classList.toggle('active', lang === 'zh');
  $('langEnBtn').classList.toggle('active', lang === 'en');
}

function showLevels() {
  $('bankpick').classList.add('hidden');
  $('pick').classList.remove('hidden');
  loadLevels();
}

// ---------- 难度选择 ----------
async function loadLevels() {
  const res = await fetch('/api/levels');
  const data = await res.json();
  const list = $('levelList');
  list.innerHTML = '';
  selectedLevel = null;
  $('startBtn').classList.add('hidden');
  data.levels.forEach(lv => {
    const b = document.createElement('button');
    b.className = 'level-card';
    b.dataset.level = lv.level;
    b.innerHTML = `<span class="lv-emoji">${lv.emoji}</span>
      <span class="lv-name">${lv.name}</span>
      <span class="lv-tag">${lv.tagline}</span>`;
    b.onclick = () => pickLevel(lv.level, b);
    list.appendChild(b);
  });
}

function pickLevel(level, btn) {
  selectedLevel = level;
  [...document.querySelectorAll('.level-card')].forEach(b =>
    b.classList.toggle('selected', b === btn));
  $('startBtn').classList.remove('hidden');
}

function startChallenge() {
  if (!selectedLevel) return;
  currentLevel = selectedLevel;
  $('pick').classList.add('hidden');
  $('quiz').classList.remove('hidden');
  nextQuestion();
}

// ---------- 出题 ----------
async function nextQuestion() {
  answered = false;
  hintStep = 0;
  currentQ = null;
  $('hints').innerHTML = '';
  $('feedback').classList.add('hidden');
  $('nextBtn').classList.add('hidden');
  $('hintBtn').disabled = false;

  const res = await fetch('/api/next', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      child_id: childId,
      level: currentLevel,
      bank: bankMode,
      source: bankMode === 'external' ? externalSource : undefined,
      lang: bankMode === 'external' ? externalLang : 'zh',
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.error || '题库空了，请先用 CLI 生成题目。');
    return;
  }
  currentQ = await res.json();
  renderQuestion(currentQ);
}

function renderQuestion(q) {
  qStartedAt = Date.now();
  if (bankMode === 'mixed') {
    $('qBank').textContent = '🧠 综合 · ' + (q.bank === 'external' ? '外部' : '内置');
  } else {
    $('qBank').textContent = q.bank === 'external'
      ? '🌐 外部 · ' + (q.source_name || '')
      : '🧩 内置';
  }
  $('qType').textContent = q.type_name;
  $('qLevel').textContent = q.level_label;
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
  const timeMs = Date.now() - qStartedAt;
  const res = await fetch('/api/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // 身份由服务端 session 绑定，无需（也不应）在请求里带 child_id
    body: JSON.stringify({ question_id: currentQ.id, choice, time_ms: timeMs }),
  });
  const r = await res.json();
  if (!res.ok) { alert(r.error || '提交失败'); answered = false; return; }

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

function changeLevel() {
  $('quiz').classList.add('hidden');
  $('pick').classList.remove('hidden');
  loadLevels();
}

function changeBank() {
  $('quiz').classList.add('hidden');
  $('pick').classList.add('hidden');
  $('bankpick').classList.remove('hidden');
  loadExternalSources();
}

// ---------- 启动 ----------
$('createBtn').onclick = createChild;
$('newName').addEventListener('keydown', e => { if (e.key === 'Enter') createChild(); });
$('startBtn').onclick = startChallenge;
$('hintBtn').onclick = showHint;
$('changeLevelBtn').onclick = changeLevel;
$('changeBankBtn').onclick = changeBank;
$('nextBtn').onclick = nextQuestion;
loadChildren();
