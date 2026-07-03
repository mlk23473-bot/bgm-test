import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import pandas as pd
import os
import time # 時間を制御する部品を追加

# 画面の基本設定
st.set_page_config(page_title="USEN BGM 提案ツール", page_icon="🎵")

st.title("🎵 USEN BGM AI営業提案ツール (CSVマスタ・3ch提案版)")
st.write("お店のURLと1000chのCSVマスタを連動させ、最適なBGMを3つ厳選して提案します。")

# サイドバーにAPIキー入力欄を設置
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
url_input = st.text_input("お店のURL（公式HPなど）を入力してください")

# 分析実行ボタン
if st.button("AIで分析してBGM(3ch)と導入メリットを提案"):
    if not api_key:
        st.warning("※画面左側のメニューからAPIキーを入力してください。")
    elif not url_input:
        st.warning("※URLが入力されていません。")
    else:
        with st.spinner("ウェブサイトを分析し、1000chのマスタから最適な番組を3つ厳選中..."):
            try:
                # 1. URL先のウェブサイトからテキストを読み取る
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url_input, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                page_text = soup.get_text(strip=True)[:3000]

                # 2. AI（Gemini）の初期設定と自動モデル選択
                genai.configure(api_key=api_key)
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                model_name = next((m for m in available_models if 'flash' in m), available_models[0])
                model = genai.GenerativeModel(model_name)

                # 3. AIにまず「お店のキーワード」を抽出させる
                keyword_prompt = f"""
                以下の店舗のウェブサイト情報から、このお店の「業態」や「雰囲気」を表す検索キーワードを日本語で3〜5個、カンマ区切りだけで出力してください。
                【ウェブサイト情報】
                {page_text}
                """
                kw_response = model.generate_content(keyword_prompt)
                keywords = [k.strip() for k in kw_response.text.split(",") if k.strip()]
                
                # --- 無料枠制限（1分間5回）を回避するための短い休憩 ---
                time.sleep(2)
                
                # 4. CSVマスタからキーワードにヒットするチャンネルを抽出
                matched_dfs = []
                for kw in keywords:
                    mask = df.astype(str).apply(lambda x: x.str.contains(kw, case=False, na=False)).any(axis=1)
                    matched_dfs.append(df[mask])
                
                if matched_dfs:
                    filtered_df = pd.concat(matched_dfs).drop_duplicates().head(40)
                else:
                    filtered_df = df.head(40)
                
                extracted_master = filtered_df.to_string(index=False)

                # 5. AIへの本番の指示書（プロンプト）
                prompt = f"""
                あなたはUSENのトップセールス・BGM空間コーディネーターです。
                以下のウェブサイト情報からお店の特性を分析し、提供された【厳選チャンネルリスト】の中から最もマッチするチャンネルを3つ選定し、お店のオーナー様が導入メリットを感じる営業提案を行ってください。

                【ウェブサイト情報】
                {page_text}

                【厳選チャンネルリスト（CSVから抽出）】
                {extracted_master}

                【提案の必須条件】
                - 必ず【厳選チャンネルリスト】にあるチャンネルから3つ選んでください。
                - ランチ/ディナー/カフェタイム等のシーン別や、顧客のターゲット層、空間演出（居心地アップ/活気/マスキング効果等）の切り口を変えて3つの異なる魅力を提案してください。
                - 「マスキング効果（雑音が消える）」「イメージ効果（店の格が上がる）」「行動心理効果（滞在時間延長による客単価アップ、またはアップテンポによる回転率向上）」などの具体的なビジネスメリットを組み込んで営業トークを展開してください。

                【出力フォーマット】
                ### 🏢 対象店舗の分析
                * **業態・コンセプト:** * **雰囲気・内装:** * **想定ターゲット層:** ---
                ### 🎧 おすすめUSENチャンネル＆導入メリット提案（厳選3ch）

                #### 💡 提案①：[チャンネル名または番号]（シーン・目的）
                * **選定の理由:** [理由を記載]
                * **🌟 期待できる導入効果・メリット:** [ビジネスメリットを具体的に]

                #### 💡 提案②：[チャンネル名または番号]（シーン・目的）
                * **選定の理由:** [理由を記載]
                * **🌟 期待できる導入効果・メリット:** [ビジネスメリットを具体的に]

                #### 💡 提案③：[チャンネル名または番号]（シーン・目的）
                * **選定の理由:** [理由を記載]
                * **🌟 期待できる導入効果・メリット:** [ビジネスメリットを具体的に]
                """

                # 6. 無料枠制限エラーが出た場合は自動で10秒待って再実行する賢い仕組み
                try:
                    ai_response = model.generate_content(prompt)
                except Exception as e_quota:
                    if "429" in str(e_quota):
                        st.info("⏳ アクセスが集中したため、AIが数秒間待機して再試行しています...")
                        time.sleep(10)
                        ai_response = model.generate_content(prompt)
                    else:
                        raise e_quota
                
                # 7. 画面に結果を表示する
                st.success("1000chマスタからの厳選・3提案の作成が完了しました！")
                st.markdown(ai_response.text)

            except Exception as e:
                st.error("エラーが発生しました。時間を置いて再度お試しいただくか、入力したURLをご確認ください。")
                st.error(f"詳細なエラー内容: {e}")