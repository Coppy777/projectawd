import streamlit as st
import pandas as pd
import numpy as np
import math
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# -------------------------  ETo -------------------------
def calculate_eto(data, latitude=14, SeaLevel=8):
    """
    คำนวณค่า ETo รายวันด้วยสูตร Penman-Monteith จากข้อมูลราย 5 นาที
    """
    # แปลง Radiant (kJ) จาก kJ เป็น MJ
    data['Radiant_MJ'] = data['Radiant (kJ)'] / 1000

    # คำนวณค่าเฉลี่ยและรวมรายวัน
    T_max = data['Temperature'].max()
    T_min = data['Temperature'].min()
    RH_max = data['Humidity'].max()
    RH_min = data['Humidity'].min()
    u2_mean = data['Wind Speed'].mean()
    P_mean = data['Pressure Air'].mean()
    Rn_total = data['Radiant_MJ'].sum()  # MJ/m2
    #Temp_avg
    T_mean = (T_max+T_min)/2
    #Humidity_avg
    RH_mean=(RH_max+RH_min)/2


    #delta_slope
    delta = 2504*math.exp((17.27*T_mean)/(T_mean+237.3))/((T_mean+237.3)**2)

    es_max_temp =0.6108 * np.exp((17.27 * T_max) / (T_max+ 237.3))

    es_min_temp =0.6108 * np.exp((17.27 * T_min) / (T_min+ 237.3))

    # ความดันไออิ่มตัว (es)
    es =(es_max_temp+es_min_temp)/2
    # ความดันไอจริง (ea)
    ea =((es_min_temp*(RH_max/100))+(es_max_temp*(RH_min/100)))/2

    # ค่าคงที่ไซโครเมตริก (gamma)
    gamma = 0.000665 * P_mean

    #Day Of Years
    Day = data['timestamp'].dt.day.iloc[0]
    Month = data['timestamp'].dt.month.iloc[0]
    Year = data['timestamp'].dt.year.iloc[0]   

    J = (Day-32)+(int((275*Month)/9))+(2*int(3/(Month+1)))+(int((Month/10)-((Year%4)/4)-0.975))

    #The solar declination
    
    solar = 0.409*(math.sin((((2*math.pi)/365)*J)-1.39))

    #the sunset angle
    
    Lat = ((math.pi*latitude)/180) 
    sunset = math.acos(-math.tan(Lat)*math.tan(solar))

    #inverse_square

    dr = 1+(0.033*(math.cos((2*math.pi*J)/365)))

    #The extraterrestrial radiation

    ex = ((24*4.92*dr)/math.pi)*((sunset)*math.sin(Lat)*math.sin(solar)+math.cos(Lat)*math.cos(solar)*math.sin(sunset))

    #clear sky

    Rso = ((0.75+(0.00002*SeaLevel))*ex)

    #long wave 

    Rnl = (4.903*(10**-9))*((((T_max+273)**4)+((T_min+273)**4))/2)*(0.34-(0.14*(ea**0.5)))*(1.35*(((Rn_total *60)/1000000)/Rso)-0.35)

    ##The net radiation
    Rn = ((1-0.23)*(((Rn_total*60)/1000000)))-Rnl

    # Penman-Monteith Equation
    #Cn = 900, cd = 0.34

    eto = ((0.408 * delta * (Rn - 0)) +
           (gamma * (900 / (T_mean + 273)) * u2_mean * (es - ea))) / (
           delta + gamma * (1 + 0.34 * u2_mean))

    return eto,T_max ,T_min,RH_max,RH_min,RH_mean,u2_mean,P_mean,Rn_total,T_mean,delta,es_max_temp,es_min_temp,es,es,Day,Month,Year,J,solar,sunset,dr,ex,Rso,Rnl
# ------------------------- ส่วนหลักของ Streamlit -------------------------
st.set_page_config(page_title="ETo Daily ", layout="wide")
st.title("🌿 ETo Daily  (Penman-Monteith Method)")
st.markdown("""
คำนวณค่า **ETo รายวัน** จากข้อมูลราย 5 นาที โดยวิธี **Penman-Monteith** \\
📅 **ช่วงเวลา:** 07:00 ของวันก่อนหน้า ถึง 06:59 ของวันถัดไป
""")



# ------------------------- ดึงข้อมูลจาก Google Sheets -------------------------
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_iTnwxt4Nq9eXhJ8hIeaBpX_VLjoFWEPeudmGf_efuo/export?format=csv&gid=613751333"

