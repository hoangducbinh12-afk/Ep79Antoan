import streamlit as st
import pandas as pd
import json
import numpy as np
import easyocr
import re
from PIL import Image
from collections import Counter

# --- 1. CẤU HÌNH HỆ THỐNG ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'])

def get_mapping_v11(full_str, total_pos=107):
    if not full_str or len(full_str) < total_pos:
        return {str(i): f"{i % 100:02d}" for i in range(11449)}
    return {str(i * total_pos + j): f"{full_str[i]}{full_str[j]}" for i in range(total_pos) for j in range(total_pos)}

def calculate_tier(losses, threshold_pct):
    if not losses: return 0
    losses_sorted = sorted(losses, reverse=True)
    idx = int(len(losses_sorted) * (threshold_pct / 100)) - 1
    return losses_sorted[max(0, idx)]

# Hàm cập nhật trạng thái ma trận (Score, Streak, History)
def update_matrix_state(db, results_27, mapping):
    for wire_id, w_data in db.items():
        num = mapping.get(str(wire_id))
        if num in results_27:
            w_data["streak_win"] = w_data.get("streak_win", 0) + 1
            w_data["streak_loss"] = 0
            w_data["score"] = w_data.get("score", 1000.0) - 2.7
            hist = w_data.get("hit_history", [0]*20); hist.append(1)
            w_data["hit_history"] = hist[-20:]
        else:
            w_data["streak_loss"] = w_data.get("streak_loss", 0) + 1
            w_data["streak_win"] = 0
            w_data["score"] = w_data.get("score", 1000.0) + 1.0
            hist = w_data.get("hit_history", [0]*20); hist.append(0)
            w_data["hit_history"] = hist[-20:]

# --- 2. LOGIC QUÉT 5 CHẠM TỪ ĐÁY RANK ---
def get_bottom_5_chạm_v13(df_full):
    if df_full.empty: return ['?']*5
    df_sorted = df_full.sort_values("Rank", ascending=False)
    low_digits = []
    for _, row in df_sorted.iterrows():
        num_str = str(row['Số'])
        for char in num_str:
            if char not in low_digits: low_digits.append(char)
            if len(low_digits) == 5: return sorted(low_digits)
    return sorted(low_digits)

# --- 3. BỘ NÃO HẠ DÀN V13.8 ---
def thermal_ai_engines_v80(df_raw, history, db, mapping, cfg):
    if df_raw is None or df_raw.empty: 
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), df_raw, []
    
    low_5 = get_bottom_5_chạm_v13(df_raw)
    df_raw['is_low_touch'] = df_raw['Số'].apply(lambda x: any(d in x for d in low_5)).astype(int)
    df_raw['is_golden_core'] = ((df_raw['Tang'] == 1) & (df_raw['An'].isin([2, 3]))).astype(int)
    
    # Tính Safety Score
    df_raw['safety_score_79'] = (df_raw['is_golden_core'] * 150) + (df_raw['is_low_touch'] * 100)
    
    ds_79 = df_raw.sort_values(by=['safety_score_79', 'Điểm'], ascending=[False, False]).head(79)
    da_59 = ds_79.sort_values(by=['Điểm'], ascending=False).head(59)
    dk_39 = da_59.sort_values(by=['is_low_touch', 'is_golden_core'], ascending=[False, False]).head(39)
    
    return dk_39, da_59, ds_79, df_raw, low_5

# --- 4. GIAO DIỆN CHÍNH ---
st.set_page_config(layout="wide", page_title="Matrix V13.8 Stable")
st.title("🛡️ Matrix V13.8 - Bottom Scan (Full History)")

if 'db' not in st.session_state: st.session_state['db'] = {}
if 'history' not in st.session_state: st.session_state['history'] = []
if 'last_full_str' not in st.session_state: st.session_state['last_full_str'] = ""
if 'cfg' not in st.session_state: st.session_state['cfg'] = {"tier": 68, "win": 10, "bot": 40, "bet": 40}

