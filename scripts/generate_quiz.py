"""
generate_quiz.py — Gemini 2.5 Pro APIでクイズ自動生成
NHK NEWS RSS + Google News RSSから時事ニュースを収集し、
10問の4択クイズを生成してSupabaseに保存する。

依存: google-generativeai supabase feedparser pydantic
"""

import os
import re
import json
import datetime
from collections import Counter
from typing import List, Literal

import feedparser
import google.generativeai as genai
from pydantic import BaseModel, field_validator
from supabase import create_client, Client

# ═══════════════════════════════════════════
# 環境変数
# ═══════════════════════════════════════════
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# ═══════════════════════════════════════════
# Pydanticスキーマ
# ═══════════════════════════════════════════
class Choice(BaseModel):
    label: Literal["A", "B", "C", "D"]
    text: str

    @field_validator("text")
    @classmethod
    def check_length(cls, v: str) -> str:
        if len(v) < 30 or len(v) > 50:
            raise ValueError(f"選択肢は30〜50字（現在{len(v)}字）: {v[:20]}...")
        return v


class QuizQuestion(BaseModel):
    order_num: int
    question_text: str
    pattern: Literal["A", "B"]
    difficulty: Literal["easy", "medium", "hard"]
    category: Literal["politics", "economy", "international"]
    choices: List[Choice]
    correct_answer: Literal["A", "B", "C", "D"]
    explanation: str
    debate_topic: str
    news_source: str


class QuizSet(BaseModel):
    week_id: str
    week_start: str
    week_end: str
    questions: List[QuizQuestion]

    @field_validator("questions")
    @classmethod
    def check_questions(cls, v: List[QuizQuestion]) -> List[QuizQuestion]:
        if len(v) != 10:
            raise ValueError(f"問題数は10問必須（現在{len(v)}問）")
        return v


# ═══════════════════════════════════════════
# RSS収集
# ═══════════════════════════════════════════
RSS_FEEDS = [
    # NHK NEWS
    "https://www.nhk.or.jp/rss/news/cat0.xml",   # 主要
    "https://www.nhk.or.jp/rss/news/cat1.xml",   # 社会
    "https://www.nhk.or.jp/rss/news/cat3.xml",   # 科学・医療
    "https://www.nhk.or.jp/rss/news/cat4.xml",   # 政治
    "https://www.nhk.or.jp/rss/news/cat5.xml",   # 経済
    "https://www.nhk.or.jp/rss/news/cat6.xml",   # 国際
    "https://www.nhk.or.jp/rss/news/cat7.xml",   # スポーツ
    # Google News 日本語
    "https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja",
    "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFZ4ZERBU0FtcGhHZ0pLVUNnQVAB?hl=ja&gl=JP&ceid=JP:ja",  # 政治
    "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtcGhHZ0pLVUNnQVAB?hl=ja&gl=JP&ceid=JP:ja",  # 経済
    "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtcGhHZ0pLVUNnQVAB?hl=ja&gl=JP&ceid=JP:ja",  # 国際
]

# カテゴリ推定キーワード
POLITICS_KW = {"政府", "首相", "内閣", "国会", "与党", "野党", "選挙", "法案", "閣議", "自民", "立憲", "衆院", "参院", "外交", "防衛", "安保"}
ECONOMY_KW = {"経済", "株", "日銀", "金利", "円安", "円高", "GDP", "物価", "企業", "貿易", "財政", "予算", "景気", "市場", "インフレ", "賃金"}
INTL_KW = {"米国", "中国", "ロシア", "EU", "NATO", "国連", "ウクライナ", "中東", "韓国", "北朝鮮", "トランプ", "バイデン", "G7", "G20", "紛争", "難民"}


