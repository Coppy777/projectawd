import streamlit as st
import pandas as pd
import plotly.express as px
import math
from st_aggrid import AgGrid, GridOptionsBuilder
import st_aggrid

st.set_page_config(
    page_title="Project Worrier",  # ชื่อหัวข้อของหน้า
    page_icon=":tada:",           # ไอคอนของหน้า (ใช้ emoji หรือ path รูปภาพ)
    layout="wide"                 # เลย์เอาต์ของหน้า (เช่น 'centered', 'wide'
)

# กำหนดค่าคงที่
SeaLevel = 8
Lattitude = 14
Lat = ((math.pi * Lattitude) / 180)

def eto_compute():
    # โหลดข้อมูลจาก Google Sheet
    sheet_url = "https://docs.google.com/spreadsheets/d/1rs_mYXCJrwQG0IaXh4laWtAbm_uYsYowweFkK4MSzno/export?format=csv"
    df = pd.read_csv(sheet_url)
    df.columns=['timestamp','Wind Speed','Temperature','Humidmidity','Pressure Air','Radiant(kj)']
    df['datetime'] = pd.to_datetime(df['timestamp'], format='%d/%m/%Y %H:%M:%S')
    df.set_index('datetime', inplace=True)

# Define the time range from 7.00 of yesterday to 6.59 of today
    today = pd.to_datetime('today').normalize()  # Get today's date at midnight
    yesterday_7am = (today - pd.Timedelta(days=1) + pd.Timedelta(hours=7)).time()
    today_659am = (today + pd.Timedelta(hours=6, minutes=59)).time()
     