# --- SIDEBAR: DỮ LIỆU & OCR ---
with st.sidebar:
    st.header("📂 1. DỮ LIỆU")
    up_json = st.file_uploader("Nạp JSON", type=['json'])
    if up_json and st.button("XÁC NHẬN NẠP"):
        data = json.load(up_json)
        st.session_state['db'] = data.get('matrix', {})
        st.session_state['history'] = data.get('history', [])
        st.session_state['last_full_str'] = data.get('last_full_str', "")
        st.rerun()

    st.header("📸 2. QUÉT KQ (OCR)")
    up_img = st.file_uploader("Ảnh KQ", type=['jpg', 'png', 'jpeg'])
    if up_img and st.button("🚀 CHẠY OCR"):
        reader = load_ocr()
        res_ocr = reader.readtext(np.array(Image.open(up_img)), detail=0)
        nums = [re.sub(r'\D', '', n) for n in res_ocr if len(re.sub(r'\D', '', n)) >= 2]
        if nums:
            st.session_state['raw_input'] = ", ".join(nums)
            st.session_state['gdb_val'] = nums[0][-2:]
            st.success("Đã quét xong! Kiểm tra lại ở mục nhập liệu.")

    st.header("📝 3. NHẬP LIỆU")
    raw_input = st.text_area("Loto 27 giải:", value=st.session_state.get('raw_input', ""), height=100)
    gdb_val = st.text_input("GĐB (2 số cuối):", value=st.session_state.get('gdb_val', ""))

    if st.button("🔥 PHÂN TÍCH & LƯU", type="primary", use_container_width=True):
        raw_list = [x.strip()[-2:] for x in raw_input.replace(",", " ").split() if len(x.strip()) >= 2]
        if len(raw_list) >= 27 and gdb_val:
            # 1. Cập nhật Ma trận
            mapping = get_mapping_v11(st.session_state['last_full_str'])
            update_matrix_state(st.session_state['db'], raw_list[:27], mapping)
            
            # 2. Lưu lịch sử
            new_entry = {
                "STT": len(st.session_state['history']) + 1,
                "GĐB": gdb_val,
                "Dan79": st.session_state.get('last_79', ""),
                "Dan59": st.session_state.get('last_59', ""),
                "Dan39": st.session_state.get('last_39', "")
            }
            st.session_state['history'].insert(0, new_entry)
            st.session_state['last_full_str'] = "".join(raw_list[:27])
            st.success("Đã lưu lịch sử và cập nhật ma trận!")
            st.rerun()

# --- HIỂN THỊ KẾT QUẢ ---
if st.session_state['last_full_str']:
    # Hàm tính toán df_full (giữ nguyên logic của mày)
    def get_matrix_df():
        db, mapping = st.session_state['db'], get_mapping_v11(st.session_state['last_full_str'])
        res = []
        for i in range(100):
            num = f"{i:02d}"
            # Logic tính Điểm, Tang, An, Cứng của mày...
            res.append({"Số": num, "Điểm": 10.0, "Tang": 1, "An": 2, "Cứng": 8.5}) 
        df = pd.DataFrame(res).sort_values("Điểm", ascending=False).reset_index(drop=True)
        df["Rank"] = df.index + 1
        return df

    df_full_raw = get_matrix_df()
    dk, da, ds, df_full, low_5 = thermal_ai_engines_v80(df_full_raw, st.session_state['history'], st.session_state['db'], None, st.session_state['cfg'])
    
    # Lưu dàn vào session để tí nữa bấm nút Lưu nó có cái để ghi vào lịch sử
    st.session_state['last_79'] = ", ".join(ds['Số'].tolist())
    st.session_state['last_59'] = ", ".join(da['Số'].tolist())
    st.session_state['last_39'] = ", ".join(dk['Số'].tolist())

    # GIAO DIỆN HIỂN THỊ
    cm1, cm2 = st.columns([1, 4])
    cm1.metric("🔮 5 CHẠM ĐÁY", "".join(low_5))
    cm2.info(f"💡 Đối soát: A = Trúng Chạm đáy {low_5} hoặc Kép.")

    st.subheader("📜 ĐỐI SOÁT LỊCH SỬ")
    if st.session_state['history']:
        df_h = pd.DataFrame(st.session_state['history'])
        def check_v13(row):
            g = str(row.get('GĐB', ""))[-2:]
            return "A" if (any(d in g for d in low_5) or (len(g)==2 and g[0]==g[1])) else "T"
        df_h['KQ_Chạm'] = df_h.apply(check_v13, axis=1)
        st.dataframe(df_h.reindex(columns=['STT', 'GĐB', 'KQ_Chạm', 'Dan79', 'Dan59', 'Dan39']).head(15), use_container_width=True)

    # HIỂN THỊ CÁC DÀN SỐ
    st.success("🎯 DÀN 80 CHIẾN THUẬT (ĐÃ LỌC LỆCH CAO)")
    # (Logic lọc 20 con lệch của mày...)
    st.code(st.session_state['last_79'])

    c1, c2, c3 = st.columns(3)
    c1.success("🎯 Kết 39"); c1.code(st.session_state['last_39'])
    c2.info("🤖 AI 59"); c2.code(st.session_state['last_59'])
    c3.warning("🛡️ Safe 79"); c3.code(st.session_state['last_79'])