@st.cache_data
def load_data(sheet_url):
    return pd.read_csv(sheet_url)

df = load_data(SHEET_URL)

# ตรวจสอบคอลัมน์ที่จำเป็น
required_cols = ['timestamp', 'Wind Speed', 'Temperature', 'Humidity', 'Pressure Air', 'Radiant (W)', 'Radiant (kJ)']
if not all(col in df.columns for col in required_cols):
    st.error("❌ Google Sheets ต้องประกอบด้วยคอลัมน์: " + ", ".join(required_cols))
else:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.sort_values('timestamp', inplace=True)

    unique_dates = df['timestamp'].dt.date.unique()
    selected_date = st.date_input("📅 เลือกวันที่ที่ต้องการคำนวณ ETo", min_value=min(unique_dates), max_value=max(unique_dates), value=min(unique_dates))

    start_time = datetime.combine(selected_date - timedelta(days=1), datetime.min.time()) + timedelta(hours=7)
    end_time = start_time + timedelta(days=1) - timedelta(minutes=5)

    st.info(f"🕖 ช่วงเวลาคำนวณ: {start_time} ถึง {end_time}")

    filtered_data = df[(df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)]

    if filtered_data.empty:
        st.warning("⚠️ ไม่มีข้อมูลในช่วงเวลาที่เลือก กรุณาเลือกวันที่อื่นหรือเช็คข้อมูลใน Google Sheets อีกครั้ง")
    else:
        eto,T_max ,T_min,RH_max,RH_min,RH_mean,u2_mean,P_mean,Rn_total,T_mean,delta,es_max_temp,es_min_temp,es,es,Day,Month,Year,J,solar,sunset,dr,ex,Rso,Rnl = calculate_eto(filtered_data)

        st.subheader("📊 ผลลัพธ์การคำนวณ ETo รายวัน")
        st.metric("🌿 ETo (mm/day)", f"{eto:.2f}")

        col1, col2, col3 = st.columns(3)
        col1.metric("🌡️ อุณหภูมิเฉลี่ย (°C)", f"{T_mean:.2f}")
        col2.metric("💧 ความชื้นเฉลี่ย (%)", f"{RH_mean:.2f}")
        col3.metric("🌬️ ความเร็วลมเฉลี่ย (m/s)", f"{u2_mean:.2f}")

        col4, col5 = st.columns(2)
        col4.metric("🌫️ ความดันบรรยากาศเฉลี่ย (kPa)", f"{P_mean:.2f}")
        col5.metric("🌞 รังสีสุทธิรวม (MJ/m²)", f"{Rn_total:.2f}")

        st.subheader("📈 กราฟข้อมูลราย 5 นาที")
        #st.line_chart(filtered_data.set_index('timestamp')[['']])
        st.line_chart(filtered_data.set_index('timestamp')[['Radiant (W)']])
        st.bar_chart(filtered_data.set_index('timestamp')['Radiant (kJ)'])

        start_date = df['timestamp'].dt.date.min() + timedelta(days=1)
        end_date = df['timestamp'].dt.date.max()

        eto_results = []
        current_date = start_date

        
        while current_date <= end_date:
            start_time = datetime.combine(current_date - timedelta(days=1), datetime.min.time()) + timedelta(hours=7)
            end_time = start_time + timedelta(days=1) - timedelta(minutes=5)

            daily_data = df[(df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)]
            if not daily_data.empty:
                eto,T_max ,T_min,RH_max,RH_min,RH_mean,u2_mean,P_mean,Rn_total,T_mean,delta,es_max_temp,es_min_temp,es,es,Day,Month,Year,J,solar,sunset,dr,ex,Rso,Rnl = calculate_eto(daily_data)
                eto_results.append({
                    "Date": current_date,
                    "ETo (mm/day)": eto,
                    "Temperature (°C)": T_mean,
                    "Humidity (%)": RH_mean,
                    "Wind Speed (m/s)": u2_mean,
                    "Pressure Air (kPa)": P_mean,
                    "Radiant (MJ/m²)": Rn_total
                })
            current_date += timedelta(days=1)
        result_df = pd.DataFrame(eto_results)
        
        st.subheader("📊 ตารางค่า ETo รายวัน (07:00 - 06:55)")
        st.dataframe(result_df, use_container_width=True)

        csv = result_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 ดาวน์โหลดผลลัพธ์เป็น CSV", data=csv, file_name="ETo_Daily_Results.csv", mime='text/csv')



