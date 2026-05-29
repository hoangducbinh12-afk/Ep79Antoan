import streamlit as st
import pandas as pd
import json
import numpy as np
import easyocr
import re
from PIL import Image

# --- 1. SETTINGS & OCR ---
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
            hist = w_data.get("hit_history", [0]*20)
            hist.append(1); w_data["hit_history"] = hist[-20:]
        else:
            w_data["streak_loss"] = w_data.get("streak_loss", 0) + 1
            w_data["streak_win"] = 0
            w_data["score"] = w_data.get("score", 1000.0) + 1.0
            hist = w_data.get("hit_history", [0]*20)
            hist.append(0); w_data["hit_history"] = hist[-20:]

def get_wire_lineage_v2(db, history, mapping, n_top_bet):
    if not history or not db or n_top_bet == 0: return set()
    try:
        last_gdb_raw = str(history[0].get('GĐB', "")).split()[0]
        last_gdb = f"{int(re.sub(r'\D', '', last_gdb_raw)[-2:]):02d}"
        parent_wires = [w_id for w_id, d in db.items() if mapping.get(w_id) == last_gdb and d.get('streak_win', 0) > 0]
        if not parent_wires: return set()
        wire_scores = {}
        for w_id in parent_wires:
            hit_hist = db[w_id].get('hit_history', [])
            for other_id, other_data in db.items():
                other_hist = other_data.get('hit_history', [])
                for t in range(len(hit_hist)-1):
                    if hit_hist[t] == 1 and other_hist[t+1] == 1:
                        wire_scores[other_id] = wire_scores.get(other_id, 0) + 1
        top_wires = sorted(wire_scores.items(), key=lambda x: x[1], reverse=True)[:n_top_bet]
        return {f"{int(mapping.get(w_id)):02d}" for w_id, score in top_wires if mapping.get(w_id)}
    except: return set()

def get_hybrid_6_touches(df_rank):
    if df_rank.empty: return ["?"]*2, ["?"]*4
    top_digits, bot_digits = [], []
    for s in df_rank.sort_values("Rank")["Số"]:
        for char in str(s):
            if char not in top_digits: top_digits.append(char)
            if len(top_digits) == 2: break
        if len(top_digits) == 2: break
    for s in df_rank.sort_values("Rank", ascending=False)["Số"]:
        for char in str(s):
            if char not in bot_digits and char not in top_digits:
                bot_digits.append(char)
            if len(bot_digits) == 4: break
        if len(bot_digits) == 4: break
    return sorted(top_digits), sorted(bot_digits)

# --- 2. LOGIC LẤY DÀN & LOẠI (LÕI V13.9.2) ---
def thermal_ai_engines_v1392(df_raw, history, db, mapping, cfg):
    if df_raw is None or df_raw.empty: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), [], [], pd.DataFrame(), ([], []), set()
    
    # A. Tạo dàn gốc 88 (6 Chạm + Kép)
    t2, b4 = get_hybrid_6_touches(df_raw)
    digits_6 = set(t2 + b4)
    base_88 = {f"{i:02d}" for i in range(100) if any(d in f"{i:02d}" for d in digits_6) or (f"{i:02d}"[0] == f"{i:02d}"[1])}
    
    # B. Xác định lỗi Sát thủ
    set_bet = get_wire_lineage_v2(db, history, mapping, cfg['bet'])
    bottom_wires = sorted(db.items(), key=lambda x: x[1]['score'])[:cfg['bot']]
    set_bottom = {f"{int(mapping.get(str(w_id))):02d}" for w_id, d in bottom_wires if mapping.get(str(w_id))}
    set_overlap = set_bottom.intersection(set_bet)
    remain_4 = set("0123456789") - digits_6
    kép_phế = {f"{d}{d}" for d in remain_4}

    def get_penalty(row):
        p = 0
        if row['Tang'] == 0: p += 1 # a
        if row['Cứng'] < 8.0: p += 1 # b
        if row['An'] == 0: p += 1 # c
        if row['Số'] in set_overlap: p += 1 # d
        if row['Số'] in kép_phế: p += 1 # e
        return p

    df_raw['penalty'] = df_raw.apply(get_penalty, axis=1)
    df_raw['has_shield'] = (((df_raw['Tang'] == 0) & (df_raw['Rank'] <= 15)) | ((df_raw['An'] >= 5) & (df_raw['Số'].isin(set_bet)))).astype(int)
    df_raw['is_in_88'] = df_raw['Số'].apply(lambda x: 1 if x in base_88 else 0)

    # C. Hạ dàn 79 & 59 (Có Shield)
    df_raw['safety_score_79'] = (df_raw['is_in_88'] * 500) + (df_raw['has_shield'] * 100) - (df_raw['penalty'] * 60)
    ds_79 = df_raw.sort_values(by=['safety_score_79', 'Điểm'], ascending=[False, False]).head(79)
    da_59 = ds_79.sort_values(by=['safety_score_79', 'Điểm'], ascending=[False, False]).head(59)

    # D. Hạ dàn 39 (Ưu tiên Vùng xanh A23-T1, Bỏ Shield)
    da_59['vung_xanh'] = ((da_59['An'].isin([2, 3])) & (da_59['Tang'] == 1)).astype(int)
    dk_39 = da_59.sort_values(by=['vung_xanh', 'Điểm'], ascending=[False, False]).head(39)
    
    return dk_39, da_59, ds_79, sorted(list(set_bottom)), sorted(list(set_bet)), df_raw, (t2, b4), base_88

