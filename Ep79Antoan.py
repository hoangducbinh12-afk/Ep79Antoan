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

# --- 2. LOGIC TÍNH RANK & NHẶT 5 CHẠM ĐÁY ---
def get_matrix_df_v13(db, last_full_str):
    if not db or not last_full_str: 
        return pd.DataFrame(columns=["Số", "Điểm", "Rank"])
    
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

def get_low_5_logic(df_rank):
    if df_rank.empty: return ["?"]*5
    df_bottom = df_rank.sort_values("Rank", ascending=False)
    digits = []
    for s in df_bottom["Số"]:
        for char in str(s):
            if char not in digits: digits.append(char)
            if len(digits) == 5: return sorted(digits)
    return sorted(digits)

# --- 3. GIAO DIỆN STREAMLIT ---
st.set_page_config(layout="wide", page_title="Matrix V13.88 Final")
st.title("🛡️ Matrix V13.88 - Surgical Protect (Bottom Scan)")

if 'db' not in st.session_state: st.session_state['db'] = {}
if 'history' not in st.session_state: st.session_state['history'] = []
if 'last_full_str' not in st.session_state: st.session_state['last_full_str'] = ""

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

    st.header("📸 2. QUÉT ẢNH KQ")
    up_img = st.file_uploader("Upload ảnh", type=['jpg','png','jpeg'])
    if up_img and st.button("🚀 CHẠY OCR"):
        res = load_ocr().readtext(np.array(Image.open(up_img)), detail=0)
        nums = [re.sub(r'\D','',n) for n in res if len(re.sub(r'\D','',n))>=2]
        if nums:
            st.session_state['raw_input'] = ",".join(nums)
            st.session_state['gdb_now'] = nums[0][-2:]

    st.header("📝 3. NHẬP LIỆU")
    raw_in = st.text_area("27 giải loto:", value=st.session_state.get('raw_input',''), height=100)
    gdb_now = st.text_input("GĐB (2 số cuối):", value=st.session_state.get('gdb_now',''))

    if st.button("🔥 PHÂN TÍCH & LƯU", type="primary", use_container_width=True):
        raw_list = [x.strip()[-2:] for x in raw_in.replace(","," ").split() if len(x.strip())>=2]
        if len(raw_list) >= 27 and gdb_now and st.session_state['db']:
            # BƯỚC 1: XÁC ĐỊNH CHẠM CỦA KỲ VỪA RỒI ĐỂ ĐỐI SOÁT
            df_before = get_matrix_df_v13(st.session_state['db'], st.session_state['last_full_str'])
            low_5_used = get_low_5_logic(df_before)
            
            # BƯỚC 2: CẬP NHẬT MA TRẬN
            old_mapping = get_mapping_v11(st.session_state['last_full_str'])
            for wid, wd in st.session_state['db'].items():
                num = old_mapping.get(str(wid))
                if num in raw_list[:27]:
                    wd["streak_win"], wd["streak_loss"] = wd.get("streak_win",0)+1, 0
                    wd["score"] = wd.get("score",1000.0) - 2.7
                else:
                    wd["streak_loss"], wd["streak_win"] = wd.get("streak_loss",0)+1, 0
                    wd["score"] = wd.get("score",1000.0) + 1.0
            
            # BƯỚC 3: LƯU LỊCH SỬ KÈM CHẠM ĐÃ DÙNG
            st.session_state['history'].insert(0, {
                "STT": len(st.session_state['history'])+1, 
                "GĐB": gdb_now, 
                "Chạm_Đáy": "".join(low_5_used)
            })
            st.session_state['last_full_str'] = "".join(raw_list[:27])
            st.rerun()

# --- HIỂN THỊ CHÍNH ---
if st.session_state['db'] and st.session_state['last_full_str']:
    # Tính Rank kỳ mới nhất
    df_current = get_matrix_df_v13(st.session_state['db'], st.session_state['last_full_str'])
    low_5_next = get_low_5_logic(df_current)
    
    # 1. Metric 5 Chạm Đáy cho ngày mai
    st.markdown("---")
    m1, m2 = st.columns([1, 4])
    m1.metric("🔮 5 CHẠM ĐÁY KỲ TỚI", "".join(low_5_next))
    m2.info(f"💡 Dự báo cho ngày mai dựa trên Rank 100 -> 1. Chạm: {', '.join(low_5_next)}")

    # 2. Bảng lịch sử đối soát chuẩn nhịp
    st.subheader("📜 ĐỐI SOÁT LỊCH SỬ (ĂN/TRƯỢT CHUẨN KỲ)")
    if st.session_state['history']:
        df_h = pd.DataFrame(st.session_state['history'])
        def check_correct_rhythm(row):
            g = str(row['GĐB'])[-2:]
            c_used = str(row.get('Chạm_Đáy', ""))
            if not c_used: return "-"
            is_hit = any(d in g for d in c_used)
            is_kep = g[0] == g[1] if len(g)==2 else False
            return "A" if (is_hit or is_kep) else "T"
        
        df_h['Kết quả'] = df_h.apply(check_correct_rhythm, axis=1)
        st.dataframe(df_h.reindex(columns=['STT', 'GĐB', 'Chạm_Đáy', 'Kết quả']).head(15), use_container_width=True)

    # 3. Dàn 80 số cho kỳ tới
    high_5 = set("0123456789") - set(low_5_next)
    to_remove = [f"{d1}{d2}" for d1 in high_5 for d2 in high_5 if d1 != d2]
    dàn_80 = [s for s in df_current["Số"].tolist() if s not in to_remove][:80]
    
    st.success(f"🎯 DÀN 80 SỐ TỐI ƯU (Dựa trên 5 chạm đáy mới: {', '.join(low_5_next)})")
    st.code(", ".join(dàn_80))
else:
    st.warning("👈 Nạp file JSON và nhập dữ liệu để bắt đầu soi!")