def fetch_news() -> list[dict]:
    """全RSSフィードからニュース記事を収集する。"""
    articles = []
    seen_titles = set()

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:30]:
                title = entry.get("title", "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                link = entry.get("link", "")
                summary = entry.get("summary", "")
                articles.append({
                    "title": title,
                    "url": link,
                    "summary": summary[:300] if summary else "",
                })
        except Exception as e:
            print(f"[WARN] RSS取得失敗: {url} — {e}")

    print(f"[INFO] 収集記事数: {len(articles)}")
    return articles


def classify_category(title: str) -> str | None:
    """タイトルからカテゴリを推定する。"""
    for kw in POLITICS_KW:
        if kw in title:
            return "politics"
    for kw in ECONOMY_KW:
        if kw in title:
            return "economy"
    for kw in INTL_KW:
        if kw in title:
            return "international"
    return None


def extract_keywords(title: str) -> list[str]:
    """タイトルから3文字以上の漢字・カタカナ語を抽出する。"""
    kanji = re.findall(r"[一-鿿]{3,}", title)
    kata = re.findall(r"[゠-ヿ]{3,}", title)
    return kanji + kata


def select_top_news(articles: list[dict], used_titles: set[str]) -> dict[str, list[dict]]:
    """
    キーワード頻度でランキングし、ジャンル別上位8件を選出する。
    used_titlesに含まれるものは除外する。
    """
    # カテゴリ分類
    categorized: dict[str, list[dict]] = {"politics": [], "economy": [], "international": []}
    keyword_counter: Counter = Counter()

    for art in articles:
        if art["title"] in used_titles:
            continue
        cat = classify_category(art["title"])
        if cat:
            art["category"] = cat
            categorized[cat].append(art)
            for kw in extract_keywords(art["title"]):
                keyword_counter[kw] += 1

    # キーワード頻度でスコア付け・ソート
    for cat in categorized:
        for art in categorized[cat]:
            art["kw_score"] = sum(keyword_counter.get(kw, 0) for kw in extract_keywords(art["title"]))
        categorized[cat].sort(key=lambda a: a["kw_score"], reverse=True)
        categorized[cat] = categorized[cat][:8]

    return categorized


# ═══════════════════════════════════════════
# Supabase操作
# ═══════════════════════════════════════════
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_used_news(sb: Client) -> set[str]:
    """4週間以内に使用済みのニュースタイトルを取得する。"""
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=28)).isoformat()
    res = sb.table("used_news").select("news_title").gte("expires_at", cutoff).execute()
    return {row["news_title"] for row in (res.data or [])}


def save_quiz_to_db(sb: Client, quiz: QuizSet, news_titles: list[str]) -> str:
    """クイズセットをSupabaseに保存する。quiz_set IDを返す。"""
    # quiz_sets 挿入
    qs_res = sb.table("quiz_sets").insert({
        "week_id": quiz.week_id,
        "week_start": quiz.week_start,
        "week_end": quiz.week_end,
        "is_published": False,
    }).execute()
    quiz_set_id = qs_res.data[0]["id"]

    # questions 挿入
    for q in quiz.questions:
        sb.table("questions").insert({
            "quiz_id": quiz_set_id,
            "order_num": q.order_num,
            "question_text": q.question_text,
            "pattern": q.pattern,
            "difficulty": q.difficulty,
            "category": q.category,
            "choice_a": q.choices[0].text,
            "choice_b": q.choices[1].text,
            "choice_c": q.choices[2].text,
            "choice_d": q.choices[3].text,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "debate_topic": q.debate_topic,
            "news_source": q.news_source,
        }).execute()

    # used_news 挿入
    now = datetime.datetime.now(datetime.timezone.utc)
    expires = now + datetime.timedelta(days=28)
    for title in news_titles:
        sb.table("used_news").insert({
            "news_title": title,
            "news_url": "",
            "used_at": now.isoformat(),
            "expires_at": expires.isoformat(),
        }).execute()

    return quiz_set_id


