import streamlit as st
import pandas as pd
import json
import numpy as np
import easyocr
import re
from PIL import Image
import io

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

# --- 2. LOGIC NHẶT 6 CHẠM BỔ TRỢ (2 MẠNH + 4 YẾU) ---
def get_hybrid_6_touches(df_rank):
    if df_rank.empty: return ["?"]*2, ["?"]*4
    top_digits, bot_digits = [], []
    # 2 Mạnh
    for s in df_rank.sort_values("Rank")["Số"]:
        for char in str(s):
            if char not in top_digits: top_digits.append(char)
            if len(top_digits) == 2: break
        if len(top_digits) == 2: break
    # 4 Yếu
    for s in df_rank.sort_values("Rank", ascending=False)["Số"]:
        for char in str(s):
            if char not in bot_digits and char not in top_digits:
                bot_digits.append(char)
            if len(bot_digits) == 4: break
        if len(bot_digits) == 4: break
    return sorted(top_digits), sorted(bot_digits)

# --- 3. BỘ NÃO HẠ DÀN HYBRID V13.8 ---
def thermal_ai_engines_v138(df_raw, history, db, mapping, cfg):
    if df_raw is None or df_raw.empty: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), [], [], pd.DataFrame(), ([], [])
    
    # 6 Chạm bổ trợ xét loại
    t2, b4 = get_hybrid_6_touches(df_raw)
    all_6 = set(t2 + b4)
    remain_4 = set("0123456789") - all_6
    vùng_lệch_phế = [f"{d1}{d2}" for d1 in remain_4 for d2 in remain_4 if d1 != d2]
    vùng_kép_phế = [f"{d1}{d1}" for d1 in remain_4]

    set_bottom = set()
    if cfg['bot'] > 0:
        bottom_wires = sorted(db.items(), key=lambda x: x[1]['score'])[:cfg['bot']]
        set_bottom = {f"{int(mapping.get(str(w_id))):02d}" for w_id, d in bottom_wires if mapping.get(str(w_id))}
    set_bet = get_wire_lineage_v2(db, history, mapping, cfg['bet'])
    set_overlap = set_bottom.intersection(set_bet)
    
    # Định nghĩa Lõi (Core)
    df_raw['core_79'] = ((df_raw['Tang'].isin([0, 1, 2, 3])) & (df_raw['An'].isin([1, 2, 3, 4, 5])) & (df_raw['Cứng'] > 7.0)).astype(int)
    df_raw['shield_T0'] = ((df_raw['Tang'] == 0) & (df_raw['Rank'] <= 10)).astype(int)
    df_raw['shield_A5'] = ((df_raw['An'] >= 5) & (df_raw['Số'].isin(set_bet))).astype(int)
    df_raw['has_shield'] = ((df_raw['shield_T0'] == 1) | (df_raw['shield_A5'] == 1)).astype(int)

    # Điểm phạt xét loại bổ trợ (6 chạm)
    def get_touch_penalty(s):
        if s in vùng_lệch_phế: return -30 # Lệch không thuộc 6 chạm
        if s in vùng_kép_phế: return -15  # Kép không thuộc 6 chạm
        return 0
    
    df_raw['touch_penalty'] = df_raw['Số'].apply(get_touch_penalty)
    df_raw['overlap_penalty'] = (df_raw['Số'].isin(set_overlap).astype(int) * (1 - df_raw['has_shield']) * -50)
    
    # Safety Score 79 tổng lực
    df_raw['safety_score_79'] = (
        (df_raw['has_shield'] * 200) + 
        (df_raw['core_79'] * 100) + 
        (df_raw['Số'].isin(set_bet).astype(int) * 10) + 
        df_raw['touch_penalty'] + 
        df_raw['overlap_penalty']
    )
    
    ds_79 = df_raw.sort_values(by=['safety_score_79', 'Điểm'], ascending=[False, False]).head(79)
    da_59 = ds_79.sort_values(by=['Điểm'], ascending=False).head(59)
    dk_39 = da_59.sort_values(by=['Tang', 'An', 'Điểm'], ascending=[True, False, False]).head(39)
    
    return dk_39, da_59, ds_79, sorted(list(set_bottom)), sorted(list(set_bet)), df_raw, (t2, b4)