# --- 3. UI (GIỮ NGUYÊN HIỂN THỊ BẢN CŨ) ---
st.set_page_config(layout="wide", page_title="Matrix Hybrid V13.9.2")
st.title("🛡️ Matrix V13.9.2 - Hybrid Shield (88-Base)")

if 'cfg' not in st.session_state: st.session_state['cfg'] = {"tier": 68, "win": 10, "hard": 7.99, "bot": 40, "bet": 40}
if 'db' not in st.session_state: st.session_state['db'] = {}
if 'history' not in st.session_state: st.session_state['history'] = []
if 'last_full_str' not in st.session_state: st.session_state['last_full_str'] = ""
if 'prev_sets' not in st.session_state: st.session_state['prev_sets'] = {}

with st.sidebar:
    if st.button("🚨 RESET ALL", use_container_width=True): st.session_state.clear(); st.rerun()
    st.header("📂 1. DỮ LIỆU")
    up_json = st.file_uploader("Nạp JSON", type=['json'])
    if up_json and st.button("XÁC NHẬN NẠP"):
        data = json.load(up_json)
        st.session_state['db'], st.session_state['history'], st.session_state['last_full_str'] = data.get('matrix', data), data.get('history', []), data.get('last_full_str', "")
        st.rerun()

    st.header("📸 2. QUÉT KQ")
    up_img = st.file_uploader("Ảnh KQ", type=['jpg', 'png', 'jpeg'])
    if up_img and st.button("🚀 CHẠY OCR"):
        res_ocr = load_ocr().readtext(np.array(Image.open(up_img)), detail=0)
        nums = [n for n in res_ocr if n.isdigit() and 2 <= len(n) <= 5]
        if nums: 
            st.session_state['raw_input'], st.session_state['gdb_val'] = ", ".join(nums), nums[0][-2:]
            st.rerun()

    st.divider()
    if st.button("🔥 PHÂN TÍCH & LƯU", type="primary", use_container_width=True):
        raw_val, gdb_val = st.session_state.get('raw_input', ""), st.session_state.get('gdb_val', "")
        raw_list = [x.strip() for x in raw_val.replace(",", " ").split() if x]
        if len(raw_list) >= 27 and gdb_val and st.session_state['db']:
            mapping = get_mapping_v11(st.session_state['last_full_str'])
            gdb_num = f"{int(re.sub(r'\D', '', gdb_val)[-2:]):02d}"
            p = st.session_state.get('prev_sets', {})
            check = lambda d: "A" if gdb_num in (d or []) else "T"
            
            c6 = p.get('c6_str', "")
            is_hit_6 = any(d in gdb_num for d in c6) or (gdb_num[0] == gdb_num[1])
            res_6t = "A" if is_hit_6 else "T"

            st.session_state['history'].insert(0, {
                "STT": len(st.session_state['history']) + 1, "GĐB": gdb_val,
                "Dan39": check(p.get('d39')), "Dan59": check(p.get('d59')), "Dan79": check(p.get('d79')),
                "88-Base": res_6t
            })
            update_matrix_state(st.session_state['db'], [n[-2:] for n in raw_list[:27]], mapping)
            st.session_state['last_full_str'] = "".join(raw_list[:27]); st.rerun()

    st.header("📝 3. INPUT")
    st.session_state['raw_input'] = st.text_area("Loto:", value=st.session_state.get('raw_input', ""), height=80)
    st.session_state['gdb_val'] = st.text_input("GĐB:", value=st.session_state.get('gdb_val', ""))
    
    st.header("⚙️ 4. BỘ LỌC")
    st.session_state['cfg']['tier'] = st.slider("Tầng (%):", 50, 80, 68)
    st.session_state['cfg']['win'] = st.slider("Kỳ:", 5, 20, 10)
    st.session_state['cfg']['bot'] = st.slider("Đáy:", 0, 100, 40)
    st.session_state['cfg']['bet'] = st.slider("Bệt:", 0, 100, 40)