# ═══════════════════════════════════════════
# Gemini API呼び出し
# ═══════════════════════════════════════════
SYSTEM_PROMPT = """あなたは「ニュース時事能力検定1級」レベルの時事問題を作成する専門家です。

## 役割
与えられた最新ニュース記事に基づいて、大学弁論部向けの4択クイズを正確に作成してください。

## 絶対ルール
1. 問題文の文体は「〜について、正しい説明はどれでしょうか。」形式を基本にする
2. 問題パターンは「A型（事実提示型）」と「B型（穴埋め文脈型）」をランダムに混ぜる
3. 各選択肢は必ず30〜50字の範囲にする（これは厳守）
4. 正解は事実に基づく正確な内容にする
5. 解説は2〜3文で正解理由を明確に述べる
6. 関連論題は弁論部のディベートテーマとして使える形にする

## 誤答の作り方（3パターンを統一的に使用）
① 細部ズレ型：数値・時期・主体が微妙に違う
② 部分正解型：部分的に正しいが重要な部分が誤っている
③ 混在型：別ニュースの内容を混ぜた紛らわしい選択肢

## 配分（厳守）
- ジャンル：政治4問・経済3問・国際3問（計10問）
- 難易度：易3問（事実確認）・中4問（背景理解）・難3問（因果関係）

## 出力形式
JSONのみを出力してください。説明文やマークダウンは不要です。"""


def build_user_prompt(categorized_news: dict[str, list[dict]], week_id: str, week_start: str, week_end: str) -> str:
    """ユーザープロンプトを構築する。"""
    sections = []
    for cat, label in [("politics", "政治"), ("economy", "経済"), ("international", "国際")]:
        articles = categorized_news.get(cat, [])
        if not articles:
            continue
        lines = [f"## {label}ニュース"]
        for i, art in enumerate(articles, 1):
            lines.append(f"{i}. {art['title']}")
            if art.get("summary"):
                lines.append(f"   概要: {art['summary'][:150]}")
        sections.append("\n".join(lines))

    news_text = "\n\n".join(sections)

    return f"""以下の最新ニュース記事から、10問の4択クイズを作成してください。

{news_text}

## 配分指示
- 政治(politics): 4問（order_num: 1〜4）
- 経済(economy): 3問（order_num: 5〜7）
- 国際(international): 3問（order_num: 8〜10）
- 難易度easy: 3問、medium: 4問、hard: 3問

## メタ情報
- week_id: "{week_id}"
- week_start: "{week_start}"
- week_end: "{week_end}"

## JSONスキーマ
{{
  "week_id": "{week_id}",
  "week_start": "{week_start}",
  "week_end": "{week_end}",
  "questions": [
    {{
      "order_num": 1,
      "question_text": "問題文",
      "pattern": "A",
      "difficulty": "easy",
      "category": "politics",
      "choices": [
        {{"label": "A", "text": "選択肢A（30〜50字）"}},
        {{"label": "B", "text": "選択肢B（30〜50字）"}},
        {{"label": "C", "text": "選択肢C（30〜50字）"}},
        {{"label": "D", "text": "選択肢D（30〜50字）"}}
      ],
      "correct_answer": "A",
      "explanation": "解説2〜3文",
      "debate_topic": "関連論題1つ",
      "news_source": "元ニュースのタイトル"
    }}
  ]
}}"""


