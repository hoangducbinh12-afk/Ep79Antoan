import streamlit as st
import pandas as pd
import json
import numpy as np
import easyocr
import re
from PIL import Image
from collections import Counter
import io

# --- 1. CẤU HÌNH HỆ THỐNG & OCR ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'])

def get_mapping_v11(full_str, total_pos=107):
    if not full_str or len(full_str) < total_pos:
        return {str(i): f"{i % 100:02d}" for i in range(11449)}
    return {str(i * total_pos + j): f"{full_str[i]}{full_str[j]}" for i in range(total_pos) for j in range(total_pos)}

# --- 2. LOGIC NHẶT 6 CHẠM (4 YẾU + 2 MẠNH) ---
def get_hybrid_6_touches_v143(df_rank):
    if df_rank.empty: return ["?"]*2, ["?"]*4
    
    # Nhặt 4 chạm Yếu nhất (Từ đáy Rank 100 ngược lên)
    bot_digits = []
    df_bot = df_rank.sort_values("Rank", ascending=False)
    for s in df_bot["Số"]:
        for char in str(s):
            if char not in bot_digits: bot_digits.append(char)
            if len(bot_digits) == 4: break
        if len(bot_digits) == 4: break
            
    # Nhặt 2 chạm Mạnh nhất (Từ đỉnh Rank 1 xuống)
    top_digits = []
    df_top = df_rank.sort_values("Rank", ascending=True)
    for s in df_top["Số"]:
        for char in str(s):
            # Không lấy trùng với 4 chạm yếu đã nhặt
            if char not in top_digits and char not in bot_digits:
                top_digits.append(char)
            if len(top_digits) == 2: break
        if len(top_digits) == 2: break
            
    return sorted(top_digits), sorted(bot_digits)

# --- 3. LOGIC TÍNH RANK REALTIME ---
def calculate_realtime_rank(db, last_full_str):
    if not db or not last_full_str:
        return pd.DataFrame(columns=["Số", "Điểm", "Rank"])
    mapping = get_mapping_v11(last_full_str)
    stats = {f"{i:02d}": 0.0 for i in range(100)}
    counts = {f"{i:02d}": 0 for i in range(100)}
    for wid, wd in db.items():
        if wd.get("streak_win", 0) == 0: # Chỉ lấy dây đang đứt
            num = mapping.get(str(wid))
            if num:
                stats[num] += float(wd.get('score', 1000.0))
                counts[num] += 1
    res = [{"Số": num, "Điểm": stats[num]/max(1, counts[num])} for num in stats]
    df = pd.DataFrame(res).sort_values("Điểm", ascending=False).reset_index(drop=True)
    df["Rank"] = df.index + 1
    return df

# --- 4. GIAO DIỆN ---
st.set_page_config(layout="wide", page_title="Matrix V14.3 Pro")
st.title("🛡️ Matrix V14.3 - Deep Bottom (4 Yếu + 2 Mạnh)")

for key in ['db', 'history', 'last_full_str', 'raw_input', 'gdb_now']:
    if key not in st.session_state:
        st.session_state[key] = {} if key == 'db' else ([] if key == 'history' else "")

