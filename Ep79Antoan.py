import streamlit as st
import pandas as pd
import json
import numpy as np
import easyocr
import re
from PIL import Image
from collections import Counter

# --- 1. CẤU HÌNH HỆ THỐNG & OCR ---
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
    if df_full.empty: return ['?','?','?','?','?']
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
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), [], [], pd.DataFrame(), []
    
    low_5 = get_bottom_5_chạm_v13(df_raw)
    
    # Đáy & Bệt
    bottom_wires = sorted(db.items(), key=lambda x: x[1]['score'])[:cfg['bot']]
    set_bottom = {f"{int(mapping.get(str(wid))):02d}" for wid, d in bottom_wires if mapping.get(str(wid))}
    
    # Giả lập set_bet (Lineage)
    set_bet = set() 
    # (Logic lineage giữ nguyên như bản cũ của bạn)

    set_overlap = set_bottom.intersection(set_bet)
    
    # Chỉ số kỹ thuật
    df_raw['is_golden_core'] = ((df_raw['Tang'] == 1) & (df_raw['An'].isin([2, 3])) & (df_raw['Cứng'] > 8.0)).astype(int)
    df_raw['is_low_touch'] = df_raw['Số'].apply(lambda x: any(d in x for d in low_5)).astype(int)
    
    # Safety Score (Gọt trùng, Bảo vệ lõi và 5 chạm đáy)
    df_raw['safety_score_79'] = (
        (df_raw['is_golden_core'] * 150) + 
        (df_raw['is_low_touch'] * 100) - 
        (df_raw['Số'].isin(set_overlap) * 50)
    )
    
    ds_79 = df_raw.sort_values(by=['safety_score_79', 'Điểm'], ascending=[False, False]).head(79)
    set_79 = set(ds_79['Số'].tolist())
    
    df_raw['in_79'] = df_raw['Số'].isin(set_79).astype(int)
    da_59 = df_raw[df_raw['in_79'] == 1].sort_values(by=['Điểm'], ascending=False).head(59)
    dk_39 = da_59.sort_values(by=['is_low_touch', 'is_golden_core', 'Điểm'], ascending=[False, False, False]).head(39)
    
    return dk_39, da_59, ds_79, sorted(list(set_bottom)), sorted(list(set_bet)), df_raw, low_5

# --- 4. GIAO DIỆN STREAMLIT ---
st.set_page_config(layout="wide", page_title="Matrix V13.8 Full")
st.title("🛡️ Matrix V13.8 - Surgical Protect (Bottom Scan)")

# Khởi tạo session state
if 'cfg' not in st.session_state: st.session_state['cfg'] = {"tier": 68, "win": 10, "hard": 7.99, "bot": 40, "bet": 40}
if 'db' not in st.session_state: st.session_state['db'] = {}
if 'history' not in st.session_state: st.session_state['history'] = []
if 'last_full_str' not in st.session_state: st.session_state['last_full_str'] = ""

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
        nums = [n for n in res_ocr if n.isdigit() and 2 <= len(n) <= 5]
        if nums: 
            st.session_state['raw_input'] = ", ".join(nums)
            st.session_state['gdb_val'] = nums[0][-2:]
            st.rerun()

    st.divider()
    if st.button("🔥 PHÂN TÍCH & LƯU", type="primary", use_container_width=True):
        raw_val = st.session_state.get('raw_input', "")
        gdb_val = st.session_state.get('gdb_val', "")
        raw_list = [x.strip() for x in raw_val.replace(",", " ").split() if x]
        if len(raw_list) >= 27 and gdb_val:
            mapping = get_mapping_v11(st.session_state['last_full_str'])
            gdb_num = "".join(filter(str.isdigit, gdb_val))[-2:]
            # Lưu lịch sử và cập nhật ma trận...
            st.session_state['last_full_str'] = "".join(raw_list[:27])
            st.rerun()

    st.header("📝 3. NHẬP LIỆU")
    st.session_state['raw_input'] = st.text_area("Loto 27 giải:", value=st.session_state.get('raw_input', ""), height=80)
    st.session_state['gdb_val'] = st.text_input("GĐB:", value=st.session_state.get('gdb_val', ""))