def generate_quiz_with_gemini(categorized_news: dict[str, list[dict]], week_id: str, week_start: str, week_end: str) -> QuizSet:
    """Gemini 2.5 ProでクイズJSONを生成し、Pydanticでバリデーションする。"""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-pro")

    user_prompt = build_user_prompt(categorized_news, week_id, week_start, week_end)

    response = model.generate_content(
        [
            {"role": "user", "parts": [{"text": SYSTEM_PROMPT}]},
            {"role": "model", "parts": [{"text": "了解しました。ニュース記事を提供してください。指定のJSONスキーマに従ってクイズを生成します。"}]},
            {"role": "user", "parts": [{"text": user_prompt}]},
        ],
        generation_config=genai.GenerationConfig(
            temperature=0.7,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )

    raw_text = response.text.strip()

    # JSONパース
    quiz_data = json.loads(raw_text)
    quiz = QuizSet(**quiz_data)

    return quiz


# ═══════════════════════════════════════════
# バリデーション
# ═══════════════════════════════════════════
def validate_distribution(quiz: QuizSet) -> list[str]:
    """配分ルールを検証し、エラーリストを返す。"""
    errors = []

    cat_counts = Counter(q.category for q in quiz.questions)
    if cat_counts.get("politics", 0) != 4:
        errors.append(f"政治の問題数が{cat_counts.get('politics', 0)}問（4問必要）")
    if cat_counts.get("economy", 0) != 3:
        errors.append(f"経済の問題数が{cat_counts.get('economy', 0)}問（3問必要）")
    if cat_counts.get("international", 0) != 3:
        errors.append(f"国際の問題数が{cat_counts.get('international', 0)}問（3問必要）")

    diff_counts = Counter(q.difficulty for q in quiz.questions)
    if diff_counts.get("easy", 0) != 3:
        errors.append(f"易の問題数が{diff_counts.get('easy', 0)}問（3問必要）")
    if diff_counts.get("medium", 0) != 4:
        errors.append(f"中の問題数が{diff_counts.get('medium', 0)}問（4問必要）")
    if diff_counts.get("hard", 0) != 3:
        errors.append(f"難の問題数が{diff_counts.get('hard', 0)}問（3問必要）")

    for q in quiz.questions:
        for c in q.choices:
            if len(c.text) < 30 or len(c.text) > 50:
                errors.append(f"Q{q.order_num} 選択肢{c.label}が{len(c.text)}字（30〜50字必要）")

    return errors


# ═══════════════════════════════════════════
# 週情報計算
# ═══════════════════════════════════════════
def get_week_info() -> tuple[str, str, str]:
    """今週のweek_id, week_start, week_endを返す。"""
    today = datetime.date.today()
    iso_year, iso_week, _ = today.isocalendar()
    week_id = f"{iso_year}-W{iso_week:02d}"

    monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)

    return week_id, monday.isoformat(), sunday.isoformat()


# ═══════════════════════════════════════════
# メイン処理
# ═══════════════════════════════════════════
def main():
    print("=" * 50)
    print("ニュース読んでる？ — クイズ自動生成")
    print("=" * 50)

    # 1. 週情報
    week_id, week_start, week_end = get_week_info()
    print(f"[INFO] 対象週: {week_id} ({week_start} ～ {week_end})")

    # 2. Supabase接続 & 使用済みニュース取得
    sb = get_supabase()
    used_titles = get_used_news(sb)
    print(f"[INFO] 使用済みニュース: {len(used_titles)}件")

    # 3. RSS収集
    articles = fetch_news()
    if len(articles) < 10:
        print("[ERROR] ニュース記事が不足しています。")
        return

    # 4. ジャンル別トップニュース選出
    categorized = select_top_news(articles, used_titles)
    for cat, arts in categorized.items():
        print(f"[INFO] {cat}: {len(arts)}件選出")

    if not any(categorized.values()):
        print("[ERROR] カテゴリ分類できるニュースがありません。")
        return

    # 5. Gemini APIでクイズ生成
    print("[INFO] Gemini 2.5 Pro でクイズ生成中...")
    try:
        quiz = generate_quiz_with_gemini(categorized, week_id, week_start, week_end)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSONパース失敗: {e}")
        return
    except Exception as e:
        print(f"[ERROR] Gemini API エラー: {e}")
        return

    # 6. バリデーション
    errors = validate_distribution(quiz)
    if errors:
        print("[WARN] バリデーションエラー:")
        for err in errors:
            print(f"  - {err}")
        print("[INFO] エラーありのため is_published=false で保存します。")

    # 7. Supabaseに保存
    news_titles = []
    for q in quiz.questions:
        if q.news_source:
            news_titles.append(q.news_source)

    quiz_set_id = save_quiz_to_db(sb, quiz, news_titles)
    print(f"[INFO] 保存完了: quiz_set_id = {quiz_set_id}")

    if errors:
        print("[INFO] バリデーションエラーがあったため、管理者による確認・手動公開が必要です。")
    else:
        print("[INFO] バリデーション通過。管理画面から公開してください。")

    print("=" * 50)
    print("完了")


if __name__ == "__main__":
    main()
