// js/config.js のテンプレート
// このファイルをコピーして js/config.js を作成し、実際の値を入力してください。
const SUPABASE_URL = 'YOUR_SUPABASE_URL';
const SUPABASE_KEY = 'YOUR_SUPABASE_ANON_KEY';
const GH_PAT = 'YOUR_GITHUB_PAT';

const _supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