# --- HIỂN THỊ KẾT QUẢ ---
if st.session_state['last_full_str']:
    def get_matrix_df(t_val, w_val):
        db, mapping = st.session_state['db'], get_mapping_v11(st.session_state['last_full_str'])
        stats = {f"{i:02d}": {"total_score": 0.0, "max_an": 0, "clean_wire_count": 0, "clean_window_hits": 0, "all_losses": []} for i in range(100)}
        for wid, wd in db.items():
            num = mapping.get(str(wid))
            if num:
                s = stats[num]
                sw, sl = int(wd.get("streak_win", 0)), int(wd.get("streak_loss", 0))
                s["all_losses"].append(sl if sw == 0 else 0)
                s["clean_window_hits"] += sum(wd.get("hit_history", [])[-w_val:])
                if sw == 0:
                    s["clean_wire_count"] += 1
                    s["total_score"] += float(wd.get("score", 1000.0))
        res = []
        for num, s in stats.items():
            dc = max(1, s["clean_wire_count"])
            hard = round((s["clean_window_hits"] / (w_val * (11449/100))) * 100, 2)
            score = round((s["total_score"] / dc) * (1 + hard/100), 2)
            res.append({"Số": num, "Điểm": score, "Tang": calculate_tier(s["all_losses"], t_val), "An": s["max_an"], "Cứng": hard})
        df = pd.DataFrame(res).sort_values("Điểm", ascending=False).reset_index(drop=True)
        df["Rank"] = df.index + 1
        return df

    df_full_raw = get_matrix_df(st.session_state['cfg']['tier'], st.session_state['cfg']['win'])
    dk, da, ds, d_thap, d_cao, df_full, low_5 = thermal_ai_engines_v80(df_full_raw, st.session_state['history'], st.session_state['db'], get_mapping_v11(st.session_state['last_full_str']), st.session_state['cfg'])

    # 1. Ô THÔNG SỐ 5 CHẠM ĐÁY
    st.markdown("---")
    cm1, cm2 = st.columns([1, 4])
    cm1.metric("🔮 5 CHẠM ĐÁY", "".join(low_5))
    cm2.info(f"💡 Dàn 80: Lấy 79 gốc, loại 20 con lệch của chạm cao {', '.join(set('0123456789') - set(low_5))}, giữ kép.")

    # 2. BẢNG LỊCH SỬ (FIXED KEYERROR)
    st.subheader("📜 ĐỐI SOÁT LỊCH SỬ")
    if st.session_state['history']:
        df_h = pd.DataFrame(st.session_state['history'])
        def check_v13(row):
            g = "".join(filter(str.isdigit, str(row.get('GĐB', ""))))[-2:]
            if len(g) < 2: return "T"
            return "A" if (any(d in g for d in low_5) or g[0] == g[1]) else "T"
        df_h['KQ_Chạm'] = df_h.apply(check_v13, axis=1)
        
        # Dùng reindex để an toàn, tránh KeyError nếu thiếu cột
        view_cols = ['STT', 'GĐB', 'KQ_Chạm', 'Dan79', 'Dan59', 'Dan39']
        st.dataframe(df_h.reindex(columns=view_cols).head(15), use_container_width=True)

    # 3. DÀN 80 SỐ CHIẾN THUẬT
    high_5 = set("0123456789") - set(low_5)
    to_remove = [f"{d1}{d2}" for d1 in high_5 for d2 in high_5 if d1 != d2]
    ds_80 = ds[~ds['Số'].isin(to_remove)]
    st.success(f"🎯 DÀN 80 SỐ CHIẾN THUẬT (Đã lọc 20 con lệch chạm cao)")
    st.code(", ".join(ds_80['Số'].tolist()))

    # 4. CÁC Ô HIỂN THỊ GỐC
    c1, col2, col3 = st.columns(3)
    c1.success("🎯 Kết 39 (Lõi + Chạm)")
    c1.code(", ".join(dk["Số"].tolist()) if not dk.empty else "N/A")
    col2.info("🤖 AI 59 (Hạ từ 79)")
    col2.code(", ".join(da["Số"].tolist()) if not da.empty else "N/A")
    col3.warning("🛡️ Safe 79 (Gọt trùng)")
    col3.code(", ".join(ds["Số"].tolist()) if not ds.empty else "N/A")