# --- 4. GIAO DIỆN CHÍNH ---
st.set_page_config(layout="wide", page_title="Matrix Shield Gold Hybrid")
st.title("🛡️ Matrix V13.8 - Hybrid Risk Shield Gold")

# Khởi tạo Session
if 'cfg' not in st.session_state: st.session_state['cfg'] = {"tier": 68, "win": 10, "hard": 7.99, "bot": 40, "bet": 40}
if 'db' not in st.session_state: st.session_state['db'] = {}
if 'history' not in st.session_state: st.session_state['history'] = []
if 'last_full_str' not in st.session_state: st.session_state['last_full_str'] = ""
if 'raw_input' not in st.session_state: st.session_state['raw_input'] = ""
if 'gdb_val' not in st.session_state: st.session_state['gdb_val'] = ""

with st.sidebar:
    if st.button("🚨 RESET ALL", use_container_width=True): st.session_state.clear(); st.rerun()
    st.header("📂 1. DỮ LIỆU")
    up_json = st.file_uploader("Nạp JSON", type=['json'])
    if up_json and st.button("XÁC NHẬN NẠP"):
        data = json.load(up_json)
        st.session_state.update({'db': data.get('matrix', data), 'history': data.get('history', []), 'last_full_str': data.get('last_full_str', "")})
        st.rerun()

    st.header("📸 2. QUÉT KQ")
    up_img = st.file_uploader("Ảnh KQ", type=['jpg', 'png', 'jpeg'])
    if up_img and st.button("🚀 CHẠY OCR"):
        res_ocr = load_ocr().readtext(np.array(Image.open(up_img)), detail=0)
        nums = [n for n in res_ocr if n.isdigit() and 2 <= len(n) <= 5]
        if nums: 
            st.session_state['raw_input'] = ", ".join(nums)
            st.session_state['gdb_val'] = nums[0][-2:]
            st.rerun()

    st.divider()
    if st.button("🔥 PHÂN TÍCH & LƯU", type="primary", use_container_width=True):
        raw_list = [x.strip() for x in st.session_state['raw_input'].replace(",", " ").split() if x]
        if len(raw_list) >= 27 and st.session_state['gdb_val'] and st.session_state['db']:
            mapping = get_mapping_v11(st.session_state['last_full_str'])
            # Lưu lịch sử kèm theo bộ 6 chạm đang dùng tại thời điểm đó
            st.session_state['history'].insert(0, {
                "STT": len(st.session_state['history']) + 1, 
                "GĐB": st.session_state['gdb_val'],
                "6-Touch": st.session_state.get('current_6t', "")
            })
            update_matrix_state(st.session_state['db'], [n[-2:] for n in raw_list[:27]], mapping)
            st.session_state['last_full_str'] = "".join(raw_list[:27])
            st.rerun()

    st.header("📝 3. INPUT")
    st.session_state['raw_input'] = st.text_area("Loto 27 giải:", value=st.session_state['raw_input'], height=80)
    st.session_state['gdb_val'] = st.text_input("GĐB:", value=st.session_state['gdb_val'])

    st.header("⚙️ 4. BỘ LỌC")
    st.session_state['cfg']['tier'] = st.slider("Tầng (%):", 50, 80, 68)
    st.session_state['cfg']['win'] = st.slider("Kỳ:", 5, 20, 10)
    st.session_state['cfg']['bot'] = st.slider("Đáy:", 0, 350, 40)
    st.session_state['cfg']['bet'] = st.slider("Bệt:", 0, 350, 40)

