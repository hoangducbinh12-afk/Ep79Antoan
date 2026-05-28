import streamlit as st
import pandas as pd
import json
import numpy as np
import easyocr
import re
from PIL import Image
from collections import Counter

# --- 1. CẤU HÌNH & MAPPING ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'])

def get_mapping_v11(full_str, total_pos=107):
    if not full_str or len(full_str) < total_pos:
        return {str(i): f"{i % 100:02d}" for i in range(11449)}
    return {str(i * total_pos + j): f"{full_str[i]}{full_str[j]}" for i in range(total_pos) for j in range(total_pos)}

# --- 2. LOGIC NHẶT 6 CHẠM HYBRID (3 MẠNH + 3 YẾU) ---
def get_hybrid_6_touches(df_rank):
    if df_rank.empty or "Số" not in df_rank.columns: return ["?"]*3, ["?"]*3
    
    # Nhặt 3 chạm Mạnh (Rank 1 ->)
    top_digits = []
    df_top = df_rank.sort_values("Rank", ascending=True)
    for s in df_top["Số"]:
        for char in str(s):
            if char not in top_digits: top_digits.append(char)
            if len(top_digits) == 3: break
        if len(top_digits) == 3: break
            
    # Nhặt 3 chạm Yếu (Rank 100 ->)
    bot_digits = []
    df_bot = df_rank.sort_values("Rank", ascending=False)
    for s in df_bot["Số"]:
        for char in str(s):
            if char not in bot_digits and char not in top_digits: 
                bot_digits.append(char)
            if len(bot_digits) == 3: break
        if len(bot_digits) == 3: break
            
    return sorted(top_digits), sorted(bot_digits)

# --- 3. GIAO DIỆN CHÍNH ---
st.set_page_config(layout="wide", page_title="Matrix V13.9 Stable")
st.title("🛡️ Matrix V13.9 - Hybrid 6-Touch (3 Mạnh + 3 Yếu)")

if 'db' not in st.session_state: st.session_state['db'] = {}
if 'history' not in st.session_state: st.session_state['history'] = []
if 'last_full_str' not in st.session_state: st.session_state['last_full_str'] = ""
if 'raw_input' not in st.session_state: st.session_state['raw_input'] = ""
if 'gdb_now' not in st.session_state: st.session_state['gdb_now'] = ""

# --- SIDEBAR: OCR & NHẬP LIỆU ---
with st.sidebar:
    st.header("📂 1. DỮ LIỆU GỐC")
    up_json = st.file_uploader("Nạp file .json", type=['json'])
    if up_json and st.button("XÁC NHẬN NẠP"):
        data = json.load(up_json)
        st.session_state['db'] = data.get('matrix', {})
        st.session_state['history'] = data.get('history', [])
        st.session_state['last_full_str'] = data.get('last_full_str', "")
        st.rerun()

    st.header("📸 2. QUÉT ẢNH")
    up_img = st.file_uploader("Upload ảnh", type=['jpg','png','jpeg'])
    if up_img and st.button("🚀 CHẠY OCR"):
        res = load_ocr().readtext(np.array(Image.open(up_img)), detail=0)
        nums = [re.sub(r'\D','',n) for n in res if len(re.sub(r'\D','',n))>=2]
        if nums:
            st.session_state['raw_input'] = ",".join(nums)
            st.session_state['gdb_now'] = nums[0][-2:]

    st.header("📝 3. NHẬP LIỆU")
    raw_in = st.text_area("27 giải:", value=st.session_state['raw_input'], height=100)
    gdb_now = st.text_input("GĐB:", value=st.session_state['gdb_now'])

    if st.button("🔥 PHÂN TÍCH & LƯU", type="primary", use_container_width=True):
        raw_list = [x.strip()[-2:] for x in raw_in.replace(","," ").split() if len(x.strip())>=2]
        if len(raw_list) >= 27 and gdb_now and st.session_state['db']:
            # Lấy mapping và tính Rank cũ để chốt Chốt_6
            mapping_old = get_mapping_v11(st.session_state['last_full_str'])
            stats = {f"{i:02d}": 0.0 for i in range(100)}
            for wid, wd in st.session_state['db'].items():
                num = mapping_old.get(str(wid))
                if num: stats[num] += float(wd.get('score', 1000.0))
            df_temp = pd.DataFrame([{"Số": k, "Điểm": v} for k, v in stats.items()]).sort_values("Điểm", ascending=False).reset_index(drop=True)
            df_temp["Rank"] = df_temp.index + 1
            t3, b3 = get_hybrid_6_touches(df_temp)
            
            # Cập nhật DB
            for wid, wd in st.session_state['db'].items():
                num = mapping_old.get(str(wid))
                if num in raw_list[:27]:
                    wd["streak_win"], wd["streak_loss"] = wd.get("streak_win", 0) + 1, 0
                    wd["score"] = wd.get("score", 1000.0) - 2.7
                else:
                    wd["streak_loss"], wd["streak_win"] = wd.get("streak_loss", 0) + 1, 0
                    wd["score"] = wd.get("score", 1000.0) + 1.0
            
            # Lưu lịch sử
            st.session_state['history'].insert(0, {
                "STT": len(st.session_state['history']) + 1, 
                "GĐB": gdb_now, 
                "Chốt_6": "".join(t3+b3)
            })
            st.session_state['last_full_str'] = "".join(raw_list[:27])
            st.rerun()

