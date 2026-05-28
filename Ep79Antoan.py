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

# --- 2. LOGIC TÍNH RANK VÀ NHẶT 6 CHẠM (ÉP TÍNH MỚI) ---
def calculate_realtime_rank(db, last_full_str):
    # Đây là trái tim của việc nhảy số: Ánh xạ lại toàn bộ dựa trên chuỗi mới
    if not db or not last_full_str:
        return pd.DataFrame()
    
    mapping = get_mapping_v11(last_full_str)
    stats = {f"{i:02d}": 0.0 for i in range(100)}
    counts = {f"{i:02d}": 0 for i in range(100)}
    
    # CHỈ NHẶT DÂY ĐỨT (streak_win == 0)
    for wid, wd in db.items():
        if wd.get("streak_win", 0) == 0:
            num = mapping.get(str(wid))
            if num:
                stats[num] += float(wd.get('score', 1000.0))
                counts[num] += 1
                
    res = []
    for num in stats:
        avg_score = stats[num] / max(1, counts[num])
        res.append({"Số": num, "Điểm": avg_score})
        
    df = pd.DataFrame(res).sort_values("Điểm", ascending=False).reset_index(drop=True)
    df["Rank"] = df.index + 1
    return df

def get_hybrid_6_touches(df_rank):
    if df_rank.empty: return ["?"]*3, ["?"]*3
    
    # 3 Mạnh (Đầu Rank)
    top_digits = []
    for s in df_rank.sort_values("Rank")["Số"]:
        for char in str(s):
            if char not in top_digits: top_digits.append(char)
            if len(top_digits) == 3: break
        if len(top_digits) == 3: break
            
    # 3 Yêu (Cuối Rank)
    bot_digits = []
    for s in df_rank.sort_values("Rank", ascending=False)["Số"]:
        for char in str(s):
            if char not in bot_digits and char not in top_digits:
                bot_digits.append(char)
            if len(bot_digits) == 3: break
        if len(bot_digits) == 3: break
            
    return sorted(top_digits), sorted(bot_digits)

# --- 3. GIAO DIỆN ---
st.set_page_config(layout="wide", page_title="Matrix V14.0 Stable")
st.title("🛡️ Matrix V14.0 - Total Reset (Nhảy số tuyệt đối)")

for key in ['db', 'history', 'last_full_str', 'raw_input', 'gdb_now']:
    if key not in st.session_state:
        st.session_state[key] = {} if key == 'db' else ([] if key == 'history' else "")

with st.sidebar:
    st.header("📂 1. DỮ LIỆU")
    up_json = st.file_uploader("Nạp file .json", type=['json'])
    if up_json and st.button("XÁC NHẬN NẠP"):
        data = json.load(up_json)
        st.session_state.update({'db': data.get('matrix', {}), 'history': data.get('history', []), 'last_full_str': data.get('last_full_str', "")})
        st.rerun()

    st.header("📸 2. QUÉT ẢNH")
    up_img = st.file_uploader("Upload ảnh", type=['jpg','png','jpeg'])
    if up_img and st.button("🚀 CHẠY OCR"):
        res = load_ocr().readtext(np.array(Image.open(up_img)), detail=0)
        nums = [re.sub(r'\D','',n) for n in res if len(re.sub(r'\D','',n))>=2]
        if nums:
            st.session_state['raw_input'] = ",".join(nums)
            st.session_state['gdb_now'] = nums[-1][-2:] # Lấy 2 số cuối của phần tử cuối cùng (thường là GĐB)

    raw_in = st.text_area("27 giải:", value=st.session_state['raw_input'], height=100)
    gdb_now = st.text_input("GĐB:", value=st.session_state['gdb_now'])

    if st.button("🔥 PHÂN TÍCH & LƯU KỲ MỚI", type="primary", use_container_width=True):
        raw_list = [x.strip()[-2:] for x in raw_in.replace(","," ").split() if len(x.strip())>=2]
        if len(raw_list) >= 27 and gdb_now and st.session_state['db']:
            # BƯỚC 1: Lấy chạm đang chốt của kỳ vừa đánh
            df_old = calculate_realtime_rank(st.session_state['db'], st.session_state['last_full_str'])
            t3, b3 = get_hybrid_6_touches(df_old)
            
            # BƯỚC 2: Cập nhật DB (Cực kỳ quan trọng)
            old_mapping = get_mapping_v11(st.session_state['last_full_str'])
            for wid, wd in st.session_state['db'].items():
                num = old_mapping.get(str(wid))
                if num in raw_list[:27]:
                    wd["score"] = wd.get("score", 1000.0) - 2.7
                    wd["streak_win"] = wd.get("streak_win", 0) + 1
                else:
                    wd["score"] = wd.get("score", 1000.0) + 1.0
                    wd["streak_win"] = 0

            # BƯỚC 3: Lưu lịch sử và ĐỔI CHUỖI 107 VỊ TRÍ
            st.session_state['history'].insert(0, {"STT": len(st.session_state['history']) + 1, "GĐB": gdb_now, "Chốt_6": "".join(t3 + b3)})
            st.session_state['last_full_str'] = "".join(raw_list[:27])
            st.rerun()

# --- 4. HIỂN THỊ KẾT QUẢ ---
if st.session_state['db'] and st.session_state['last_full_str']:
    # ÉP BUỘC TÍNH LẠI RANK THEO DỮ LIỆU MỚI
    df_rank = calculate_realtime_rank(st.session_state['db'], st.session_state['last_full_str'])
    top3, bot3 = get_hybrid_6_touches(df_rank)
    all_6 = sorted(list(set(top3 + bot3)))

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("🔝 3 MẠNH", ",".join(top3))
    c2.metric("📉 3 YẾU", ",".join(bot3))
    c3.metric("🎯 TỔNG 6 CHẠM KỲ TỚI", "".join(all_6))

    # Lịch sử đối soát
    st.subheader("📜 ĐỐI SOÁT CHUẨN KỲ")
    if st.session_state['history']:
        df_h = pd.DataFrame(st.session_state['history'])
        def check_res(row):
            g = str(row['GĐB'])[-2:]; c6 = str(row.get('Chốt_6', ""))
            if not c6: return "-"
            return "A" if (any(d in g for d in c6) or (len(g)==2 and g[0]==g[1])) else "T"
        df_h['KQ'] = df_h.apply(check_res, axis=1)
        st.dataframe(df_h.reindex(columns=['STT', 'GĐB', 'Chốt_6', 'KQ']).head(15), use_container_width=True)

    # Dàn 88 số
    high_4 = set("0123456789") - set(all_6)
    to_remove = [f"{d1}{d2}" for d1 in high_4 for d2 in high_4 if d1 != d2]
    dàn_88 = [s for s in df_rank["Số"].tolist() if s not in to_remove]
    st.success(f"💎 DÀN 88 SỐ CHIẾN THUẬT (Dựa trên bộ chạm {','.join(all_6)})")
    st.code(", ".join(dàn_88))
