const RANKS = [
  { id: 1,  name: '学生',                    chapter: 1, min: 0 },
  { id: 2,  name: '財務省入省',              chapter: 1, min: 50 },
  { id: 3,  name: '省庁研修・事務官',        chapter: 2, min: 120 },
  { id: 4,  name: '財務省主計局係員・主査',  chapter: 2, min: 210 },
  { id: 5,  name: '課長補佐',                chapter: 2, min: 320 },
  { id: 6,  name: '主計局総務課長',          chapter: 3, min: 450 },
  { id: 7,  name: '審議官・主計局長',        chapter: 3, min: 600 },
  { id: 8,  name: '財務省事務次官',          chapter: 3, min: 770 },
  { id: 9,  name: '衆議院議員',              chapter: 4, min: 960 },
  { id: 10, name: '衆院財務金融委員会委員長', chapter: 4, min: 1170 },
  { id: 11, name: '財務大臣',                chapter: 4, min: 1400 },
  { id: 12, name: '内閣官房長官',            chapter: 5, min: 1650 },
  { id: 13, name: '未来党幹事長',            chapter: 5, min: 1920 },
  { id: 14, name: '内閣総理大臣',            chapter: 5, min: 2200 },
];

function getRankById(id) {
  return RANKS.find(r => r.id === id) || RANKS[0];
}

function getRankByScore(score) {
  for (let i = RANKS.length - 1; i >= 0; i--) {
    if (score >= RANKS[i].min) return RANKS[i];
  }
  return RANKS[0];
}

async function signInWithGoogle() {
  const { error } = await _supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.origin + '/news-yonderu2/home.html' }
  });
  if (error) alert('ログインに失敗しました: ' + error.message);
}

async function signOut() {
  await _supabase.auth.signOut();
  window.location.href = 'index.html';
}

async function getCurrentUser() {
  const { data: { user } } = await _supabase.auth.getUser();
  if (!user) return null;

  const { data: profile } = await _supabase
    .from('users')
    .select('*')
    .eq('id', user.id)
    .single();

  return profile;
}

async function requireAuth() {
  const user = await getCurrentUser();
  if (!user) {
    window.location.href = 'index.html';
    return null;
  }
  if (user.is_banned) {
    await signOut();
    alert('このアカウントは停止されています。');
    return null;
  }
  return user;
}

async function requireAdmin() {
  const user = await requireAuth();
  if (!user) return null;
  if (user.role !== 'admin') {
    window.location.href = '../home.html';
    return null;
  }
  return user;
}

async function registerGuestName(name) {
  const { data: { user } } = await _supabase.auth.getUser();
  if (!user) return { error: 'Not authenticated' };

  const { data: existing } = await _supabase
    .from('users')
    .select('id')
    .eq('guest_name', name)
    .single();

  if (existing) return { error: 'この名前はすでに使用されています' };

  const { error } = await _supabase.from('users').upsert({
    id: user.id,
    guest_name: name,
  });

  return { error: error ? error.message : null };
}

async function checkGuestNameAvailable(name) {
  if (!name || name.trim().length === 0) return false;
  const { data } = await _supabase
    .from('users')
    .select('id')
    .eq('guest_name', name.trim())
    .maybeSingle();
  return !data;
}