# --- 5. HIỂN THỊ BIẾN THIÊN ---
if st.session_state['last_full_str']:
    def get_matrix_df(t_val, w_val):
        db, mapping = st.session_state['db'], get_mapping_v11(st.session_state['last_full_str'])
        stats = {f"{i:02d}": {"total_score": 0.0, "max_an": 0, "clean_wire_count": 0, "clean_window_hits": 0, "all_losses": []} for i in range(100)}
        for w_id, w_d in db.items():
            num = mapping.get(str(w_id))
            if num:
                s = stats[num]; sw, sl = int(w_d.get("streak_win", 0)), int(w_d.get("streak_loss", 0))
                s["all_losses"].append(sl if sw == 0 else 0); s["max_an"] = max(s["max_an"], sw)
                s["clean_window_hits"] += sum(w_d.get("hit_history", [])[-w_val:])
                if sw == 0: s["clean_wire_count"] += 1; s["total_score"] += float(w_d.get("score", 1000.0))
        res = []
        for num, s in stats.items():
            dc = max(1, s["clean_wire_count"]); hard = round((s["clean_window_hits"] / (w_val * (11449/100))) * 100, 2)
            score = round((s["total_score"] / dc) * (1 + hard/100), 2)
            res.append({"Số": num, "Điểm": score, "Tang": calculate_tier(s["all_losses"], t_val), "An": s["max_an"], "Cứng": hard})
        df = pd.DataFrame(res).sort_values("Điểm", ascending=False).reset_index(drop=True); df["Rank"] = df.index + 1; return df

    df_raw_val = get_matrix_df(st.session_state['cfg']['tier'], st.session_state['cfg']['win'])
    dk, da, ds, d_thap, d_cao, df_full, (t2, b4) = thermal_ai_engines_v138(df_raw_val, st.session_state['history'], st.session_state['db'], get_mapping_v11(st.session_state['last_full_str']), st.session_state['cfg'])
    
    # Lưu 6 chạm hiện tại vào session để dùng khi bấm Lưu
    st.session_state['current_6t'] = "".join(t2 + b4)

    # --- KHU VỰC METRIC (MỚI) ---
    st.markdown("---")
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("🔝 2 CHẠM MẠNH", ",".join(t2))
    col_m2.metric("📉 4 CHẠM YẾU", ",".join(b4))
    col_m3.info(f"💡 Cơ chế: Phạt lệch phế -30, Phạt kép phế -15. Lõi được ưu tiên xét trước.")

    # --- HIỂN THỊ DÀN ---
    c1, c2, c3 = st.columns(3)
    c1.success(f"🎯 Kết 39 ({len(dk)})\nPhụ thuộc: Core + 6-Touch"); c1.code(", ".join(dk["Số"].tolist()))
    c2.info(f"🤖 AI 59 ({len(da)})\nNested in 79"); c2.code(", ".join(da["Số"].tolist()))
    c3.warning(f"🛡️ Safe 79 ({len(ds)})\nRisk Shield Gold (T0/A5)"); c3.code(", ".join(ds["Số"].tolist()))

    st.divider()
    tab_hist, tab_rank = st.tabs(["📜 ĐỐI SOÁT LỊCH SỬ", "📊 CHI TIẾT RANK & SHIELD"])
    
    with tab_hist:
        if st.session_state['history']:
            df_h = pd.DataFrame(st.session_state['history'])
            def check_6t_at(row):
                g = str(row.get('GĐB', ""))[-2:]; c6 = str(row.get('6-Touch', ""))
                if not c6: return "-"
                # Ăn nếu dính chạm hoặc là kép bằng (bất kỳ)
                is_hit = any(d in g for d in c6)
                is_kep = g[0] == g[1] if len(g)==2 else False
                return "A" if (is_hit or is_kep) else "T"
            
            df_h['KQ_Chạm'] = df_h.apply(check_6t_at, axis=1)
            # Hiển thị các cột lịch sử
            view_cols = ['STT', 'GĐB', '6-Touch', 'KQ_Chạm']
            st.dataframe(df_h.reindex(columns=view_cols).head(20), use_container_width=True, hide_index=True)

    with tab_rank:
        st.dataframe(df_full.sort_values(by=['safety_score_79', 'Điểm'], ascending=[False, False]), use_container_width=True)

    # --- NÚT LƯU DỮ LIỆU ---
    st.download_button("💾 XUẤT JSON CẬP NHẬT", data=json.dumps({"matrix": st.session_state['db'], "history": st.session_state['history'], "last_full_str": st.session_state['last_full_str']}, ensure_ascii=False), file_name="matrix_v138_final.json", use_container_width=True)
