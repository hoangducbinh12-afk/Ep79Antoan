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
        # Nếu chưa có chuỗi 107 vị trí, dùng tạm mapping mặc định để không lỗi code
        return {str(i): f"{i % 100:02d}" for i in range(11449)}
    return {str(i * total_pos + j): f"{full_str[i]}{full_str[j]}" for i in range(total_pos) for j in range(total_pos)}

# --- 2. LOGIC TÍNH RANK & NHẶT 5 CHẠM ĐÁY (NHÂN VẬT CHÍNH) ---
def get_matrix_df_v13(db, last_full_str, t_val=68, w_val=10):
    if not db or not last_full_str: return pd.DataFrame()
    mapping = get_mapping_v11(last_full_str)
    stats = {f"{i:02d}": {"total_score": 0.0, "clean_wire_count": 0} for i in range(100)}
    
    for wid, wd in db.items():
        num = mapping.get(str(wid))
        if num:
            if wd.get("streak_win", 0) == 0:
                stats[num]["clean_wire_count"] += 1
                stats[num]["total_score"] += float(wd.get("score", 1000.0))
    
    res = []
    for num, s in stats.items():
        score = round(s["total_score"] / max(1, s["clean_wire_count"]), 2)
        res.append({"Số": num, "Điểm": score})
    
    df = pd.DataFrame(res).sort_values("Điểm", ascending=False).reset_index(drop=True)
    df["Rank"] = df.index + 1
    return df

def get_low_5_realtime(df_rank):
    if df_rank.empty: return ["?"]*5
    # Quét từ Rank 100 ngược lên
    df_bottom = df_rank.sort_values("Rank", ascending=False)
    digits = []
    for s in df_bottom["Số"]:
        for char in s:
            if char not in digits: digits.append(char)
            if len(digits) == 5: return sorted(digits)
    return sorted(digits)

# --- 3. GIAO DIỆN ---
st.set_page_config(layout="wide", page_title="Matrix V13.85")
st.title("🛡️ Matrix V13.85 - Real-time Bottom Scan")

if 'db' not in st.session_state: st.session_state['db'] = {}
if 'history' not in st.session_state: st.session_state['history'] = []
if 'last_full_str' not in st.session_state: st.session_state['last_full_str'] = ""

# --- SIDEBAR: OCR & LƯU ---
with st.sidebar:
    st.header("📸 QUÉT KẾT QUẢ")
    up_img = st.file_uploader("Upload ảnh KQ", type=['jpg','png'])
    if up_img and st.button("🚀 CHẠY OCR"):
        res = load_ocr().readtext(np.array(Image.open(up_img)), detail=0)
        nums = [re.sub(r'\D','',n) for n in res if len(re.sub(r'\D','',n))>=2]
        if nums:
            st.session_state['raw_input'] = ",".join(nums)
            st.session_state['gdb_now'] = nums[0][-2:]

    raw_in = st.text_area("27 giải loto:", value=st.session_state.get('raw_input',''))
    gdb_now = st.text_input("GĐB (2 số cuối):", value=st.session_state.get('gdb_now',''))

    if st.button("🔥 PHÂN TÍCH & LƯU KỲ MỚI", type="primary"):
        raw_list = [x.strip()[-2:] for x in raw_in.replace(","," ").split() if len(x.strip())>=2]
        if len(raw_list) >= 27 and gdb_now:
            # BƯỚC 1: Lấy mapping cũ để cập nhật database
            old_mapping = get_mapping_v11(st.session_state['last_full_str'])
            for wid, wd in st.session_state['db'].items():
                num = old_mapping.get(str(wid))
                if num in raw_list[:27]:
                    wd["streak_win"], wd["streak_loss"] = wd.get("streak_win",0)+1, 0
                    wd["score"] = wd.get("score",1000.0) - 2.7
                else:
                    wd["streak_loss"], wd["streak_win"] = wd.get("streak_loss",0)+1, 0
                    wd["score"] = wd.get("score",1000.0) + 1.0
            
            # BƯỚC 2: Cập nhật chuỗi 107 vị trí mới
            st.session_state['last_full_str'] = "".join(raw_list[:27])
            
            # BƯỚC 3: Lưu lịch sử
            st.session_state['history'].insert(0, {"STT": len(st.session_state['history'])+1, "GĐB": gdb_now})
            st.success("Đã cập nhật Rank và Chạm mới!")
            st.rerun()

# --- HIỂN THỊ BIẾN THIÊN ---
if st.session_state['last_full_str']:
    # Tính Rank dựa trên dữ liệu VỪA CẬP NHẬT
    df_current_rank = get_matrix_df_v13(st.session_state['db'], st.session_state['last_full_str'])
    low_5_dynamic = get_low_5_realtime(df_current_rank)
    
    # HIỂN THỊ Ô THÔNG SỐ
    st.markdown(f"### 🔮 5 Chạm Đáy Biến Thiên: `{','.join(low_5_dynamic)}`")
    
    # BẢNG ĐỐI SOÁT A/T
    st.subheader("📜 Lịch sử đối soát A/T")
    df_h = pd.DataFrame(st.session_state['history'])
    if not df_h.empty:
        def check_at(row):
            g = str(row['GĐB'])[-2:]
            is_hit = any(d in g for d in low_5_dynamic)
            is_kep = g[0] == g[1] if len(g)==2 else False
            return "A" if (is_hit or is_kep) else "T"
        
        df_h['Kết quả'] = df_h.apply(check_at, axis=1)
        st.dataframe(df_h[['STT', 'GĐB', 'Kết quả']].head(15), use_container_width=True)

    # DÀN 80 SỐ (Loại 20 con lệch của chạm cao)
    all_digs = set("0123456789")
    high_5 = all_digs - set(low_5_dynamic)
    to_remove = [f"{d1}{d2}" for d1 in high_5 for d2 in high_5 if d1 != d2]
    
    # Lấy 80 số từ Rank 1 -> 80 (đã trừ 20 con lệch chạm cao)
    dàn_full_100 = df_current_rank["Số"].tolist()
    dàn_80_final = [s for s in dàn_full_100 if s not in to_remove][:80]
    
    st.success(f"🎯 Dàn 80 số tối ưu cho kỳ sau (Dựa trên chạm {','.join(low_5_dynamic)})")
    st.code(", ".join(dàn_80_final))
