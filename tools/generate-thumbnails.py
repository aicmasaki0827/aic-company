#!/usr/bin/env python3
"""
サムネイル自動生成スクリプト
briefs/ の .md ファイルを読み込み、DALL-E 3 API で画像を生成・保存する

使い方:
    1. APIキーを環境変数にセット
       Windows: set OPENAI_API_KEY=sk-xxxx
    2. 実行
       python tools/generate-thumbnails.py

    特定ファイルだけ生成する場合:
       python tools/generate-thumbnails.py thumb-49-nigasita-yameidoki
"""
import os
import re
import sys
import time
import requests
from pathlib import Path
from openai import OpenAI

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
API_KEY    = os.environ.get("OPENAI_API_KEY", "")
BRIEFS_DIR = Path(".company/creative/briefs")
OUTPUT_DIR = Path(".company/creative/assets/thumbs")
IMAGE_SIZE    = "1792x1024"   # 横長（YouTube / NOTE サムネイル向け）
IMAGE_QUALITY = "standard"    # "standard" or "hd"（hd は約2倍の料金）
SLEEP_SEC     = 1.0           # 連続生成時のウェイト（秒）


# ─────────────────────────────────────────
# プロンプト抽出
# ─────────────────────────────────────────

def extract_prompt_old_format(content: str) -> str | None:
    """旧フォーマット: ## AI画像生成プロンプト の英語コードブロックを取得"""
    match = re.search(
        r'英語プロンプト[^\n]*\n```\n(.+?)\n```',
        content,
        re.DOTALL,
    )
    return match.group(1).strip() if match else None


def build_prompt_new_format(content: str) -> str:
    """新フォーマット: 各フィールドを読んで英語プロンプトを組み立てる"""
    get = lambda label: next(
        (line.split(label)[-1].strip() for line in content.splitlines() if label in line),
        ""
    )

    concept_ja = get("パターン:")
    tone_ja    = get("トーン:")
    bg_ja      = get("背景:")
    notes_ja   = ""
    in_notes   = False
    for line in content.splitlines():
        if "参考イメージ" in line:
            in_notes = True
            continue
        if in_notes:
            if line.startswith("##"):
                break
            if line.strip():
                notes_ja += line.lstrip("- ").strip() + " "

    # 日本語 → 英語マッピング
    tone_map = {
        "暗め": "melancholic, introspective",
        "共感": "empathetic, relatable",
        "明るめ": "hopeful, warm",
        "希望": "optimistic",
        "緊張感": "tense, urgent",
        "危機感": "alarming",
    }
    tone_en = ", ".join(v for k, v in tone_map.items() if k in tone_ja) or "calm, thoughtful"

    concept_map = {
        "状況描写": "a scene depicting a person in a relatable everyday situation",
        "テキストのみ": "minimalist abstract background",
        "Before/After": "a split-scene showing contrast",
    }
    concept_en = next((v for k, v in concept_map.items() if k in concept_ja), "a visual scene")

    parts = [concept_en, f"{tone_en} atmosphere"]
    if bg_ja:
        parts.append(f"color palette: {bg_ja[:120]}")
    if notes_ja:
        parts.append(notes_ja[:200])
    parts += ["illustration style", "no text", "no japanese characters", "professional thumbnail design"]

    return ", ".join(parts)


def get_prompt(brief_file: Path) -> str:
    content = brief_file.read_text(encoding="utf-8")
    prompt = extract_prompt_old_format(content)
    if prompt:
        return prompt
    return build_prompt_new_format(content)


# ─────────────────────────────────────────
# 画像生成
# ─────────────────────────────────────────

def generate(client: OpenAI, brief_file: Path) -> str:
    """
    Returns: "generated" | "skipped" | "error"
    """
    output_file = OUTPUT_DIR / (brief_file.stem + ".png")

    if output_file.exists():
        print(f"  ⏭  スキップ（既存）: {output_file.name}")
        return "skipped"

    prompt = get_prompt(brief_file)
    format_label = "旧" if extract_prompt_old_format(brief_file.read_text(encoding="utf-8")) else "新"
    print(f"  🖼  [{format_label}] {brief_file.name}")
    print(f"      プロンプト: {prompt[:90]}...")

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=IMAGE_SIZE,
            quality=IMAGE_QUALITY,
            n=1,
        )
        url = response.data[0].url
        img_bytes = requests.get(url, timeout=60).content
        output_file.write_bytes(img_bytes)
        size_kb = len(img_bytes) // 1024
        print(f"      ✅ 保存: {output_file}  ({size_kb} KB)")
        return "generated"

    except Exception as e:
        print(f"      ❌ エラー: {e}")
        return "error"


# ─────────────────────────────────────────
# メイン
# ─────────────────────────────────────────

def main():
    if not API_KEY:
        print("❌  OPENAI_API_KEY が設定されていません。")
        print("    Windows: set OPENAI_API_KEY=sk-xxxx")
        print("    Mac/Linux: export OPENAI_API_KEY=sk-xxxx")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=API_KEY)

    # 対象ファイルを決定
    if len(sys.argv) > 1:
        # 引数でファイル名（拡張子なし）を指定した場合
        targets = [BRIEFS_DIR / (arg.removesuffix(".md") + ".md") for arg in sys.argv[1:]]
        targets = [f for f in targets if f.exists()]
        if not targets:
            print("❌  指定されたブリーフファイルが見つかりません。")
            sys.exit(1)
    else:
        targets = sorted(BRIEFS_DIR.glob("thumb-*.md"))

    total = len(targets)
    # 料金の目安（standard / 1792x1024 = 約0.08ドル ≒ 12円）
    cost_yen = sum(
        0 if (OUTPUT_DIR / (f.stem + ".png")).exists() else 12
        for f in targets
    )
    print(f"📁  ブリーフ: {total} 件  |  出力先: {OUTPUT_DIR}")
    print(f"💴  生成コスト目安: 約 {cost_yen} 円")
    print()

    gen, skip, err = 0, 0, 0
    for i, brief_file in enumerate(targets, 1):
        print(f"[{i}/{total}]")
        result = generate(client, brief_file)
        if result == "generated":
            gen += 1
            if i < total:
                time.sleep(SLEEP_SEC)
        elif result == "skipped":
            skip += 1
        else:
            err += 1

    print()
    print(f"🎉  完了  生成={gen}  スキップ={skip}  エラー={err}")


if __name__ == "__main__":
    main()