#df_filtered=df.between_time(yesterday_7am, today_659am)
    df_filtered = df.between_time(yesterday_7am, today_659am).copy()
    
    daily_data = df_filtered.resample('24H').agg({
        'timestamp': 'datetime',
        'Wind Speed': 'Wind',
        'Temperature': 'Temp',
        'Humidity': 'Humid',
        'Pressure Air': 'Pressure',
        'Radiant (kj)': 'Solar'
    })
    
    # แปลงคอลัมน์ datetime ให้เป็น datetime object
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)

    # กำหนดช่วงเวลา 07:00 - 06:59 ของวันถัดไป
    today = pd.to_datetime('today').normalize()
    start_time = today - pd.Timedelta(days=1) + pd.Timedelta(hours=7)
    end_time = today + pd.Timedelta(hours=6, minutes=59)
    
    df_filtered = df.loc[start_time:end_time].copy()
    
    # คำนวณค่าเฉลี่ยรายวัน
    daily_data = df_filtered.resample('24H').agg({
        'Temp': ['max', 'min', 'mean'],
        'Humid': ['max', 'min', 'mean'],
        'Wind': ['mean'],
        'Pressure': ['mean'],
        'Solar': ['sum']
    })
    
    # จัดรูปแบบคอลัมน์
    daily_data.reset_index(inplace=True)
    daily_data.columns = ['datetime','TempMax', 'TempMin', 'TempMean', 'HumidMax', 'HumidMin', 'HumidMean', 'WindMean', 'PressureMean', 'SolarSum']
    daily_data['timestamp'] = daily_data['datetime'].dt.date.astype(str)

    def temp_avg(row): #Average Temperature
        return (row.iloc[1] + row.iloc[2])/2
    daily_data['TempAvg']  = daily_data.apply(temp_avg, axis = 1)

    def delta_slope(row): # Delta Slope
         return (2504*math.exp((17.27*row.iloc[10])/(row.iloc[10]+237.3))/((row.iloc[10]+237.3)**2))
    daily_data['DeltaSlope'] = daily_data.apply(delta_slope, axis = 1)

    def es_max_temp(row): #Es Max. Temperature
         return 0.6108*math.exp((17.27*row.iloc[1])/(row.iloc[1]+237.3))
    daily_data['EsMaxTemp'] = daily_data.apply(es_max_temp, axis = 1)

    def es_min_temp(row): # Es Min. Temperature
         return 0.6108*math.exp((17.27*row.iloc[2])/(row.iloc[2]+237.3))
    daily_data['EsMinTemp'] = daily_data.apply(es_min_temp, axis = 1)

    def es_avg(row): #Average Es
         return (row.iloc[12]+row.iloc[13])/2
    daily_data['EsAvg'] = daily_data.apply(es_avg, axis = 1)

    #Ea = ((EsMinTemp*(MaxHumid/100))+(EsMaxTemp*(MinHumid/100)))/2
    def ea(row): #Actual Vapore pressure (Ea)
        return ((row.iloc[12]*(row.iloc[4]/100))+(row.iloc[13]*(row.iloc[5]/100)))/2
    daily_data['Ea'] = daily_data.apply(ea, axis = 1)

    #The mean atmospheric pressure at the station
    def psyco(row):
        return 0.000665*row.iloc[8]*0.1
    daily_data['PsychomaticConstant'] = daily_data.apply(psyco, axis = 1)

    # แปลงคอลัมน์ date จาก string เป็น datetime64
    daily_data['timestamp'] = pd.to_datetime(daily_data['timestamp'])
    # สร้างคอลัมน์ใหม่สำหรับวัน, เดือน, และปี
    daily_data['Day'] = daily_data['date'].dt.day
    daily_data['Month'] = daily_data['date'].dt.month
    daily_data['Year'] = daily_data['date'].dt.year

    def dayofyears(row):
            return (row.iloc[18]-32)+(int((275*row.iloc[19])/9))+(2*int(3/(row.iloc[19]+1)))+(int(((row.iloc[19]/100)-((row.iloc[20]%4)/4))+0.975))
    daily_data['Day of Year'] = daily_data.apply(dayofyears, axis = 1)

    def solar_dec(row): #The solar declination
        return 0.409*(math.sin((((2*math.pi)*row.iloc[21])/365)-1.39))
    daily_data['Declination'] = daily_data.apply(solar_dec, axis = 1)

    def sunset_angle(row): ##The sunset Angle
        return math.acos(-math.tan(Lat)*math.tan(row.iloc[24]))
    daily_data['Sunset Angle'] = daily_data.apply(sunset_angle, axis = 1)

    def inverse_square(row): #The inverse square of the relative distance Earth to Sun
        return 1+(0.033*(math.cos((2*math.pi*row.iloc[21])/365)))
    daily_data['Dr'] = daily_data.apply(inverse_square, axis = 1)

    #The extraterrestrial radiation
    #Ra1=((24*4.92*Dr)/math.pi)
    #Ra2=(SunsetAngle)*math.sin(Lat)*math.sin(Deelination)
    #Ra3=math.cos(Lat)*math.cos(Deelination)*math.sin(SunsetAngle)
    #Ra4=Ra2+Ra3
    #Ra=Ra1*Ra4
    def extra_radiation(row): #The extraterrestrial radiation
        return ((24*4.92*row.iloc[24])/math.pi)*((row.iloc[23])*math.sin(Lat)*math.sin(row.iloc[22])+math.cos(Lat)*math.cos(row.iloc[22])*math.sin(row.iloc[23]))
    daily_data['Ra'] = daily_data.apply(extra_radiation, axis = 1)

 #Clear-sky radiation 
    #Rsw = ((0.75+(0.00002*SeaLevel))*Ra)
    def clear_sky(row): #Clear-sky radiation 
        return ((0.75+(0.00002*SeaLevel))*row.iloc[25])
    daily_data['Rsw'] = daily_data.apply(clear_sky, axis = 1)

    #The net-long wave radiation 
    #Rnl1 = (4.903 * (10**-9))
    #Rnl2 = ((((MaxTemp+273)**4)+((MinTemp+273)**4))/2)
    #Rnl3 = (0.34-(0.14*(Ea**0.5)))
    #Rn14 = (1.35*(Rs/Rsw)-0.35)
    #Rnl = Rnl1*Rnl2*Rnl3*Rn14
    def long_wave(row): #The net radiation
        return (4.903*(10**-9))*((((row.iloc[1]+273)**4)+((row.iloc[2]+273)**4))/2)*(0.34-(0.14*(row.iloc[14]**0.5)))*(1.35*(((row.iloc[9]*60)/1000000)/row.iloc[26])-0.35)
    daily_data['RnL'] = daily_data.apply(long_wave, axis = 1)
    
    def net_radiation(row): #The net radiation
        return ((1-0.23)*(((row.iloc[9]*60)/1000000)))-row.iloc[27]
    daily_data['Rn'] = daily_data.apply(net_radiation, axis = 1)

    def eto_pm(row): #ETo Penman-Monteith
    #ETo1 = (0.408*DeltaSlope)*(Rn-Ground)
    #ETo2 = PsychromaticConstant*(Cn/(TempAvg+273))*(EsAvg-Ea)*WindSpeed
    #ETo3 = DeltaSlope+(PsychromaticConstant*(1+(Cd*WindSpeed)))
    #ETo = (ETo1+ETo2)/ETo3
    # Cn = 900, cd = 0.34
    #Ground = 0
        return (((0.408*row.iloc[12])*(row.iloc[28]-0))+(row.iloc[17]*(900/(row.iloc[11]+273))*(row.iloc[15]-row.iloc[16])*row.iloc[7]))/(row.iloc[12]+(row.iloc[17]*(1+(0.34*row.iloc[7]))))
    daily_data['ETo'] = daily_data.apply(eto_pm, axis = 1)

    custom_slider_colors = """
    <style>
        .rangeslider-bg {
            fill: lightgray !important;
        }
        .rangeslider-mask-min, .rangeslider-mask-max {
            fill: gray !important;
        }
        .rangeslider-slidebox {
            fill: blue !important;
        }
    </style>
    """
    st.markdown(custom_slider_colors, unsafe_allow_html=True)
    print(daily_data.info())

  #Temperature Graph
    st.subheader('🌿💧 :blue[Evaporation Transpiration Reference (ETO (mm.))]')
    fig_temp = px.bar(daily_data, x='timestamp', y=['ETo'])
      # Customize the y-axis label
    fig_temp.update_yaxes(title_text="Evaporation Transpiration Reference (mm.)")  # Change the y-axis label

    fig_temp.update_xaxes(
        title_text='Date',
        rangeslider_visible=True,  # เพิ่ม slider ใต้กราฟ
)
    st.plotly_chart(fig_temp,use_container_width=True)

     #Show Table
    daily_data1 = daily_data[['timestamp','ETo']]
    gd=GridOptionsBuilder.from_dataframe(daily_data1)
    gd.configure_pagination(paginationAutoPageSize=False)
    #gd.configure_default_column()
    gridoptions = gd.build()
#    AgGrid(daily_data1,gridOptions=gridoptions)
    daily_data_copy = daily_data1.copy()
    AgGrid(daily_data_copy, gridOptions=gridoptions)

    Dailydatacsv=daily_data1.to_csv(index=False)
    st.download_button('Download Data',data=Dailydatacsv,file_name='DailydataETo.csv',mime='text/scv',
        help='Click Here to Download for CSV format')

#    print(daily_data)
