import streamlit as st
import pandas as pd
from supabase import create_client, Client
import json
import time
import base64
from datetime import datetime

# ==============================================================================
# PAGE CONFIGURATION & RTL STYLING
# ==============================================================================
st.set_page_config(
    page_title="سیستم یکپارچه مدیریت باشگاه",
    page_icon="🥋",
    layout="wide",
    initial_sidebar_state="expanded"
)

rtl_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;700;900&display=swap');
    
    html, body, [data-testid="stSidebar"], .stApp, .stMarkdown, p, h1, h2, h3, h4, h5, h6, label, button, select, input, div, span, textarea {
        font-family: 'Vazirmatn', sans-serif !important;
        direction: rtl !important;
        text-align: right !important;
    }
    
    [data-testid="stSidebar"] {
        text-align: right !important;
        direction: rtl !important;
    }
    [data-testid="stSidebarNav"] { direction: rtl !important; }
    
    .stTextInput, .stSelectbox, .stTextArea, .stNumberInput, .stDateInput, .stFileUploader {
        direction: rtl !important;
        text-align: right !important;
    }
    
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"], [data-testid="stMetricDelta"] {
        text-align: right !important;
        direction: rtl !important;
    }
    
    .digital-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: white;
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        max-width: 450px;
        margin: 10px auto;
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.1);
    }