# --- 4. HIỂN THỊ (TRẢ LẠI GIAO DIỆN BẢN CŨ) ---
if st.session_state['last_full_str']:
    def get_matrix_df(t_val, w_val):
        db, mapping = st.session_state['db'], get_mapping_v11(st.session_state['last_full_str'])
        stats = {f"{i:02d}": {"total_score": 0.0, "max_an": 0, "clean_wire_count": 0, "hits": 0, "losses": []} for i in range(100)}
        for w_id, w_d in db.items():
            num = mapping.get(str(w_id))
            if num:
                s = stats[num]; sw, sl = int(w_d.get("streak_win", 0)), int(w_d.get("streak_loss", 0))
                s["losses"].append(sl if sw == 0 else 0); s["max_an"] = max(s["max_an"], sw)
                s["hits"] += sum(w_d.get("hit_history", [])[-w_val:])
                if sw == 0: s["clean_wire_count"] += 1; s["total_score"] += float(w_d.get("score", 1000.0))
        res = []
        for num, s in stats.items():
            dc = max(1, s["clean_wire_count"]); hard = round((s["hits"] / (w_val * (11449/100))) * 100, 2)
            score = round((s["total_score"] / dc) * (1 + hard/100), 2)
            res.append({"Số": num, "Điểm": score, "Tang": calculate_tier(s["losses"], t_val), "An": s["max_an"], "Cứng": hard})
        df = pd.DataFrame(res).sort_values("Điểm", ascending=False).reset_index(drop=True); df["Rank"] = df.index + 1; return df

    df_raw_val = get_matrix_df(st.session_state['cfg']['tier'], st.session_state['cfg']['win'])
    dk, da, ds, d_thap, d_cao, df_full, (t2, b4), b88 = thermal_ai_engines_v1392(df_raw_val, st.session_state['history'], st.session_state['db'], get_mapping_v11(st.session_state['last_full_str']), st.session_state['cfg'])
    
    st.session_state['prev_sets'] = {'d39': dk["Số"].tolist(), 'd59': da["Số"].tolist(), 'd79': ds["Số"].tolist(), 'c6_str': "".join(t2 + b4)}

    # METRIC TRÊN ĐẦU
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("🔝 2 CHẠM MẠNH", ",".join(t2))
    m2.metric("📉 4 CHẠM YẾU", ",".join(b4))
    m3.info("Hybrid V13.9.2: Gốc 88s + Gọt tỉa Sát thủ")

    c1, c2, c3 = st.columns(3)
    c1.success(f"🎯 Kết 39 (Vùng Xanh)"); c1.code(", ".join(dk["Số"].tolist()))
    c2.info(f"🤖 AI 59 (Shield)"); c2.code(", ".join(da["Số"].tolist()))
    c3.warning(f"🛡️ Safe 79 (88-Base)"); c3.code(", ".join(ds["Số"].tolist()))

    st.divider()
    t_hist, t_rank = st.tabs(["📜 LỊCH SỬ ĂN/TRƯỢT", "📊 CHI TIẾT RANK"])
    with t_hist:
        if st.session_state['history']:
            df_hist = pd.DataFrame(st.session_state['history'])
            # Trả lại các cột lịch sử cũ nhưng có thêm cột 88-Base để mày soi 6 chạm
            cols = ["STT", "GĐB", "Dan39", "Dan59", "Dan79", "88-Base"]
            st.dataframe(df_hist.reindex(columns=cols), use_container_width=True, hide_index=True)
    with t_rank:
        st.dataframe(df_full.sort_values(by=['safety_score_79', 'Điểm'], ascending=[False, False]), use_container_width=True)

    st.download_button("💾 LƯU JSON", data=json.dumps({"matrix": st.session_state['db'], "history": st.session_state['history'], "last_full_str": st.session_state['last_full_str']}, ensure_ascii=False), file_name="matrix_full_v1392.json", use_container_width=True)
