import streamlit as st
import pandas as pd
import json
import numpy as np
import easyocr
import re
from PIL import Image
from collections import Counter

# --- 1. CẤU HÌNH OCR & MAPPING ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'])

def get_mapping_v11(full_str, total_pos=107):
    if not full_str or len(full_str) < total_pos:
        return {str(i): f"{i % 100:02d}" for i in range(11449)}
    return {str(i * total_pos + j): f"{full_str[i]}{full_str[j]}" for i in range(total_pos) for j in range(total_pos)}

# --- 2. LOGIC TÍNH RANK VÀ NHẶT CHẠM (ÉP TÍNH MỚI MỖI KỲ) ---
def get_hybrid_6_touches(df_rank):
    if df_rank.empty: return ["?"]*3, ["?"]*3
    
    # 3 Mạnh (Từ đỉnh Rank xuống)
    top_digits = []
    df_top = df_rank.sort_values("Rank", ascending=True)
    for s in df_top["Số"]:
        for char in str(s):
            if char not in top_digits: top_digits.append(char)
            if len(top_digits) == 3: break
        if len(top_digits) == 3: break
            
    # 3 Yếu (Từ đáy Rank lên)
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
st.set_page_config(layout="wide", page_title="Matrix V13.96 Stable")
st.title("🛡️ Matrix V13.96 - Zero-Latency Rhythm (6-Touch)")

# Khởi tạo Session State
for key in ['db', 'history', 'last_full_str', 'raw_input', 'gdb_now']:
    if key not in st.session_state:
        st.session_state[key] = {} if key == 'db' else ([] if key == 'history' else "")

# --- SIDEBAR: XỬ LÝ DỮ LIỆU ---
with st.sidebar:
    st.header("📂 1. DỮ LIỆU GỐC")
    up_json = st.file_uploader("Nạp file .json", type=['json'])
    if up_json and st.button("XÁC NHẬN NẠP"):
        data = json.load(up_json)
        st.session_state.update({
            'db': data.get('matrix', {}),
            'history': data.get('history', []),
            'last_full_str': data.get('last_full_str', "")
        })
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

    if st.button("🔥 PHÂN TÍCH & LƯU KỲ MỚI", type="primary", use_container_width=True):
        raw_list = [x.strip()[-2:] for x in raw_in.replace(","," ").split() if len(x.strip())>=2]
        if len(raw_list) >= 27 and gdb_now and st.session_state['db']:
            # BƯỚC 1: Lấy bảng Rank HIỆN TẠI để chốt 6 chạm cho kỳ vừa quay
            mapping_now = get_mapping_v11(st.session_state['last_full_str'])
            stats_now = {f"{i:02d}": 0.0 for i in range(100)}
            for wid, wd in st.session_state['db'].items():
                num = mapping_now.get(str(wid))
                if num: stats_now[num] += float(wd.get('score', 1000.0))
            
            df_now = pd.DataFrame([{"Số": k, "Điểm": v} for k, v in stats_now.items()]).sort_values("Điểm", ascending=False).reset_index(drop=True)
            df_now["Rank"] = df_now.index + 1
            t3, b3 = get_hybrid_6_touches(df_now)
            
            # BƯỚC 2: Cập nhật Score cho Ma trận
            for wid, wd in st.session_state['db'].items():
                num = mapping_now.get(str(wid))
                if num in raw_list[:27]:
                    wd["score"] = wd.get("score", 1000.0) - 2.7
                else:
                    wd["score"] = wd.get("score", 1000.0) + 1.0
            
            # BƯỚC 3: Lưu lịch sử và cập nhật chuỗi 107 vị trí mới
            st.session_state['history'].insert(0, {
                "STT": len(st.session_state['history']) + 1,
                "GĐB": gdb_now,
                "Chốt_6": "".join(t3 + b3)
            })
            st.session_state['last_full_str'] = "".join(raw_list[:27])
            st.rerun()

# --- 4. HIỂN THỊ KẾT QUẢ (THỰC THI MỖI LẦN RERUN) ---
if st.session_state['db'] and st.session_state['last_full_str']:
    # TÍNH RANK MỚI NGAY LẬP TỨC
    mapping_latest = get_mapping_v11(st.session_state['last_full_str'])
    stats_latest = {f"{i:02d}": 0.0 for i in range(100)}
    for wid, wd in st.session_state['db'].items():
        num = mapping_latest.get(str(wid))
        if num: stats_latest[num] += float(wd.get('score', 1000.0))
    
    df_rank = pd.DataFrame([{"Số": k, "Điểm": v} for k, v in stats_latest.items()]).sort_values("Điểm", ascending=False).reset_index(drop=True)
    df_rank["Rank"] = df_rank.index + 1
    
    t3_next, b3_next = get_hybrid_6_touches(df_rank)
    all_6_next = sorted(list(set(t3_next + b3_next)))

    # Metrics cho kỳ tới
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("🔝 3 MẠNH (Ngày mai)", ",".join(t3_next))
    m2.metric("📉 3 YẾU (Ngày mai)", ",".join(b3_next))
    m3.metric("🎯 BỘ 6 CHẠM", "".join(all_6_next))

    # Lịch sử đối soát
    st.subheader("📜 ĐỐI SOÁT CHUẨN KỲ")
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
        st.dataframe(df_h.reindex(columns=['STT', 'GĐB', 'Chốt_6', 'KQ']).head(15), use_container_width=True)

    # Dàn 88 số
    high_4 = set("0123456789") - set(all_6_next)
    to_remove = [f"{d1}{d2}" for d1 in high_4 for d2 in high_4 if d1 != d2]
    dàn_88 = [s for s in df_rank["Số"].tolist() if s not in to_remove]
    
    st.success(f"💎 DÀN 88 SỐ CHO KỲ TỚI (Bao phủ 6 chạm: {','.join(all_6_next)})")
    st.code(", ".join(dàn_88))
