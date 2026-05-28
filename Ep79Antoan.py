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
    if df_rank.empty: return ["?"]*6
    
    # Nhặt 3 chạm Mạnh (Từ Rank 1 trở xuống)
    top_digits = []
    df_top = df_rank.sort_values("Rank", ascending=True)
    for s in df_top["Số"]:
        for char in str(s):
            if char not in top_digits: top_digits.append(char)
            if len(top_digits) == 3: break
        if len(top_digits) == 3: break
            
    # Nhặt 3 chạm Yếu (Từ Rank 100 ngược lên)
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
st.set_page_config(layout="wide", page_title="Matrix V13.9 Hybrid")
st.title("🛡️ Matrix V13.9 - Hybrid 6-Touch (3 Mạnh + 3 Yếu)")

if 'db' not in st.session_state: st.session_state['db'] = {}
if 'history' not in st.session_state: st.session_state['history'] = []
if 'last_full_str' not in st.session_state: st.session_state['last_full_str'] = ""

# --- SIDEBAR XỬ LÝ DỮ LIỆU ---
with st.sidebar:
    st.header("📂 1. DỮ LIỆU")
    up_json = st.file_uploader("Nạp file .json", type=['json'])
    if up_json and st.button("XÁC NHẬN NẠP"):
        data = json.load(up_json)
        st.session_state['db'] = data.get('matrix', {})
        st.session_state['history'] = data.get('history', [])
        st.session_state['last_full_str'] = data.get('last_full_str', "")
        st.rerun()

    st.header("📸 2. QUÉT ẢNH")
    up_img = st.file_uploader("Ảnh KQ", type=['jpg','png','jpeg'])
    if up_img and st.button("🚀 OCR SCAN"):
        res = load_ocr().readtext(np.array(Image.open(up_img)), detail=0)
        nums = [re.sub(r'\D','',n) for n in res if len(re.sub(r'\D','',n))>=2]
        if nums:
            st.session_state['raw_in'] = ",".join(nums)
            st.session_state['gdb_now'] = nums[0][-2:]

    raw_in = st.text_area("27 giải:", value=st.session_state.get('raw_in',''), height=100)
    gdb_now = st.text_input("GĐB:", value=st.session_state.get('gdb_now',''))

    if st.button("🔥 LƯU & CẬP NHẬT RANK", type="primary", use_container_width=True):
        raw_list = [x.strip()[-2:] for x in raw_in.replace(","," ").split() if len(x.strip())>=2]
        if len(raw_list) >= 27 and gdb_now and st.session_state['db']:
            # Tính chạm chốt kỳ này TRƯỚC KHI cập nhật
            def get_df_temp():
                mapping = get_mapping_v11(st.session_state['last_full_str'])
                res = []
                for i in range(100):
                    num = f"{i:02d}"
                    score = sum([float(wd['score']) for wid, wd in st.session_state['db'].items() if mapping.get(str(wid)) == num])
                    res.append({"Số": num, "Điểm": score})
                df = pd.DataFrame(res).sort_values("Điểm", ascending=False).reset_index(drop=True)
                df["Rank"] = df.index + 1
                return df
            
            df_old = get_df_temp()
            t3, b3 = get_hybrid_6_touches(df_old)
            
            # Cập nhật DB
            old_map = get_mapping_v11(st.session_state['last_full_str'])
            for wid, wd in st.session_state['db'].items():
                num = old_map.get(str(wid))
                if num in raw_list[:27]:
                    wd["streak_win"], wd["streak_loss"] = wd.get("streak_win",0)+1, 0
                    wd["score"] = wd.get("score",1000.0) - 2.7
                else:
                    wd["streak_loss"], wd["streak_win"] = wd.get("streak_loss",0)+1, 0
                    wd["score"] = wd.get("score",1000.0) + 1.0
            
            st.session_state['history'].insert(0, {"STT": len(st.session_state['history'])+1, "GĐB": gdb_now, "Chốt_6": "".join(t3+b3)})
            st.session_state['last_full_str'] = "".join(raw_list[:27])
            st.rerun()

# --- HIỂN THỊ KẾT QUẢ ---
if st.session_state['db'] and st.session_state['last_full_str']:
    # Hàm tính Rank chính thức
    def get_final_rank():
        mapping = get_mapping_v11(st.session_state['last_full_str'])
        res = []
        for i in range(100):
            num = f"{i:02d}"
            # Logic score tối giản để chạy nhanh
            wires = [wd for wid, wd in st.session_state['db'].items() if mapping.get(str(wid)) == num]
            score = sum([float(w['score']) for w in wires]) / max(1, len(wires))
            res.append({"Số": num, "Điểm": score})
        df = pd.DataFrame(res).sort_values("Điểm", ascending=False).reset_index(drop=True)
        df["Rank"] = df.index + 1
        return df

    df_rank = get_final_rank()
    top3, bot3 = get_hybrid_6_touches(df_rank)
    all_6 = sorted(list(set(top3 + bot3)))

    # Metrics
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("🔝 3 CHẠM MẠNH", ",".join(top3))
    m2.metric("📉 3 CHẠM YẾU", ",".join(bot3))
    m3.metric("🎯 TỔNG 6 CHẠM", "".join(all_6))

    # Lịch sử
    st.subheader("📜 ĐỐI SOÁT CHUẨN KỲ")
    if st.session_state['history']:
        df_h = pd.DataFrame(st.session_state['history'])
        def check_win(row):
            g = str(row['GĐB'])[-2:]
            c6 = str(row.get('Chốt_6', ""))
            return "A" if (any(d in g for d in c6) or (len(g)==2 and g[0]==g[1])) else "T"
        df_h['KQ'] = df_h.apply(check_win, axis=1)
        st.dataframe(df_h[['STT', 'GĐB', 'Chốt_6', 'KQ']].head(15), use_container_width=True)

    # Dàn 88 số
    all_digs = set("0123456789")
    remain_4 = all_digs - set(all_6)
    # Loại 4x3=12 con lệch của 4 chạm còn lại
    to_remove = [f"{d1}{d2}" for d1 in remain_4 for d2 in remain_4 if d1 != d2]
    dàn_88 = [s for s in df_rank["Số"].tolist() if s not in to_remove]
    
    st.success(f"💎 DÀN 88 SỐ CHIẾN THUẬT (Giữ 6 chạm: {','.join(all_6)} + 4 Kép còn lại)")
    st.code(", ".join(dàn_88))
