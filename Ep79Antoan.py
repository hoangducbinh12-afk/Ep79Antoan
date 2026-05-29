import streamlit as st
import pandas as pd
import json
import numpy as np
import re

# --- 1. CORE LOGIC V13.9.3 ---
def thermal_ai_v13_9_3(df_raw, history, db, mapping, cfg):
    if df_raw.empty: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), df_raw, ([], []), set()
    
    # A. 6 Chạm & Dàn 88 Base
    t2, b4 = get_hybrid_6_touches(df_raw)
    digits_6 = set(t2 + b4)
    base_88 = {f"{i:02d}" for i in range(100) if any(d in f"{i:02d}" for d in digits_6) or (f"{i:02d}"[0] == f"{i:02d}"[1])}
    
    # B. Xác định vùng loại tuyệt đối (Sát thủ dàn 39)
    remain_4 = set("0123456789") - digits_6
    kép_tuyệt_đối = {f"{d}{d}" for d in remain_4} # a. Kép từ 4 chạm ko xh

    def evaluate_39_strength(row):
        s = row['Số']
        # 1. LOẠI TUYỆT ĐỐI (Nếu dính 1 trong các cái này là văng khỏi 39)
        if s in kép_tuyệt_đối: return -1000
        if row['Tang'] in [0, 3]: return -1000       # b. T=0,3
        if row['An'] in [0, 5]: return -1000         # c. A=0,5
        if row['Cứng'] < 9.0: return -1000           # d. C<9
        
        # 2. XÉT YẾU (Trừ điểm để đẩy xuống dưới)
        score_39 = 1000 # Điểm gốc cho những con sống sót
        if row['Tang'] == 2: score_39 -= 200         # b. Xét yếu T=2
        if row['An'] == 1: score_39 -= 150           # c. Xét yếu A=1
        if row['An'] == 4: score_39 -= 100           # c. Xét yếu nhẹ A=4
        
        # d. Xét yếu C theo thang đo
        c = row['Cứng']
        if 9.0 <= c < 13.0: score_39 -= 150          # Yếu C=9,10,11,12
        elif 13.0 <= c <= 16.0: score_39 -= 50       # Yếu nhẹ C=13,14,15,16
        
        # 3. ƯU TIÊN VÙNG XANH (A=2,3 & T=1)
        if row['An'] in [2, 3] and row['Tang'] == 1:
            score_39 += 500
            
        return score_39

    # C. Tính điểm và phân cấp
    df_raw['score_39'] = df_raw.apply(evaluate_39_strength, axis=1)
    
    # Shield bảo vệ cho 79 và 59
    set_bet = get_wire_lineage_v2(db, history, mapping, cfg['bet'])
    df_raw['has_shield'] = (((df_raw['Tang'] == 0) & (df_raw['Rank'] <= 15)) | 
                            ((df_raw['An'] >= 5) & (df_raw['Số'].isin(set_bet)))).astype(int)
    
    # Điểm an toàn dàn 79 (Dựa trên 88-Base)
    df_raw['is_in_88'] = df_raw['Số'].apply(lambda x: 1 if x in base_88 else 0)
    df_raw['safety_79'] = (df_raw['is_in_88'] * 500) + (df_raw['has_shield'] * 100)
    
    # D. HẠ DÀN THEO QUY TRÌNH MỚI
    # 1. Dàn 79 (Lưới 88)
    ds_79 = df_raw.sort_values(by=['safety_79', 'Điểm'], ascending=[False, False]).head(79)
    
    # 2. Dàn 39 (Lọc tuyệt đối)
    # Lấy từ ds_79 để đảm bảo nằm trong lưới 88, sau đó lọc theo score_39
    dk_39 = ds_79.sort_values(by=['score_39', 'Điểm'], ascending=[False, False]).head(39)
    
    # 3. Dàn 59 (Lấy 39 làm gốc + 20 con khỏe nhất còn lại trong 79)
    s_39 = set(dk_39['Số'])
    remain_in_79 = ds_79[~ds_79['Số'].isin(s_39)]
    top_20_remain = remain_in_79.sort_values(by='Điểm', ascending=False).head(20)
    da_59 = pd.concat([dk_39, top_20_remain]).sort_values(by='Điểm', ascending=False)
    
    return dk_39, da_59, ds_79, df_raw, (t2, b4), base_88

# --- PHẦN UI GIỮ NGUYÊN BẢN CŨ ---
# (Thay thế hàm thermal_ai_engines_v138 bằng hàm thermal_ai_v13_9_3 trong phần UI)
