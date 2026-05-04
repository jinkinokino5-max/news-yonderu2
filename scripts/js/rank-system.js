/* ランクシステム（auth.js の RANKS 定数を共有して使う） */

function calcRankScore(participations, avgCorrectRate) {
  return participations * avgCorrectRate;
}

function getRankForScore(score) {
  for (let i = RANKS.length - 1; i >= 0; i--) {
    if (score >= RANKS[i].min) return RANKS[i];
  }
  return RANKS[0];
}

function getNextRank(currentRankId) {
  const next = RANKS.find(r => r.id === currentRankId + 1);
  return next || null;
}

function getProgressToNextRank(score, currentRank) {
  const next = getNextRank(currentRank.id);
  if (!next) return 100;
  const range = next.min - currentRank.min;
  const gained = score - currentRank.min;
  return Math.min(100, Math.max(0, (gained / range) * 100));
}

async function updateUserRank(userId, newTotalScore, newParticipations) {
  const avgRate = newTotalScore / (newParticipations * 10) * 100;
  const rankScore = calcRankScore(newParticipations, avgRate);
  const newRank = getRankForScore(rankScore);

  const { data: current } = await _supabase
    .from('users')
    .select('rank_id, rank_score')
    .eq('id', userId)
    .single();

  const didRankUp = current && newRank.id > current.rank_id;

  await _supabase.from('users').update({
    rank_id: newRank.id,
    rank_score: rankScore,
    total_participations: newParticipations,
  }).eq('id', userId);

  return { newRank, didRankUp, rankScore };
}