</style>
"""
st.markdown(rtl_css, unsafe_allow_html=True)

# ==============================================================================
# SUPABASE CONNECTION
# ==============================================================================
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("ارتباط با پایگاه داده برقرار نشد. لطفاً تنظیمات Secrets را در استریم‌لیت بررسی کنید.")
    st.stop()

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def to_persian_digits(number):
    if number is None: return ""
    return str(number).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

def image_to_base64(uploaded_file):
    if uploaded_file is not None:
        return base64.b64encode(uploaded_file.read()).decode('utf-8')
    return ""

def jalali_to_days(jalali_str):
    try:
        parts = jalali_str.split('/')
        if len(parts) != 3: return 0
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        days = (y - 1400) * 365 + ((y - 1400) // 4)
        for i in range(1, m):
            if i <= 6: days += 31
            elif i <= 11: days += 30
            else: days += 29
        return days + d
    except Exception: return 0

# ==============================================================================
# DATA LOADING FROM SUPABASE
# ==============================================================================
if 'db_loaded' not in st.session_state:
    # 1. Load Settings
    settings_data = supabase.table('club_settings').select('*').execute().data
    settings_dict = {r['key']: r['value'] for r in settings_data}
    
    st.session_state.club_name = settings_dict.get('club_name', 'باشگاه ورزشی')
    st.session_state.club_logo = settings_dict.get('club_logo', '')
    st.session_state.admin_username = settings_dict.get('admin_username', 'admin')
    st.session_state.admin_password = settings_dict.get('admin_password', '1234')

    # 2. Load Main Tables
    st.session_state.specialties = supabase.table('specialties').select('*').execute().data
    st.session_state.students = supabase.table('students').select('*').execute().data
    st.session_state.coaches = supabase.table('coaches').select('*').execute().data
    st.session_state.tuitions = supabase.table('tuitions').select('*').execute().data
    st.session_state.events = supabase.table('events').select('*').execute().data
    st.session_state.sms_logs = supabase.table('sms_logs').select('*').order('date', desc=True).execute().data
    
    # 3. Load Attendance (Parse JSON)
    att_data = supabase.table('attendance').select('*').execute().data
    st.session_state.attendance = []
    for row in att_data:
        try:
            row['presentStudentIds'] = json.loads(row['presentStudentIds']) if isinstance(row['presentStudentIds'], str) else row['presentStudentIds']
        except:
            row['presentStudentIds'] = []
        st.session_state.attendance.append(row)
        
    # Default SMS Templates
    st.session_state.sms_templates = [
        {'id': 't1', 'title': 'یادآور شهریه', 'text': 'هنرجوی گرامی [نام]، مهلت شهریه شما در تاریخ [تاریخ] به پایان رسیده است. لطفا تمدید نمایید.'},
        {'id': 't2', 'title': 'یادآور بیمه', 'text': 'هنرجوی عزیز [نام]، مهلت اعتبار بیمه ورزشی شما پایان می‌یابد. باشگاه ورزشی.'},
        {'id': 't3', 'title': 'خوش‌آمدگویی', 'text': 'هنرجوی عزیز [نام]، به باشگاه خوش آمدید. آرزوی موفقیت برای شما داریم.'}
    ]
        
    st.session_state.db_loaded = True

TODAY_JALALI = "1405/04/11"
active_specialties_names = [s['name'] for s in st.session_state.specialties]

# ==============================================================================
# ROUTING & SIDEBAR
# ==============================================================================
if st.session_state.club_logo:
    st.sidebar.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{st.session_state.club_logo}" width="120" style="border-radius:15px; margin-bottom:10px;"></div>', unsafe_allow_html=True)
    
st.sidebar.markdown(f"<h2 style='text-align:center;'>🥋 {st.session_state.club_name}</h2>", unsafe_allow_html=True)
st.sidebar.divider()

view_mode = st.sidebar.radio("مسیر کاربری", ["📝 فرم ثبت‌نام عمومی (لینک وب)", "🔐 ورود به پنل مدیریت"])
st.sidebar.divider()
st.sidebar.info(f"📅 تاریخ جاری سیستم: {to_persian_digits(TODAY_JALALI)}")

# ==============================================================================
# PUBLIC VIEW: REGISTRATION FORM
# ==============================================================================
if view_mode == "📝 فرم ثبت‌نام عمومی (لینک وب)":
    
    col_t1, col_t2 = st.columns([1, 4])
    with col_t1:
        if st.session_state.club_logo:
            st.markdown(f'<img src="data:image/png;base64,{st.session_state.club_logo}" width="100" style="border-radius:10px;">', unsafe_allow_html=True)
    with col_t2:
        st.title(f"ثبت‌نام در {st.session_state.club_name}")
        st.markdown("هنرجوی گرامی، لطفا جهت شروع فرآیند ثبت‌نام، فرم زیر را تکمیل نمایید.")
        
    st.divider()
    
    st.markdown("### 🗓️ برنامه زمان‌بندی کلاس‌ها و مربیان")
    if st.session_state.coaches:
        grid_cols = st.columns(2)
        for idx, coach in enumerate(st.session_state.coaches):
            with grid_cols[idx % 2]:
                img_tag = f'<img src="data:image/png;base64,{coach["logo"]}" width="55" height="55" style="border-radius:50%; margin-left:15px; float:right; object-fit:cover; border: 2px solid #bae6fd;">' if coach.get("logo") else '<div style="width:55px; height:55px; background:#e2e8f0; border-radius:50%; float:right; margin-left:15px; text-align:center; line-height:55px; font-size:26px; border: 2px solid #bae6fd;">👤</div>'
                
                st.markdown(f"""
                <div style='background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 12px; padding: 15px; margin-bottom: 15px; height: 140px;'>
                    {img_tag}
                    <div style='margin-top: 2px;'>
                        <h4 style='margin:0; color:#0369a1;'>استاد {coach['name']}</h4>
                        <div style='font-size:12px; color:#475569; margin-top:8px; line-height:1.6;'>
                            <b>رشته:</b> {coach['specialty']}<br>
                            <b>⏰ زمان:</b> {coach.get('schedule', 'نامشخص')}<br>
                            <b>📞 تماس:</b> <span dir="ltr">{to_persian_digits(coach.get('phone', '---'))}</span>
                        </div>
                    </div>
                    <div style="clear:both;"></div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.warning("در حال حاضر برنامه کلاسی مربیان ثبت نشده است.")
        
    st.divider()
    
    st.markdown("### 📋 فرم اطلاعات هنرجو")
    with st.form("public_registration", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("نام و نام خانوادگی:")
            fatherName = st.text_input("نام پدر:")
            national_id = st.text_input("کد ملی:")
            birthDate = st.text_input("تاریخ تولد (مثال: ۱۳۸۰/۰۵/۱۲):")
            s_photo_public = st.file_uploader("عکس پرسنلی هنرجو:", type=['png', 'jpg', 'jpeg'])
        with col2:
            phone = st.text_input("شماره همراه:")
            coach_opts = st.session_state.coaches
            selected_coach_id = st.selectbox("انتخاب مربی کلاس:", options=[""] + [c['id'] for c in coach_opts], format_func=lambda x: next((c['name'] for c in coach_opts if c['id'] == x), "--- انتخاب کنید ---"))
            specialty = st.selectbox("رشته ورزشی:", active_specialties_names if active_specialties_names else ["نامشخص"])
            address = st.text_area("آدرس دقیق محل سکونت:", height=130)
            
        submitted = st.form_submit_button("ثبت نهایی اطلاعات", type="primary")
        
        if submitted:
            if not name or not phone or not national_id:
                st.error("لطفا فیلدهای نام، شماره همراه و کد ملی را حتماً تکمیل فرمایید.")
            else:
                photo_b64 = image_to_base64(s_photo_public)
                new_id = f's-{int(time.time())}'
                new_s = {
                    'id': new_id, 'name': name, 'fatherName': fatherName, 'birthDate': birthDate,
                    'phone': phone, 'nationalId': national_id, 'address': address,
                    'coachId': selected_coach_id, 'specialty': specialty, 'status': 'در انتظار تایید',
                    'insuranceExpiry': '', 'tuitionExpiry': '', 'joinDate': TODAY_JALALI, 'photo': photo_b64
                }
                # Insert into Supabase
                supabase.table('students').insert(new_s).execute()
                st.session_state.students.append(new_s)
                st.success(f"هنرجوی عزیز {name}، اطلاعات شما با موفقیت ثبت شد.")
                st.balloons()

# ==============================================================================
# ADMIN VIEW: SECURE DASHBOARD
# ==============================================================================
elif view_mode == "🔐 ورود به پنل مدیریت":
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.subheader("ورود به سیستم یکپارچه مدیریت")
        with st.form("login_form"):
            username = st.text_input("نام کاربری:")
            password = st.text_input("رمز عبور:", type="password")
            if st.form_submit_button("ورود به مدیریت"):
                if username == st.session_state.admin_username and password == st.session_state.admin_password:
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("نام کاربری یا رمز عبور اشتباه است.")
    else:
        menu_options = {
            "dashboard": "📊 پیشخوان مانیتورینگ",
            "students": "👥 مدیریت هنرجویان",
            "specialties": "🎯 مدیریت رشته‌های ورزشی",
            "coaches": "👔 مدیریت مربیان",
            "attendance": "📋 حضور و غیاب",
            "tuition": "💳 امور مالی و خزانه‌داری",
            "sms": "💬 سامانه پیامک",
            "events": "📅 رویدادها",
            "settings": "⚙️ تنظیمات"
        }

        selection = st.sidebar.radio("بخش‌های سیستم:", options=list(menu_options.keys()), format_func=lambda x: menu_options[x])

        # ----------------------------------------------------------------------
        # DASHBOARD
        # ----------------------------------------------------------------------
        if selection == "dashboard":
            st.title("📊 پیشخوان مانیتورینگ هوشمند")
            total_students = len(st.session_state.students)
            active_students = len([s for s in st.session_state.students if s['status'] == 'فعال'])
            total_coaches = len(st.session_state.coaches)
            total_revenue = sum([t['amount'] for t in st.session_state.tuitions])
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("کل ثبت‌نامی‌ها", to_persian_digits(total_students), f"فعال: {to_persian_digits(active_students)}")
            col2.metric("اساتید و مربیان", to_persian_digits(total_coaches))
            col3.metric("درآمد ثبت شده", f"{to_persian_digits(f'{total_revenue:,}')} ریال")
            expired = len([s for s in st.session_state.students if s['tuitionExpiry'] and s['tuitionExpiry'] < TODAY_JALALI and s['status'] == 'فعال'])
            col4.metric("شهریه‌های منقضی", to_persian_digits(expired), delta_color="inverse")
            st.divider()

        # ----------------------------------------------------------------------
        # STUDENTS & EXCEL IMPORT
        # ----------------------------------------------------------------------
        elif selection == "students":
            st.title("👥 مدیریت هنرجویان")
            tab_list, tab_add, tab_excel, tab_card = st.tabs(["لیست و ویرایش", "ثبت هنرجوی جدید", "📥 ورود از اکسل", "صدور کارت"])
            
            with tab_list:
                if st.session_state.students:
                    df_st = pd.DataFrame(st.session_state.students)
                    df_st_renamed = df_st[['id', 'name', 'fatherName', 'phone', 'specialty', 'status', 'tuitionExpiry']].copy()
                    df_st_renamed.columns = ['شناسه', 'نام و نام خانوادگی', 'نام پدر', 'شماره همراه', 'رشته ورزشی', 'وضعیت', 'سررسید شهریه']
                    st.dataframe(df_st_renamed, use_container_width=True, hide_index=True)
                    
                    st.markdown("---")
                    st.markdown("#### ✏️ ویرایش کامل اطلاعات هنرجو")
                    
                    selected_student_id = st.selectbox("انتخاب هنرجو جهت ویرایش یا حذف:", options=[s['id'] for s in st.session_state.students], format_func=lambda x: next(s['name'] for s in st.session_state.students if s['id'] == x))
                    st_idx = next(i for i, s in enumerate(st.session_state.students) if s['id'] == selected_student_id)
                    cur_st = st.session_state.students[st_idx]
                    
                    with st.form("edit_student_form"):
                        ecol1, ecol2 = st.columns(2)
                        with ecol1:
                            e_name = st.text_input("نام:", value=cur_st.get('name', ''))
                            e_father = st.text_input("نام پدر:", value=cur_st.get('fatherName', ''))
                            e_nid = st.text_input("کد ملی:", value=cur_st.get('nationalId', ''))
                            e_birth = st.text_input("تاریخ تولد:", value=cur_st.get('birthDate', ''))
                            e_photo = st.file_uploader("عکس هنرجو (آپلود مجدد جایگزین عکس قبلی می‌شود)", type=['png', 'jpg', 'jpeg'])
                        with ecol2:
                            e_phone = st.text_input("شماره همراه:", value=cur_st.get('phone', ''))
                            
                            c_opts = st.session_state.coaches
                            c_idx_opt = 0
                            if cur_st.get('coachId') and any(c['id'] == cur_st['coachId'] for c in c_opts):
                                c_idx_opt = [c['id'] for c in c_opts].index(cur_st['coachId']) + 1
                            e_coach = st.selectbox("مربی:", options=[""] + [c['id'] for c in c_opts], index=c_idx_opt, format_func=lambda x: next((c['name'] for c in c_opts if c['id'] == x), "--- انتخاب کنید ---")) if c_opts else ""
                            
                            s_opts = active_specialties_names if active_specialties_names else ["نامشخص"]
                            s_idx_opt = s_opts.index(cur_st['specialty']) if cur_st.get('specialty') in s_opts else 0
                            e_spec = st.selectbox("رشته ورزشی:", options=s_opts, index=s_idx_opt)
                            
                            e_address = st.text_area("آدرس:", value=cur_st.get('address', ''), height=130)
                        
                        ecol3, ecol4, ecol5 = st.columns(3)
                        with ecol3:
                            e_ins = st.text_input("انقضای بیمه:", value=cur_st.get('insuranceExpiry', ''))
                        with ecol4:
                            e_tui = st.text_input("انقضای شهریه:", value=cur_st.get('tuitionExpiry', ''))
                        with ecol5:
                            status_opts = ["فعال", "غیرفعال", "در انتظار تایید"]
                            status_idx = status_opts.index(cur_st['status']) if cur_st.get('status') in status_opts else 0
                            e_status = st.selectbox("وضعیت:", options=status_opts, index=status_idx)
                            
                        sub_edit, sub_del = st.columns([1, 1])
                        with sub_edit:
                            if st.form_submit_button("💾 ذخیره تغییرات", type="primary"):
                                final_photo = image_to_base64(e_photo) if e_photo else cur_st.get('photo', '')
                                updates = {
                                    'name': e_name, 'fatherName': e_father, 'nationalId': e_nid, 'birthDate': e_birth,
                                    'phone': e_phone, 'coachId': e_coach, 'specialty': e_spec, 'address': e_address,
                                    'insuranceExpiry': e_ins, 'tuitionExpiry': e_tui, 'status': e_status, 'photo': final_photo
                                }
                                # Update Supabase
                                supabase.table('students').update(updates).eq('id', cur_st['id']).execute()
                                st.session_state.students[st_idx].update(updates)
                                st.success("اطلاعات هنرجو با موفقیت ویرایش شد.")
                                time.sleep(1)
                                st.rerun()
                        with sub_del:
                            if st.form_submit_button("❌ حذف هنرجو"):
                                supabase.table('students').delete().eq('id', cur_st['id']).execute()
                                st.session_state.students.pop(st_idx)
                                st.warning("هنرجو حذف شد.")
                                time.sleep(1)
                                st.rerun()

            with tab_add:
                with st.form("add_student_form", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        name = st.text_input("نام و نام خانوادگی:")
                        fatherName = st.text_input("نام پدر:")
                        national_id = st.text_input("کد ملی:")
                        birthDate = st.text_input("تاریخ تولد:")
                        s_photo = st.file_uploader("عکس هنرجو", type=['png', 'jpg', 'jpeg'])
                    with col2:
                        phone = st.text_input("شماره همراه:")
                        coach_options = st.session_state.coaches
                        coach_id = st.selectbox("مربی:", options=[""] + [c['id'] for c in coach_options], format_func=lambda x: next((c['name'] for c in coach_options if c['id'] == x), "--- انتخاب کنید ---")) if coach_options else ""
                        specialty = st.selectbox("رشته ورزشی:", active_specialties_names if active_specialties_names else ["نامشخص"])
                        address = st.text_area("آدرس:", height=130)
                    
                    col3, col4 = st.columns(2)
                    with col3:
                        insurance_exp = st.text_input("انقضای بیمه ورزشی:", value="1406/04/11")
                    with col4:
                        tuition_exp = st.text_input("انقضای شهریه:", value="1405/05/11")
                    
                    if st.form_submit_button("ثبت‌نام هنرجو"):
                        photo_b64 = image_to_base64(s_photo)
                        new_s = {
                            'id': f's-{int(time.time())}', 'name': name, 'fatherName': fatherName, 'birthDate': birthDate,
                            'phone': str(phone), 'nationalId': str(national_id), 'address': address,
                            'coachId': coach_id, 'specialty': specialty, 'status': 'فعال',
                            'insuranceExpiry': insurance_exp, 'tuitionExpiry': tuition_exp, 'joinDate': TODAY_JALALI, 'photo': photo_b64
                        }
                        supabase.table('students').insert(new_s).execute()
                        st.session_state.students.append(new_s)
                        st.success("هنرجو ثبت شد.")
                        st.rerun()

            with tab_excel:
                st.markdown("### وارد کردن گروهی از فایل اکسل")
                st.info("فایل اکسل شما باید دارای این ستون‌ها باشد: `نام و نام خانوادگی` ، `کد ملی` ، `شماره همراه` ، `نام پدر` ، `رشته ورزشی`")
                uploaded_excel = st.file_uploader("فایل اکسل خود را انتخاب کنید (.xlsx)", type=['xlsx'])
                if uploaded_excel is not None:
                    try:
                        df_import = pd.read_excel(uploaded_excel)
                        st.dataframe(df_import.head())
                        if st.button("شروع انتقال به سیستم", type="primary"):
                            success_count = 0
                            for index, row in df_import.iterrows():
                                try:
                                    s_name = str(row.get('نام و نام خانوادگی', ''))
                                    if pd.isna(row.get('نام و نام خانوادگی')) or s_name.strip() == '': continue
                                    s_nid = str(row.get('کد ملی', ''))
                                    s_phone = str(row.get('شماره همراه', ''))
                                    s_father = str(row.get('نام پدر', ''))
                                    s_spec = str(row.get('رشته ورزشی', 'نامشخص'))
                                    new_s = {
                                        'id': f's-{int(time.time()*1000)+index}', 'name': s_name, 'fatherName': s_father, 'birthDate': '', 
                                        'phone': s_phone, 'nationalId': s_nid, 'address': '', 'coachId': '', 'specialty': s_spec, 
                                        'status': 'فعال', 'insuranceExpiry': '', 'tuitionExpiry': '', 'joinDate': TODAY_JALALI, 'photo': ''
                                    }
                                    supabase.table('students').insert(new_s).execute()
                                    st.session_state.students.append(new_s)
                                    success_count += 1
                                except Exception as e:
                                    st.error(f"خطا در سطر {index}: {str(e)}")
                            st.success(f"{to_persian_digits(success_count)} هنرجو با موفقیت وارد سیستم شدند.")
                            time.sleep(2)
                            st.rerun()
                    except Exception as e:
                        st.error("خطا در خواندن فایل اکسل.")

            with tab_card:
                if st.session_state.students:
                    sel_card = st.selectbox("صدور کارت هنرجو:", options=[s['id'] for s in st.session_state.students], format_func=lambda x: next(s['name'] for s in st.session_state.students if s['id'] == x))
                    s_data = next(s for s in st.session_state.students if s['id'] == sel_card)
                    
                    coach_name = "نامشخص"
                    coach_phone = "---"
                    if s_data.get('coachId'):
                        coach_info = next((c for c in st.session_state.coaches if c['id'] == s_data['coachId']), None)
                        if coach_info:
                            coach_name = coach_info['name']
                            coach_phone = coach_info['phone']

                    club_logo_tag = f'<img src="data:image/png;base64,{st.session_state.club_logo}" width="50" style="position: absolute; left: 20px; top: 20px; border-radius: 8px;">' if st.session_state.club_logo else ''
                    
                    student_photo_tag = f'<img src="data:image/png;base64,{s_data.get("photo", "")}" width="70" height="70" style="border-radius:50%; object-fit:cover; border: 2px solid #fbbf24;">' if s_data.get('photo') else '<div style="width:70px; height:70px; background:rgba(255,255,255,0.1); border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:35px; border: 2px solid #fbbf24;">👤</div>'
                    
                    card_html = f"""<div class="digital-card">
{club_logo_tag}
<h3 style="margin:0; font-size: 16px; color: white;">{st.session_state.club_name}</h3>
<p style="margin:2px 0 15px 0; font-size: 10px; color: rgba(255,255,255,0.6);">کارت هوشمند هواداری و عضویت</p>
<div style="display: flex; align-items: center; gap: 15px; margin-top: 20px;">
    {student_photo_tag}
    <div>
        <h4 style="margin: 0; font-size: 18px; color: white;">{s_data['name']}</h4>
        <p style="margin: 4px 0 0 0; font-size: 12px; color: #fbbf24;">رشته: {s_data['specialty']}</p>
    </div>
</div>
<div style="margin-top: 20px; font-size: 11px; border-top: 1px dashed rgba(255,255,255,0.2); padding-top: 15px; display:flex; justify-content:space-between;">
    <div>
        <b>کد ملی:</b> {to_persian_digits(s_data['nationalId'])}<br>
        <div style="margin-top: 5px;"><b>نام پدر:</b> {s_data['fatherName']}</div>
    </div>
    <div style="text-align:left;">
        <b>مربی:</b> {coach_name}<br>
        <div style="margin-top: 5px;"><b>تلفن مربی:</b> <span dir="ltr">{to_persian_digits(coach_phone)}</span></div>
    </div>
</div>
</div>"""
                    st.markdown(card_html, unsafe_allow_html=True)

        # ----------------------------------------------------------------------
        # SPECIALTIES MANAGEMENT
        # ----------------------------------------------------------------------
        elif selection == "specialties":
            st.title("🎯 مدیریت رشته‌های ورزشی")
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown("### افزودن رشته جدید")
                with st.form("add_spec_form", clear_on_submit=True):
                    new_spec_name = st.text_input("نام رشته ورزشی:")
                    if st.form_submit_button("ثبت رشته جدید"):
                        if new_spec_name:
                            new_id = f'sp-{int(time.time())}'
                            supabase.table('specialties').insert({'id': new_id, 'name': new_spec_name}).execute()
                            st.session_state.specialties.append({'id': new_id, 'name': new_spec_name})
                            st.success(f"رشته {new_spec_name} اضافه شد.")
                            st.rerun()
            with col2:
                st.markdown("### رشته‌های موجود (حذف و ویرایش)")
                for sp in st.session_state.specialties:
                    c1, c2 = st.columns([3, 1])
                    c1.info(f"🔹 {sp['name']}")
                    if c2.button("❌ حذف", key=f"del_sp_{sp['id']}"):
                        supabase.table('specialties').delete().eq('id', sp['id']).execute()
                        st.session_state.specialties = [s for s in st.session_state.specialties if s['id'] != sp['id']]
                        st.rerun()

        # ----------------------------------------------------------------------
        # COACHES (EDIT / ADD / DELETE)
        # ----------------------------------------------------------------------
        elif selection == "coaches":
            st.title("👔 مدیریت مربیان و اساتید")
            
            tab_list, tab_add = st.tabs(["لیست و ویرایش مربیان", "ثبت مربی جدید"])
            
            with tab_list:
                for coach in st.session_state.coaches:
                    st_count = len([s for s in st.session_state.students if s['coachId'] == coach['id']])
                    img_tag = f'<img src="data:image/png;base64,{coach["logo"]}" width="50" height="50" style="border-radius:50%; margin-left:15px; float:right; object-fit:cover;">' if coach.get("logo") else '<div style="width:50px; height:50px; background:#e2e8f0; border-radius:50%; float:right; margin-left:15px; text-align:center; line-height:50px; font-size:24px;">👤</div>'
                    st.markdown(f"""
                    <div style='background-color: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 15px; margin-bottom: 12px;'>
                        {img_tag}
                        <h4 style='margin:0; color:#1e293b;'>{coach['name']}</h4>
                        <div style='font-size:12px; color:#475569; margin-top:5px; line-height: 1.6;'>
                            <b>رشته:</b> {coach['specialty']} | 👥 <b>هنرجویان:</b> {to_persian_digits(st_count)} نفر<br>
                            <b>روز و ساعت کلاس:</b> {coach.get('schedule', '---')} | 🔑 <b>نام کاربری:</b> {coach.get('username', 'تعریف نشده')}
                        </div>
                        <div style="clear:both;"></div>
                    </div>
                    """, unsafe_allow_html=True)
                
                if st.session_state.coaches:
                    st.markdown("---")
                    st.markdown("#### ✏️ ویرایش یا حذف مربی")
                    selected_coach_id = st.selectbox("انتخاب مربی جهت ویرایش یا حذف:", options=[c['id'] for c in st.session_state.coaches], format_func=lambda x: next(c['name'] for c in st.session_state.coaches if c['id'] == x))
                    c_idx = next(i for i, c in enumerate(st.session_state.coaches) if c['id'] == selected_coach_id)
                    cur_coach = st.session_state.coaches[c_idx]
                    
                    with st.form("edit_coach_form"):
                        ecol1, ecol2 = st.columns(2)
                        with ecol1:
                            e_c_name = st.text_input("نام و نام خانوادگی:", value=cur_coach.get('name', ''))
                            e_c_phone = st.text_input("شماره همراه:", value=cur_coach.get('phone', ''))
                            e_c_username = st.text_input("نام کاربری مربی:", value=cur_coach.get('username', ''))
                        with ecol2:
                            s_opts = active_specialties_names if active_specialties_names else ["نامشخص"]
                            s_idx = s_opts.index(cur_coach['specialty']) if cur_coach.get('specialty') in s_opts else 0
                            e_c_spec = st.selectbox("رشته تخصصی:", options=s_opts, index=s_idx)
                            e_c_schedule = st.text_input("روزها و ساعات کلاس:", value=cur_coach.get('schedule', ''))
                            e_c_password = st.text_input("رمز عبور:", value=cur_coach.get('password', ''))
                            
                        e_c_logo = st.file_uploader("عکس/لوگوی جدید مربی (آپلود مجدد جایگزین قبلی می‌شود)", type=['png', 'jpg', 'jpeg'])
                        
                        sub_edit, sub_del = st.columns([1, 1])
                        with sub_edit:
                            if st.form_submit_button("💾 ذخیره تغییرات", type="primary"):
                                final_logo = image_to_base64(e_c_logo) if e_c_logo else cur_coach.get('logo', '')
                                updates = {
                                    'name': e_c_name, 'phone': e_c_phone, 'specialty': e_c_spec,
                                    'schedule': e_c_schedule, 'logo': final_logo, 'username': e_c_username, 'password': e_c_password
                                }
                                supabase.table('coaches').update(updates).eq('id', cur_coach['id']).execute()
                                st.session_state.coaches[c_idx].update(updates)
                                st.success("اطلاعات مربی با موفقیت ویرایش شد.")
                                time.sleep(1)
                                st.rerun()
                        with sub_del:
                            if st.form_submit_button("❌ حذف مربی"):
                                supabase.table('coaches').delete().eq('id', cur_coach['id']).execute()
                                st.session_state.coaches.pop(c_idx)
                                st.warning("مربی حذف شد.")
                                time.sleep(1)
                                st.rerun()
                                
            with tab_add:
                with st.form("add_coach_form", clear_on_submit=True):
                    col_a1, col_a2 = st.columns(2)
                    with col_a1:
                        c_name = st.text_input("نام و نام خانوادگی:")
                        c_phone = st.text_input("شماره همراه:")
                        c_username = st.text_input("نام کاربری (جهت ورود مربی):")
                    with col_a2:
                        c_spec = st.selectbox("رشته تخصصی:", active_specialties_names if active_specialties_names else ["نامشخص"])
                        c_schedule = st.text_input("روزها و ساعات کلاس (مثال: روزهای زوج ۱۸ الی ۲۰):")
                        c_password = st.text_input("رمز عبور:")
                        
                    c_logo = st.file_uploader("عکس/لوگو", type=['png', 'jpg', 'jpeg'])
                    
                    if st.form_submit_button("ثبت مربی"):
                        logo_b64 = image_to_base64(c_logo)
                        new_c = {'id': f'c-{int(time.time())}', 'name': c_name, 'phone': c_phone, 'specialty': c_spec, 'nationalId': '', 'salaryType': 'percentage', 'salaryValue': 50, 'status': 'فعال', 'joinDate': TODAY_JALALI, 'logo': logo_b64, 'schedule': c_schedule, 'username': c_username, 'password': c_password}
                        supabase.table('coaches').insert(new_c).execute()
                        st.session_state.coaches.append(new_c)
                        st.success("مربی جدید اضافه شد.")
                        time.sleep(1)
                        st.rerun()

        # ----------------------------------------------------------------------
        # ATTENDANCE 
        # ----------------------------------------------------------------------
        elif selection == "attendance":
            st.title("📋 سامانه حضور و غیاب هوشمند")
            tab_reg, tab_hist = st.tabs(["ثبت حضور و غیاب امروز", "سوابق حضور و غیاب"])
            
            with tab_reg:
                if not active_specialties_names:
                    st.warning("ابتدا یک رشته ورزشی تعریف کنید.")
                else:
                    col_sp, col_dt = st.columns(2)
                    with col_sp:
                        selected_spec = st.selectbox("انتخاب کلاس (رشته):", active_specialties_names)
                    with col_dt:
                        selected_date = st.text_input("تاریخ (جلالی):", value=TODAY_JALALI)
                    
                    class_students = [s for s in st.session_state.students if s['specialty'] == selected_spec and s['status'] == 'فعال']
                    
                    if not class_students:
                        st.info(f"هنرجوی فعالی در رشته {selected_spec} یافت نشد.")
                    else:
                        exist_rec = next((r for r in st.session_state.attendance if r['date'] == selected_date and r['specialty'] == selected_spec), None)
                        initial_present = exist_rec['presentStudentIds'] if exist_rec else []
                        
                        st.markdown(f"#### لیست هنرجویان کلاس ({to_persian_digits(len(class_students))} نفر)")
                        st.markdown("افراد حاضر در کلاس را تیک بزنید:")
                        
                        present_list = []
                        for s in class_students:
                            if st.checkbox(s['name'], value=(s['id'] in initial_present), key=f"att_{s['id']}"):
                                present_list.append(s['id'])
                                
                        if st.button("💾 ذخیره لیست حاضرین", type="primary"):
                            if exist_rec:
                                supabase.table('attendance').update({'presentStudentIds': json.dumps(present_list)}).eq('id', exist_rec['id']).execute()
                                exist_rec['presentStudentIds'] = present_list
                            else:
                                new_att = {'id': f'att-{int(time.time())}', 'date': selected_date, 'specialty': selected_spec, 'presentStudentIds': present_list}
                                # Supabase needs list as JSON string if column is text
                                db_att = new_att.copy()
                                db_att['presentStudentIds'] = json.dumps(present_list)
                                supabase.table('attendance').insert(db_att).execute()
                                st.session_state.attendance.append(new_att)
                            st.success("حضور و غیاب با موفقیت ثبت شد.")
                            time.sleep(1)
                            st.rerun()

            with tab_hist:
                if not st.session_state.attendance:
                    st.info("هیچ سابقه حضور و غیابی یافت نشد.")
                else:
                    sorted_att = sorted(st.session_state.attendance, key=lambda x: x['date'], reverse=True)
                    for att in sorted_att:
                        present_names = [next((s['name'] for s in st.session_state.students if s['id'] == sid), "نامشخص") for sid in att['presentStudentIds']]
                        st.markdown(f"""
                        <div style='background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-bottom: 10px;'>
                            <b>{att['specialty']}</b> | تاریخ: {to_persian_digits(att['date'])}<br/>
                            <span style='font-size:12px; color:#475569;'>حاضرین ({to_persian_digits(len(present_names))} نفر): {', '.join(present_names) if present_names else 'کسی حاضر نبود'}</span>
                        </div>
                        """, unsafe_allow_html=True)

        # ----------------------------------------------------------------------
        # TUITION (FINANCIALS)
        # ----------------------------------------------------------------------
        elif selection == "tuition":
            st.title("💳 امور مالی و خزانه‌داری")
            tab_tuition, tab_pay = st.tabs(["گردش حساب", "ثبت فیش و تمدید"])
            with tab_tuition:
                if st.session_state.tuitions:
                    df_tu = pd.DataFrame(st.session_state.tuitions)
                    df_tu['هنرجو'] = df_tu['studentId'].apply(lambda x: next((s['name'] for s in st.session_state.students if s['id'] == x), "نامشخص"))
                    st.dataframe(df_tu[['هنرجو', 'amount', 'payDate', 'expiryDate', 'paymentMethod']], use_container_width=True, hide_index=True)
                else:
                    st.info("تاکنون تراکنشی ثبت نشده است.")
            with tab_pay:
                with st.form("pay_form", clear_on_submit=True):
                    active_st = [s for s in st.session_state.students if s['status'] == 'فعال']
                    if active_st:
                        pay_st_id = st.selectbox("انتخاب هنرجو:", options=[s['id'] for s in active_st], format_func=lambda x: next(s['name'] for s in active_st if s['id'] == x))
                        pay_amount = st.number_input("مبلغ پرداختی (ریال):", min_value=0, value=600000)
                        pay_expiry = st.text_input("سررسید شهریه جدید:", value="1405/05/11")
                        if st.form_submit_button("ثبت فیش و تمدید"):
                            new_t = {'id': f't-{int(time.time())}', 'studentId': pay_st_id, 'amount': int(pay_amount), 'payDate': TODAY_JALALI, 'expiryDate': pay_expiry, 'paymentMethod': 'کارت خوان', 'notes': ''}
                            supabase.table('tuitions').insert(new_t).execute()
                            supabase.table('students').update({'tuitionExpiry': pay_expiry}).eq('id', pay_st_id).execute()
                            
                            st.session_state.tuitions.append(new_t)
                            st_idx = next(i for i, s in enumerate(st.session_state.students) if s['id'] == pay_st_id)
                            st.session_state.students[st_idx]['tuitionExpiry'] = pay_expiry
                            st.success("فیش ثبت و شهریه تمدید شد.")
                            st.rerun()

        # ----------------------------------------------------------------------
        # SMS SYSTEM
        # ----------------------------------------------------------------------
        elif selection == "sms":
            st.title("💬 سامانه اطلاع‌رسانی پیامک")
            col_send, col_logs = st.columns([1, 1])
            
            with col_send:
                st.markdown("### ارسال پیامک جدید")
                if st.session_state.students:
                    sms_st_id = st.selectbox("گیرنده پیامک:", options=[s['id'] for s in st.session_state.students], format_func=lambda x: next(s['name'] for s in st.session_state.students if s['id'] == x))
                    st_info = next(s for s in st.session_state.students if s['id'] == sms_st_id)
                    
                    selected_temp_id = st.selectbox("قالب آماده پیامک:", options=[t['id'] for t in st.session_state.sms_templates], format_func=lambda x: next(t['title'] for t in st.session_state.sms_templates if t['id'] == x))
                    template_text = next(t['text'] for t in st.session_state.sms_templates if t['id'] == selected_temp_id)
                    
                    custom_msg = template_text.replace("[نام]", st_info['name']).replace("[تاریخ]", to_persian_digits(st_info.get('tuitionExpiry', '---')))
                    
                    sms_text = st.text_area("متن نهایی پیامک:", value=custom_msg, height=120)
                    
                    if st.button("✉️ ارسال پیامک", type="primary"):
                        new_log = {
                            'id': f'sms-{int(time.time())}',
                            'recipientName': st_info['name'],
                            'recipientPhone': st_info['phone'],
                            'messageText': sms_text,
                            'date': f"{TODAY_JALALI} {datetime.now().strftime('%H:%M')}"
                        }
                        supabase.table('sms_logs').insert(new_log).execute()
                        st.session_state.sms_logs.insert(0, new_log)
                        st.success(f"پیامک به {st_info['name']} ({st_info['phone']}) با موفقیت ارسال شد.")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.warning("هنوز هنرجویی ثبت نشده است.")
                    
            with col_logs:
                st.markdown("### گزارش پیامک‌های ارسالی")
                if not st.session_state.sms_logs:
                    st.info("تاکنون پیامکی ارسال نشده است.")
                else:
                    for log in st.session_state.sms_logs[:10]:
                        st.markdown(f"""
                        <div style='background-color: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 10px;'>
                            <div style='font-size:11px; color:#475569; display:flex; justify-content:space-between;'>
                                <b>{log['recipientName']} ({log['recipientPhone']})</b> <span>{to_persian_digits(log['date'])}</span>
                            </div>
                            <div style='margin-top:5px; font-size:12px; color:#1e293b; background:#f1f5f9; padding:5px; border-radius:5px;'>
                                {log['messageText']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

        # ----------------------------------------------------------------------
        # EVENTS
        # ----------------------------------------------------------------------
        elif selection == "events":
            st.title("📅 تقویم رویدادها")
            with st.form("event_form", clear_on_submit=True):
                ev_title = st.text_input("عنوان رویداد:")
                ev_date = st.text_input("تاریخ:", value="1405/05/15")
                ev_loc = st.text_input("محل برگزاری:")
                if st.form_submit_button("ثبت رویداد"):
                    new_ev = {'id': f'ev-{int(time.time())}', 'title': ev_title, 'date': ev_date, 'time': '10:00', 'location': ev_loc, 'type': 'match'}
                    supabase.table('events').insert(new_ev).execute()
                    st.session_state.events.append(new_ev)
                    st.success("رویداد ذخیره شد.")
                    st.rerun()
                    
        # ----------------------------------------------------------------------
        # SETTINGS (CLUB NAME, LOGO, ADMIN CREDS)
        # ----------------------------------------------------------------------
        elif selection == "settings":
            st.title("⚙️ تنظیمات سیستم")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown("### آپلود لوگوی باشگاه")
                if st.session_state.club_logo:
                    st.markdown(f'<img src="data:image/png;base64,{st.session_state.club_logo}" width="150" style="border-radius:10px; margin-bottom:15px;">', unsafe_allow_html=True)
                with st.form("logo_form"):
                    club_logo_file = st.file_uploader("انتخاب فایل لوگو (PNG/JPG)", type=['png', 'jpg', 'jpeg'])
                    if st.form_submit_button("ذخیره لوگو"):
                        if club_logo_file:
                            b64_logo = image_to_base64(club_logo_file)
                            supabase.table('club_settings').upsert({'key': 'club_logo', 'value': b64_logo}).execute()
                            st.session_state.club_logo = b64_logo
                            st.rerun()
            with col2:
                st.markdown("### نام و برند باشگاه")
                with st.form("name_form"):
                    new_club_name = st.text_input("نام باشگاه:", value=st.session_state.club_name)
                    if st.form_submit_button("ذخیره نام"):
                        supabase.table('club_settings').upsert({'key': 'club_name', 'value': new_club_name}).execute()
                        st.session_state.club_name = new_club_name
                        st.rerun()
                        
            st.divider()
            
            st.markdown("### 🔐 تنظیمات حساب کاربری مدیریت")
            with st.form("admin_credentials_form"):
                col3, col4 = st.columns(2)
                with col3:
                    new_user = st.text_input("نام کاربری جدید:", value=st.session_state.admin_username)
                with col4:
                    new_pass = st.text_input("رمز عبور جدید:", type="password", value=st.session_state.admin_password)
                
                if st.form_submit_button("ذخیره اطلاعات ورود"):
                    supabase.table('club_settings').upsert({'key': 'admin_username', 'value': new_user}).execute()
                    supabase.table('club_settings').upsert({'key': 'admin_password', 'value': new_pass}).execute()
                    st.session_state.admin_username = new_user
                    st.session_state.admin_password = new_pass
                    st.success("اطلاعات ورود با موفقیت تغییر کرد. لطفا در ورود بعدی از این اطلاعات استفاده نمایید.")
                    time.sleep(2)
                    st.rerun()
                    
            st.divider()
            
            if st.button("🚪 خروج از مدیریت", type="primary"):
                st.session_state.logged_in = False
                st.rerun()
