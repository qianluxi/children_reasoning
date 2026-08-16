// 能力画像页
const $ = (id) => document.getElementById(id);
let kids = [];

async function loadChildren() {
  const res = await fetch('/api/children');
  kids = await res.json();
  const sel = $('childSel');
  sel.innerHTML = '';
  kids.forEach(k => {
    const opt = document.createElement('option');
    opt.value = k.id;
    opt.textContent = k.name;
    sel.appendChild(opt);
  });
  if (kids.length) loadProfile(kids[0].id);
  sel.onchange = () => loadProfile(sel.value);
}

async function loadProfile(childId) {
  const res = await fetch(`/api/profile/${childId}`);
  const p = await res.json();

  $('summary').innerHTML = `
    <div class="stat"><div class="num">${p.total_attempts}</div><div class="lbl">答题总数</div></div>
    <div class="stat"><div class="num">${p.stars} ⭐</div><div class="lbl">答对星星</div></div>
  `;

  const skills = $('skills');
  skills.innerHTML = '';
  p.skills.forEach(s => {
    const div = document.createElement('div');
    div.className = 'skill';
    const pct = s.mastery === null ? 0 : s.mastery;
    const label = s.mastery === null ? '还没练过' : s.mastery + '%';
    div.innerHTML = `
      <div class="skill-top"><span>${s.type_name}</span><span>${label}</span></div>
      <div class="bar"><div class="fill" style="width:${pct}%"></div></div>
      <div class="meta">最近练习 ${s.attempts} 题</div>
    `;
    skills.appendChild(div);
  });
}

loadChildren();
