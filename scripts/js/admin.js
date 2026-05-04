/* ═══════════════════════════════════════════
   admin.js — 管理者機能全般
   ═══════════════════════════════════════════ */

/* ── ダッシュボード統計 ── */
async function loadDashboardStats() {
  const [
    { count: userCount },
    { count: quizCount },
    { data: latestQuiz },
  ] = await Promise.all([
    _supabase.from('users').select('*', { count: 'exact', head: true }),
    _supabase.from('quiz_sets').select('*', { count: 'exact', head: true }),
    _supabase.from('quiz_sets').select('id, week_id, is_published, created_at')
      .order('created_at', { ascending: false }).limit(1).maybeSingle(),
  ]);

  return { userCount: userCount || 0, quizCount: quizCount || 0, latestQuiz: latestQuiz?.data || latestQuiz };
}

/* ── クイズセット一覧 ── */
async function loadQuizSets() {
  const { data } = await _supabase
    .from('quiz_sets')
    .select('*')
    .order('created_at', { ascending: false });
  return data || [];
}

/* ── クイズ公開切替 ── */
async function togglePublish(quizId, publish) {
  const { error } = await _supabase
    .from('quiz_sets')
    .update({ is_published: publish })
    .eq('id', quizId);
  return !error;
}

/* ── 問題取得 ── */
async function loadQuestions(quizId) {
  const { data } = await _supabase
    .from('questions')
    .select('*')
    .eq('quiz_id', quizId)
    .order('order_num', { ascending: true });
  return data || [];
}

/* ── 問題更新 ── */
async function updateQuestion(questionId, updates) {
  const { error } = await _supabase
    .from('questions')
    .update(updates)
    .eq('id', questionId);
  return !error;
}

/* ── ユーザー一覧 ── */
async function loadAllUsers() {
  const { data } = await _supabase
    .from('users')
    .select('*')
    .order('created_at', { ascending: false });
  return data || [];
}

/* ── ユーザーBAN切替 ── */
async function toggleBan(userId, ban) {
  const { error } = await _supabase
    .from('users')
    .update({ is_banned: ban })
    .eq('id', userId);
  return !error;
}

/* ── ユーザー削除 ── */
async function deleteUser(userId) {
  const { error } = await _supabase
    .from('users')
    .delete()
    .eq('id', userId);
  return !error;
}

/* ── ランク変更 ── */
async function changeUserRank(userId, newRankId) {
  const rank = getRankById(newRankId);
  if (!rank) return false;
  const { error } = await _supabase
    .from('users')
    .update({ rank_id: newRankId })
    .eq('id', userId);
  return !error;
}

/* ── クイズセット削除 ── */
async function deleteQuizSet(quizId) {
  const { error } = await _supabase
    .from('quiz_sets')
    .delete()
    .eq('id', quizId);
  return !error;
}