# --- HIỂN THỊ CHÍNH ---
if st.session_state['db'] and st.session_state['last_full_str']:
    # Hàm tính Rank mới
    mapping_new = get_mapping_v11(st.session_state['last_full_str'])
    stats_new = {f"{i:02d}": 0.0 for i in range(100)}
    for wid, wd in st.session_state['db'].items():
        num = mapping_new.get(str(wid))
        if num: stats_new[num] += float(wd.get('score', 1000.0))
    df_rank = pd.DataFrame([{"Số": k, "Điểm": v} for k, v in stats_new.items()]).sort_values("Điểm", ascending=False).reset_index(drop=True)
    df_rank["Rank"] = df_rank.index + 1
    
    top3, bot3 = get_hybrid_6_touches(df_rank)
    all_6 = sorted(list(set(top3 + bot3)))

    # Metrics
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("🔝 3 CHẠM MẠNH (RANK 1->)", ",".join(top3))
    m2.metric("📉 3 CHẠM YẾU (RANK 100->)", ",".join(bot3))
    m3.metric("🎯 TỔNG 6 CHẠM", "".join(all_6))

    # Lịch sử (FIX KEYERROR Ở ĐÂY)
    st.subheader("📜 ĐỐI SOÁT LỊCH SỬ")
    if st.session_state['history']:
        df_h = pd.DataFrame(st.session_state['history'])
        def check_at(row):
            g = str(row['GĐB'])[-2:]
            c6 = str(row.get('Chốt_6', ""))
            if not c6: return "-"
            is_hit = any(d in g for d in c6)
            is_kep = g[0] == g[1] if len(g)==2 else False
            return "A" if (is_hit or is_kep) else "T"
        
        df_h['KQ'] = df_h.apply(check_at, axis=1)
        # REINDEX đảm bảo nếu thiếu cột vẫn không sập
        view_cols = ['STT', 'GĐB', 'Chốt_6', 'KQ']
        st.dataframe(df_h.reindex(columns=view_cols).head(15), use_container_width=True)

    # Dàn 88 số
    all_digs = set("0123456789")
    remain_4 = all_digs - set(all_6)
    to_remove = [f"{d1}{d2}" for d1 in remain_4 for d2 in remain_4 if d1 != d2]
    dàn_88 = [s for s in df_rank["Số"].tolist() if s not in to_remove]
    
    st.success(f"💎 DÀN 88 SỐ (Giữ 6 chạm: {','.join(all_6)} + Kép 4 chạm còn lại)")
    st.code(", ".join(dàn_88))
else:
    st.warning("👈 Hãy nạp file JSON ở Sidebar để bắt đầu phân tích!")
