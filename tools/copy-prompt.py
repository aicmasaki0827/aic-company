#!/usr/bin/env python3
"""
サムネイルプロンプト抽出スクリプト（ChatGPT貼り付け用）

使い方:
    python tools/copy-prompt.py              # 一覧表示して番号で選ぶ
    python tools/copy-prompt.py thumb-49     # 直接指定

動作:
    briefs/.mdファイルから英語プロンプトを抽出してクリップボードにコピーする
    → ChatGPT に貼り付けるだけで画像生成できる
"""
import re
import sys
from pathlib import Path

BRIEFS_DIR = Path(".company/creative/briefs")


def extract_prompt(brief_file: Path) -> str:
    content = brief_file.read_text(encoding="utf-8")

    # 旧フォーマット: ## AI画像生成プロンプト の英語コードブロック
    match = re.search(r'英語プロンプト[^\n]*\n```\n(.+?)\n```', content, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 新フォーマット: フィールドから組み立て
    get = lambda label: next(
        (line.split(label)[-1].strip() for line in content.splitlines() if label in line), ""
    )
    concept_ja = get("パターン:")
    tone_ja    = get("トーン:")
    bg_ja      = get("背景:")
    notes_lines = []
    in_notes = False
    for line in content.splitlines():
        if "参考イメージ" in line:
            in_notes = True
            continue
        if in_notes:
            if line.startswith("##"):
                break
            if line.strip():
                notes_lines.append(line.lstrip("- ").strip())

    tone_map = {"暗め": "melancholic", "共感": "empathetic", "明るめ": "hopeful",
                "希望": "optimistic", "緊張感": "tense", "危機感": "urgent"}
    tone_en = ", ".join(v for k, v in tone_map.items() if k in tone_ja) or "calm"

    concept_map = {"状況描写": "a scene of a person in a relatable situation",
                   "テキストのみ": "minimalist abstract background",
                   "Before/After": "a split-scene showing before and after contrast"}
    concept_en = next((v for k, v in concept_map.items() if k in concept_ja), "a visual scene")

    parts = [concept_en, f"{tone_en} atmosphere"]
    if bg_ja:
        parts.append(f"color palette inspired by: {bg_ja[:100]}")
    if notes_lines:
        parts.append(". ".join(notes_lines[:2]))
    parts += ["illustration style", "no text", "no japanese characters", "professional thumbnail"]

    return ", ".join(parts)


def copy_to_clipboard(text: str) -> bool:
    try:
        import subprocess
        subprocess.run("clip", input=text.encode("utf-8"), check=True)
        return True
    except Exception:
        return False


def main():
    briefs = sorted(BRIEFS_DIR.glob("thumb-*.md"))

    # 直接指定モード
    if len(sys.argv) > 1:
        name = sys.argv[1].removesuffix(".md")
        target = BRIEFS_DIR / (name + ".md")
        if not target.exists():
            print(f"❌ 見つかりません: {target}")
            sys.exit(1)
        briefs = [target]

    # 一覧表示モード
    if len(briefs) > 1:
        print("─" * 50)
        print("  サムネイルブリーフ一覧")
        print("─" * 50)
        for i, f in enumerate(briefs, 1):
            done = "✅" if Path(f".company/creative/assets/thumbs/{f.stem}.png").exists() else "  "
            print(f"  {done} {i:2}. {f.name}")
        print("─" * 50)
        try:
            choice = int(input("番号を入力（0で終了）: "))
        except ValueError:
            print("キャンセル")
            return
        if choice == 0:
            return
        if not 1 <= choice <= len(briefs):
            print("❌ 範囲外の番号です")
            return
        briefs = [briefs[choice - 1]]

    # プロンプト抽出 & クリップボードコピー
    target = briefs[0]
    prompt = extract_prompt(target)

    print(f"\n📋 {target.name}")
    print("─" * 50)
    print(prompt)
    print("─" * 50)

    if copy_to_clipboard(prompt):
        print("\n✅ クリップボードにコピーしました！")
        print("   ChatGPT に貼り付けて「この内容でサムネイルを作って」と送信してください。")
    else:
        print("\n⚠️  クリップボードへのコピーに失敗しました。上のテキストを手動でコピーしてください。")


if __name__ == "__main__":
    main()
