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
    for s in df_rank.sort_values(by=["Rank", "Số"])["Số"]:
        for char in str(s):
            if char not in top_digits: top_digits.append(char)
            if len(top_digits) == 2: break
        if len(top_digits) == 2: break
    for s in df_rank.sort_values(by=["Rank", "Số"], ascending=[False, True])["Số"]:
        for char in str(s):
            if char not in bot_digits and char not in top_digits:
                bot_digits.append(char)
            if len(bot_digits) == 4: break
        if len(bot_digits) == 4: break
    return sorted(top_digits), sorted(bot_digits)

# --- 2. BỘ NÃO LỌC TẦNG V13.9.8 ---
def thermal_ai_engines_v1398(df_raw, history, db, mapping, cfg):
    if df_raw is None or df_raw.empty: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), [], [], pd.DataFrame(), ([], []), set()
    
    # BƯỚC 1: XÁC ĐỊNH DÀN GỐC 88
    t2, b4 = get_hybrid_6_touches(df_raw)
    digits_6 = set(t2 + b4)
    base_88 = {f"{i:02d}" for i in range(100) if any(d in f"{i:02d}" for d in digits_6) or (f"{i:02d}"[0] == f"{i:02d}"[1])}
    
    # BƯỚC 2: GỌT DÀN 88 XUỐNG 79 SỐ
    set_bet = get_wire_lineage_v2(db, history, mapping, cfg['bet'])
    bottom_wires = sorted(db.items(), key=lambda x: x[1]['score'])[:cfg['bot']]
    set_bottom = {f"{int(mapping.get(str(w_id))):02d}" for w_id, d in bottom_wires if mapping.get(str(w_id))}
    set_overlap_absolute = set_bottom.intersection(set_bet) # d. Trùng bệt & đáy
    
    remain_4 = set("0123456789") - digits_6
    kép_phế = {f"{d}{d}" for d in remain_4} # e. Kép phế

    def calculate_79_penalty(row):
        p = 0
        if row['Tang'] == 0: p += 1      # a. T=0
        if row['Cứng'] < 8.0: p += 1     # b. C < 8
        if row['An'] == 0: p += 1        # c. A = 0
        if row['Số'] in set_overlap_absolute: p += 1 # d
        if row['Số'] in kép_phế: p += 1  # e
        return p

    df_raw['penalty_79'] = df_raw.apply(calculate_79_penalty, axis=1)
    df_raw['is_in_88'] = df_raw['Số'].apply(lambda x: 1 if x in base_88 else 0)
    df_raw['has_shield'] = (((df_raw['Tang'] == 0) & (df_raw['Rank'] <= 15)) | ((df_raw['An'] >= 5) & (df_raw['Số'].isin(set_bet)))).astype(int)
    
    # Điểm hạ dàn 79 (Shield bảo vệ T0 & A5)
    df_raw['safety_79'] = (df_raw['is_in_88'] * 2000) + (df_raw['has_shield'] * 150) - (df_raw['penalty_79'] * 100)
    ds_79 = df_raw.sort_values(by=['safety_79', 'Điểm', 'Số'], ascending=[False, False, True]).head(79)

    # BƯỚC 3: LỌC DÀN 39 TỪ DÀN 79 (LOẠI TUYỆT ĐỐI)
    def evaluate_39_supreme(row):
        # Chỉ xét các số thuộc dàn 79
        s = row['Số']
        # a. Kép phế
        if s in kép_phế: return -10000
        # b. T=0,3 (Loại 100%), T=2 (Yếu)
        if row['Tang'] in [0, 3]: return -10000
        # c. A=0,5 (Loại 100%), A=1 (Yếu), A=4 (Yếu nhẹ)
        if row['An'] in [0, 5]: return -10000
        # d. C<9 (Loại 100%), C=9-12 (Yếu), C=13-16 (Yếu nhẹ)
        if row['Cứng'] < 9.0: return -10000
        # f. Trùng Đáy & Bệt (Loại 100%)
        if s in set_overlap_absolute: return -10000

        # Tầng tính điểm cho những con sống sót
        score_39 = 5000
        if row['Tang'] == 2: score_39 -= 1000
        if row['An'] == 1: score_39 -= 800
        if row['An'] == 4: score_39 -= 400
        c = row['Cứng']
        if 9.0 <= c < 13.0: score_39 -= 600
        elif 13.0 <= c <= 16.0: score_39 -= 200
        
        # VÙNG XANH ƯU TIÊN SỐ 1 (A=2,3 & T=1)
        if row['An'] in [2, 3] and row['Tang'] == 1:
            score_39 += 10000
            
        return score_39

    # Ép dàn 39 phải lấy từ ds_79
    ds_79['score_39'] = ds_79.apply(evaluate_39_supreme, axis=1)
    dk_39 = ds_79.sort_values(by=['score_39', 'Điểm', 'Số'], ascending=[False, False, True]).head(39)
    
    # BƯỚC 4: DÀN 59 (LẤY 39 LÀM GỐC + 20 CON KHỎE NHẤT TRONG 40 CON CÒN LẠI CỦA 79)
    s39_set = set(dk_39['Số'])
    rem_in_79 = ds_79[~ds_79['Số'].isin(s39_set)]
    # Nhặt 20 con khỏe nhất dựa trên Điểm ma trận
    top_20_remain = rem_in_79.sort_values(by=['Điểm', 'Số'], ascending=[False, True]).head(20)
    da_59 = pd.concat([dk_39, top_20_remain]).sort_values(by=['Điểm', 'Số'], ascending=[False, True])

    return dk_39, da_59, ds_79, sorted(list(set_bottom)), sorted(list(set_bet)), df_raw, (t2, b4), base_88

# --- PHẦN UI GIỮ NGUYÊN BẢN CŨ CỦA MÀY ---
# (Thay thế hàm thermal_ai_engines bằng v1398 vào phần hiển thị là xong)
