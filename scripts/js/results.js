/* ═══════════════════════════════════════════
   results.js — 結果画面・カテゴリ別統計処理
   ═══════════════════════════════════════════ */

function getQuizResult() {
  const raw = sessionStorage.getItem('quizResult');
  if (!raw) return null;
  return JSON.parse(raw);
}

/* ── スコアリング表示 ── */
function renderScoreSummary(result, containerEl) {
  const pct = Math.round((result.score / result.total) * 100);
  const minutes = Math.floor(result.timeTaken / 60);
  const seconds = String(result.timeTaken % 60).padStart(2, '0');

  containerEl.innerHTML = `
    <div class="result-score-circle">
      <div class="score-big">${result.score}<span class="score-slash">/${result.total}</span></div>
      <div class="score-pct">${pct}%</div>
    </div>
    <div class="result-time">所要時間 ${minutes}:${seconds}</div>
  `;
}

/* ── カテゴリ別正答率バー ── */
function renderCategoryBars(result, containerEl) {
  const categories = [
    { key: 'politics', label: '政治', color: '#6688ff', total: 4 },
    { key: 'economy', label: '経済', color: '#66ffcc', total: 3 },
    { key: 'international', label: '国際', color: '#cc66ff', total: 3 },
  ];

  let html = '';
  categories.forEach(cat => {
    const correct = result.categoryScores[cat.key] || 0;
    const pct = cat.total > 0 ? Math.round((correct / cat.total) * 100) : 0;
    html += `
      <div class="cat-bar-row">
        <span class="cat-label" style="color:${cat.color}">${cat.label}</span>
        <div class="cat-bar-track">
          <div class="cat-bar-fill" style="width:${pct}%; background:${cat.color}"></div>
        </div>
        <span class="cat-score">${correct}/${cat.total}</span>
      </div>
    `;
  });

  containerEl.innerHTML = html;

  // アニメーション：少し遅れてバーを伸ばす
  requestAnimationFrame(() => {
    containerEl.querySelectorAll('.cat-bar-fill').forEach(bar => {
      bar.style.transition = 'width 0.8s ease-out';
    });
  });
}

/* ── 全問解説一覧 ── */
function renderAllExplanations(result, containerEl) {
  const categoryLabel = { politics: '政治', economy: '経済', international: '国際' };
  const diffLabel = { easy: '易', medium: '中', hard: '難' };
  const labels = ['A', 'B', 'C', 'D'];

  let html = '';
  result.answers.forEach((a, i) => {
    const q = a.question;
    const isCorrect = a.is_correct;
    const selectedLabel = a.selected_answer === 'TIMEOUT' ? '時間切れ' : a.selected_answer;
    const statusClass = isCorrect ? 'explanation-correct' : 'explanation-wrong';
    const statusIcon = isCorrect ? '✓' : '✗';
    const statusColor = isCorrect ? 'var(--color-correct)' : 'var(--color-wrong)';

    const choices = [q.choice_a, q.choice_b, q.choice_c, q.choice_d];

    html += `
      <div class="explanation-card ${statusClass}">
        <div class="explanation-header">
          <span class="explanation-num">Q${i + 1}</span>
          <span class="badge badge--${q.category}">${categoryLabel[q.category]}</span>
          <span class="badge badge--${q.difficulty}">${diffLabel[q.difficulty]}</span>
          <span class="explanation-status" style="color:${statusColor}">${statusIcon} ${isCorrect ? '正解' : '不正解'}</span>
        </div>
        <div class="explanation-question">${q.question_text}</div>
        <div class="explanation-choices">
          ${labels.map((l, ci) => {
            let cls = 'exp-choice';
            if (l === q.correct_answer) cls += ' exp-choice-correct';
            if (l === a.selected_answer && !isCorrect) cls += ' exp-choice-wrong';
            return `<div class="${cls}"><span class="exp-choice-label">${l}.</span> ${choices[ci]}</div>`;
          }).join('')}
        </div>
        <div class="explanation-answer">
          あなたの回答：<strong>${selectedLabel}</strong>
          正解：<strong style="color:var(--color-correct)">${q.correct_answer}</strong>
        </div>
        ${q.explanation ? `<div class="explanation-body">${q.explanation}</div>` : ''}
        ${q.debate_topic ? `<div class="explanation-debate"><strong>関連論題：</strong>${q.debate_topic}</div>` : ''}
      </div>
    `;
  });

  containerEl.innerHTML = html;
}

/* ── ランクアップ演出 ── */
function showRankUpEffect(newRank) {
  const CHAPTER_NAMES = ['', '第1章 学び舎', '第2章 霞が関', '第3章 権力の回廊', '第4章 国会議事堂', '第5章 総理官邸'];

  // パーティクル
  const particles = document.createElement('div');
  particles.className = 'rankup-particles';
  for (let i = 0; i < 40; i++) {
    const p = document.createElement('div');
    p.className = 'rankup-particle';
    p.style.left = Math.random() * 100 + '%';
    p.style.animationDuration = (2 + Math.random() * 3) + 's';
    p.style.animationDelay = Math.random() * 2 + 's';
    p.style.width = (2 + Math.random() * 4) + 'px';
    p.style.height = p.style.width;
    particles.appendChild(p);
  }
  document.body.appendChild(particles);

  // オーバーレイ
  const overlay = document.createElement('div');
  overlay.className = 'rankup-overlay';
  overlay.innerHTML = `
    <div class="rankup-label">RANK UP!</div>
    <div class="rankup-new-rank">${newRank.name}</div>
    <div class="rankup-chapter">${CHAPTER_NAMES[newRank.chapter] || ''}</div>
    <div class="rankup-scroll-text">
      新たな役職に就任しました。<br>さらなる高みを目指しましょう。
    </div>
    <div class="rankup-continue">画面をクリックして続ける</div>
  `;
  document.body.appendChild(overlay);

  return new Promise(resolve => {
    overlay.addEventListener('click', () => {
      overlay.style.transition = 'opacity 0.5s';
      overlay.style.opacity = '0';
      particles.style.transition = 'opacity 0.5s';
      particles.style.opacity = '0';
      setTimeout(() => {
        overlay.remove();
        particles.remove();
        resolve();
      }, 500);
    });
  });
}

/* ── 成績コメント ── */
function getScoreComment(score, total) {
  const pct = (score / total) * 100;
  if (pct === 100) return '満点！完璧です！';
  if (pct >= 80) return '素晴らしい成績です！';
  if (pct >= 60) return '良い調子です。もう少し頑張りましょう！';
  if (pct >= 40) return 'まずまずですが、ニュースをもっとチェックしましょう。';
  if (pct >= 20) return 'もっとニュースに触れてみましょう。';
  return '今週のニュースを振り返ってみましょう。';
}
