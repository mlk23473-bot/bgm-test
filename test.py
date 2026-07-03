import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import pandas as pd
import os
import time

# 画面の基本設定
st.set_page_config(page_title="USEN BGM 提案ツール", page_icon="🎵")

st.title("🎵 USEN BGM 営業提案ツール")
st.write("内装・業種・ターゲット等に合わせてそのお店に最適なBGMチャンネルを厳選し、お店にとってどのような効果・メリットがあるかを踏まえて提案します。")

# --- APIキーの自動読み込み（Secrets対応） ---
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    st.sidebar.title("⚙️ 初期設定")
    api_key = st.sidebar.text_input("Gemini APIキー", type="password")

# --- CSVマスタの読み込みチェック ---
csv_file = "channels.csv"
if not os.path.exists(csv_file):
    st.error(f"⚠️ デスクトップに '{csv_file}' が見つかりません。ファイルを配置してください。")
    st.stop()

# CSVを読み込む
df = pd.read_csv(csv_file, encoding='utf-8')
st.sidebar.success(f"📊 チャンネルマスタを読み込みました ({len(df)} チャンネル)")

# メイン画面のURL入力欄
url_input = st.text_input("お店の情報がわかるURL（公式HPなど）を入力してください")

# 分析実行ボタン
if st.button("AIで分析してBGM(3ch)と導入メリットを提案"):
    if not api_key:
        st.warning("※APIキーが読み込めませんでした。設定をご確認ください。")
    elif not url_input:
        st.warning("※URLが入力されていません。")
    else:
        with st.spinner("ウェブサイトを分析し、1000chのマスタから最適な番組と効果タグを作成中..."):
            try:
                # 1. URL読み取り
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url_input, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                page_text = soup.get_text(strip=True)[:3000]

                # 2. AI初期設定
                genai.configure(api_key=api_key)
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                model_name = next((m for m in available_models if 'flash' in m), available_models[0])
                model = genai.GenerativeModel(model_name)

                # 3. キーワード抽出
                keyword_prompt = f"""
                以下の店舗のウェブサイト情報から、このお店の「業態」や「雰囲気」を表す検索キーワードを日本語で3〜5個、カンマ区切りだけで出力してください。
                【ウェブサイト情報】
                {page_text}
                """
                kw_response = model.generate_content(keyword_prompt)
                keywords = [k.strip() for k in kw_response.text.split(",") if k.strip()]
                
                time.sleep(2) # 無料枠エラー防止の待機
                
                # 4. CSVマスタ絞り込み
                matched_dfs = []
                for kw in keywords:
                    mask = df.astype(str).apply(lambda x: x.str.contains(kw, case=False, na=False)).any(axis=1)
                    matched_dfs.append(df[mask])
                
                if matched_dfs:
                    filtered_df = pd.concat(matched_dfs).drop_duplicates().head(40)
                else:
                    filtered_df = df.head(40)
                
                extracted_master = filtered_df.to_string(index=False)

                # 5. AIへの本番指示書（詳しい解説はそのままに、効果タグのみ追加）
                prompt = f"""
                あなたはUSENのトップセールス・BGM空間コーディネーターです。
                以下のウェブサイト情報からお店の特性を分析し、提供された【厳選チャンネルリスト】の中から最もマッチするチャンネルを3つ選定し、お店のオーナー様が導入メリットを感じる詳しい営業提案を行ってください。

                【ウェブサイト情報】
                {page_text}

                【厳選チャンネルリスト（CSVから抽出）】
                {extracted_master}

                【提案の必須条件】
                - 必ず【厳選チャンネルリスト】にあるチャンネルから3つ選んでください。
                - ランチ/ディナー/カフェタイム等のシーン別や、顧客のターゲット層、空間演出（居心地アップ/活気/マスキング効果等）の切り口を変えて3つの異なる魅力を提案してください。
                - 各提案には、期待できるビジネス効果を一目で把握できるよう、バッククォートで囲んだラベル（例: `🏷️ 客単価UP` `🏷️ 回転率向上` `🏷️ マスキング効果` `🏷️ ブランド価値向上` など）を2〜3個付与してください。
                - 選定理由や営業メリットの文章は簡略化せず、オーナー様を納得させる詳しいビジネスメリットを展開してください。

                【出力フォーマット】
                ### 🏢 対象店舗の分析
                * **業態・コンセプト:** * **雰囲気・内装:** * **想定ターゲット層:** ---
                ### 🎧 おすすめUSENチャンネル＆導入メリット提案（厳選3ch）

                #### 💡 提案①：[チャンネル名または番号]（例：ランチタイム・活気重視などシーン名も添えて）
                * **効果タグ:** `🏷️ [効果タグ1]` `🏷️ [効果タグ2]`
                * **選定の理由:** [なぜこのお店に合うのか、これまで通り詳しく記載]
                * **🌟 期待できる導入効果・メリット:** [ビジネスにどう貢献するか、これまで通り詳しく具体的に記載]

                #### 💡 提案②：[チャンネル名または番号]（例：ディナータイム・客単価アップなどシーン名も添えて）
                * **効果タグ:** `🏷️ [効果タグ1]` `🏷️ [効果タグ2]`
                * **選定の理由:** [別のシーンや切り口での理由を詳しく記載]
                * **🌟 期待できる導入効果・メリット:** [ビジネスにどう貢献するか詳しく具体的に記載]

                #### 💡 提案③：[チャンネル名または番号]（例：リラックス・空間演出重視などシーン名も添えて）
                * **効果タグ:** `🏷️ [効果タグ1]` `🏷️ [効果タグ2]`
                * **選定の理由:** [さらなる切り口での理由を詳しく記載]
                * **🌟 期待できる導入効果・メリット:** [ビジネスにどう貢献するか詳しく具体的に記載]
                """

                # 6. 実行＆制限エラー時自動リトライ
                try:
                    ai_response = model.generate_content(prompt)
                except Exception as e_quota:
                    if "429" in str(e_quota):
                        st.info("⏳ アクセス集中を避けるため数秒待機して再実行しています...")
                        time.sleep(10)
                        ai_response = model.generate_content(prompt)
                    else:
                        raise e_quota
                
                # 7. 表示
                st.success("1000chマスタからの厳選・効果タグ付き3提案の作成が完了しました！")
                st.markdown(ai_response.text)

            except Exception as e:
                st.error("エラーが発生しました。時間を置いて再度お試しいただくか、入力したURLをご確認ください。")
                st.error(f"詳細なエラー内容: {e}")