with st.sidebar:
    st.header("📂 1. QUẢN LÝ FILE")
    up_json = st.file_uploader("Nạp file .json", type=['json'])
    if up_json and st.button("XÁC NHẬN NẠP"):
        data = json.load(up_json)
        st.session_state.update({'db': data.get('matrix', {}), 'history': data.get('history', []), 'last_full_str': data.get('last_full_str', "")})
        st.rerun()

    if st.session_state['db']:
        st.divider()
        full_data = {"matrix": st.session_state['db'], "history": st.session_state['history'], "last_full_str": st.session_state['last_full_str']}
        st.download_button("💾 XUẤT JSON", json.dumps(full_data, ensure_ascii=False), file_name="matrix_v143.json", mime="application/json", use_container_width=True)

    st.header("📸 2. QUÉT ẢNH KQ")
    up_img = st.file_uploader("Upload ảnh", type=['jpg','png','jpeg'])
    if up_img and st.button("🚀 CHẠY OCR SCAN"):
        res = load_ocr().readtext(np.array(Image.open(up_img)), detail=0)
        nums = [re.sub(r'\D','',n) for n in res if len(re.sub(r'\D','',n))>=2]
        if nums:
            st.session_state['raw_input'] = ",".join(nums)
            st.session_state['gdb_now'] = nums[0][-2:]

    st.header("📝 3. NHẬP KQ")
    raw_in = st.text_area("27 giải:", value=st.session_state['raw_input'], height=100)
    gdb_now = st.text_input("GĐB (2 số cuối):", value=st.session_state['gdb_now'])

    if st.button("🔥 LƯU & PHÂN TÍCH", type="primary", use_container_width=True):
        raw_list = [x.strip()[-2:] for x in raw_in.replace(","," ").split() if len(x.strip())>=2]
        if len(raw_list) >= 27 and gdb_now and st.session_state['db']:
            # Lấy chạm cũ 4 yếu 2 mạnh để đối soát
            df_old = calculate_realtime_rank(st.session_state['db'], st.session_state['last_full_str'])
            t2, b4 = get_hybrid_6_touches_v143(df_old)
            
            old_map = get_mapping_v11(st.session_state['last_full_str'])
            for wid, wd in st.session_state['db'].items():
                num = old_map.get(str(wid))
                if num in raw_list[:27]:
                    wd["score"] = wd.get("score", 1000.0) - 2.7
                    wd["streak_win"] = wd.get("streak_win", 0) + 1
                else:
                    wd["score"] = wd.get("score", 1000.0) + 1.0
                    wd["streak_win"] = 0
            
            st.session_state['history'].insert(0, {"STT": len(st.session_state['history']) + 1, "GĐB": gdb_now, "Chốt_6": "".join(t2 + b4)})
            st.session_state['last_full_str'] = "".join(raw_list[:27])
            st.rerun()

# --- 4. HIỂN THỊ KẾT QUẢ ---
if st.session_state['db'] and st.session_state['last_full_str']:
    df_rank = calculate_realtime_rank(st.session_state['db'], st.session_state['last_full_str'])
    top2, bot4 = get_hybrid_6_touches_v143(df_rank)
    all_6 = sorted(list(set(top2 + bot4)))

    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("🔝 2 CHẠM MẠNH", ",".join(top2))
    m2.metric("📉 4 CHẠM YẾU", ",".join(bot4))
    m3.metric("🎯 TỔNG 6 CHẠM KỲ TỚI", "".join(all_6))

    st.subheader("📜 ĐỐI SOÁT LỊCH SỬ")
    if st.session_state['history']:
        df_h = pd.DataFrame(st.session_state['history'])
        def check_at(row):
            g = str(row['GĐB'])[-2:]; c6 = str(row.get('Chốt_6', ""))
            if not c6: return "-"
            return "A" if (any(d in g for d in c6) or (len(g)==2 and g[0]==g[1])) else "T"
        df_h['Kết quả'] = df_h.apply(check_at, axis=1)
        st.dataframe(df_h.reindex(columns=['STT', 'GĐB', 'Chốt_6', 'Kết quả']).head(15), use_container_width=True)

    # Dàn 88 số
    high_4 = set("0123456789") - set(all_6)
    to_remove = [f"{d1}{d2}" for d1 in high_4 for d2 in high_4 if d1 != d2]
    dàn_88 = [s for s in df_rank["Số"].tolist() if s not in to_remove]
    
    st.success(f"💎 DÀN 88 SỐ (Tập trung vùng đáy: {','.join(bot4)} + 2 Mạnh: {','.join(top2)})")
    st.code(", ".join(dàn_88))
