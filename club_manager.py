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
st.set_page_config(page_title="سیستم یکپارچه مدیریت باشگاه", page_icon="🥋", layout="wide", initial_sidebar_state="expanded")

rtl_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;700;900&display=swap');
    html, body, [data-testid="stSidebar"], .stApp, .stMarkdown, p, h1, h2, h3, h4, h5, h6, label, button, select, input, div, span, textarea {
        font-family: 'Vazirmatn', sans-serif !important;
        direction: rtl !important;
        text-align: right !important;
    }
    [data-testid="stSidebar"], [data-testid="stSidebarNav"], .stTextInput, .stSelectbox, .stTextArea, .stNumberInput, .stDateInput, .stFileUploader {
        direction: rtl !important;
        text-align: right !important;
    }
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"], [data-testid="stMetricDelta"] {
        text-align: right !important;
        direction: rtl !important;
    }
    .digital-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: white; border-radius: 20px; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        max-width: 450px; margin: 10px auto; position: relative; overflow: hidden; border: 1px solid rgba(255,255,255,0.1);
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

supabase: Client = init_connection()

# ==============================================================================
# HELPER FUNCTIONS & DATA LOADING
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

# Load DB into session_state
if 'db_loaded' not in st.session_state:
    res_settings = supabase.table('club_settings').select('*').execute().data
    settings_dict = {r['key']: r['value'] for r in res_settings}
    
    st.session_state.club_name = settings_dict.get('club_name', 'باشگاه ورزشی المپیک')
    if 'club_name' not in settings_dict:
        supabase.table('club_settings').insert({'key': 'club_name', 'value': st.session_state.club_name}).execute()
        
    st.session_state.club_logo = settings_dict.get('club_logo', '')
    st.session_state.admin_username = settings_dict.get('admin_username', 'admin')
    st.session_state.admin_password = settings_dict.get('admin_password', '1234')

    for table in ['specialties', 'students', 'coaches', 'tuitions', 'events', 'sms_logs']:
        st.session_state[table] = supabase.table(table).select('*').execute().data
        
    if not st.session_state.specialties:
        default_specs = [{'id': 'sp-1', 'name': 'هاپکیدو'}, {'id': 'sp-2', 'name': 'تکواندو'}, {'id': 'sp-3', 'name': 'کاراته'}, {'id': 'sp-4', 'name': 'دفاع شخصی'}]
        supabase.table('specialties').insert(default_specs).execute()
        st.session_state.specialties = default_specs

    att_data = supabase.table('attendance').select('*').execute().data
    st.session_state.attendance = []
    for row in att_data:
        row['presentStudentIds'] = json.loads(row['presentStudentIds']) if isinstance(row['presentStudentIds'], str) else row['presentStudentIds']
        st.session_state.attendance.append(row)
        
    st.session_state.sms_templates = [
        {'id': 't1', 'title': 'یادآور شهریه', 'text': 'هنرجوی گرامی [نام]، مهلت شهریه شما در تاریخ [تاریخ] به پایان رسیده است. لطفا تمدید نمایید.'},
        {'id': 't2', 'title': 'یادآور بیمه', 'text': 'هنرجوی عزیز [نام]، مهلت اعتبار بیمه ورزشی شما پایان می‌یابد.'}
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
view_mode = st.sidebar.radio("مسیر کاربری", ["📝 فرم ثبت‌نام عمومی", "🔐 ورود به پنل مدیریت"])
st.sidebar.divider()
st.sidebar.info(f"📅 تاریخ: {to_persian_digits(TODAY_JALALI)}")

# ==============================================================================
# PUBLIC VIEW: REGISTRATION FORM
# ==============================================================================
if view_mode == "📝 فرم ثبت‌نام عمومی":
    col_t1, col_t2 = st.columns([1, 4])
    with col_t1:
        if st.session_state.club_logo:
            st.markdown(f'<img src="data:image/png;base64,{st.session_state.club_logo}" width="100" style="border-radius:10px;">', unsafe_allow_html=True)
    with col_t2:
        st.title(f"ثبت‌نام در {st.session_state.club_name}")
        st.markdown("جهت شروع فرآیند ثبت‌نام، فرم زیر را تکمیل نمایید.")
        
    st.divider()
    st.markdown("### 🗓️ برنامه زمان‌بندی کلاس‌ها")
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
                            <b>رشته:</b> {coach['specialty']}<br><b>⏰ زمان:</b> {coach.get('schedule', 'نامشخص')}<br><b>📞 تماس:</b> <span dir="ltr">{to_persian_digits(coach.get('phone', '---'))}</span>
                        </div>
                    </div><div style="clear:both;"></div>
                </div>""", unsafe_allow_html=True)
    else:
        st.warning("برنامه کلاسی ثبت نشده است.")
        
    st.divider()
    st.markdown("### 📋 فرم اطلاعات هنرجو")
    with st.form("public_registration", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("نام و نام خانوادگی:")
            fatherName = st.text_input("نام پدر:")
            national_id = st.text_input("کد ملی:")
            birthDate = st.text_input("تاریخ تولد:")
            s_photo_public = st.file_uploader("عکس پرسنلی:", type=['png', 'jpg', 'jpeg'])
        with col2:
            phone = st.text_input("شماره همراه:")
            coach_opts = st.session_state.coaches
            selected_coach_id = st.selectbox("مربی کلاس:", options=[""] + [c['id'] for c in coach_opts], format_func=lambda x: next((c['name'] for c in coach_opts if c['id'] == x), "--- انتخاب کنید ---"))
            specialty = st.selectbox("رشته ورزشی:", active_specialties_names if active_specialties_names else ["نامشخص"])
            address = st.text_area("آدرس:", height=130)
            
        if st.form_submit_button("ثبت نهایی اطلاعات", type="primary"):
            if not name or not phone or not national_id:
                st.error("فیلدهای نام، شماره و کدملی اجباری است.")
            else:
                new_s = {
                    'id': f's-{int(time.time())}', 'name': name, 'fatherName': fatherName, 'birthDate': birthDate,
                    'phone': phone, 'nationalId': national_id, 'address': address, 'coachId': selected_coach_id, 
                    'specialty': specialty, 'status': 'در انتظار تایید', 'insuranceExpiry': '', 'tuitionExpiry': '', 
                    'joinDate': TODAY_JALALI, 'photo': image_to_base64(s_photo_public)
                }
                supabase.table('students').insert(new_s).execute()
                st.session_state.students.append(new_s)
                st.success("ثبت‌نام با موفقیت انجام شد.")
                st.balloons()

# ==============================================================================
# ADMIN VIEW
# ==============================================================================
elif view_mode == "🔐 ورود به پنل مدیریت":
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.subheader("ورود مدیریت")
        with st.form("login_form"):
            username = st.text_input("نام کاربری:")
            password = st.text_input("رمز عبور:", type="password")
            if st.form_submit_button("ورود"):
                if username == st.session_state.admin_username and password == st.session_state.admin_password:
                    st.session_state.logged_in = True
                    st.rerun()
                else: st.error("نام کاربری یا رمز عبور اشتباه است.")
    else:
        menu = {"dashboard": "📊 پیشخوان", "students": "👥 هنرجویان", "specialties": "🎯 رشته‌های ورزشی", "coaches": "👔 مربیان", "attendance": "📋 حضور و غیاب", "tuition": "💳 امور مالی", "sms": "💬 پیامک", "events": "📅 رویدادها", "settings": "⚙️ تنظیمات"}
        selection = st.sidebar.radio("بخش‌ها:", options=list(menu.keys()), format_func=lambda x: menu[x])

        if selection == "dashboard":
            st.title("📊 پیشخوان")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("کل ثبت‌نامی‌ها", len(st.session_state.students), f"فعال: {len([s for s in st.session_state.students if s['status'] == 'فعال'])}")
            col2.metric("مربیان", len(st.session_state.coaches))
            col3.metric("درآمد کل", f"{sum([t['amount'] for t in st.session_state.tuitions]):,} ریال")
            col4.metric("شهریه‌های منقضی", len([s for s in st.session_state.students if s['tuitionExpiry'] < TODAY_JALALI and s['status'] == 'فعال']), delta_color="inverse")

        elif selection == "students":
            st.title("👥 مدیریت هنرجویان")
            tab_list, tab_add, tab_excel, tab_card = st.tabs(["لیست و ویرایش", "ثبت هنرجو", "📥 ورود از اکسل", "صدور کارت"])
            
            with tab_list:
                if st.session_state.students:
                    df = pd.DataFrame(st.session_state.students)[['id', 'name', 'fatherName', 'phone', 'specialty', 'status', 'tuitionExpiry']]
                    df.columns = ['شناسه', 'نام', 'پدر', 'تلفن', 'رشته', 'وضعیت', 'سررسید شهریه']
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.markdown("#### ✏️ ویرایش هنرجو")
                    sel_id = st.selectbox("انتخاب:", options=[s['id'] for s in st.session_state.students], format_func=lambda x: next(s['name'] for s in st.session_state.students if s['id'] == x))
                    s_idx = next(i for i, s in enumerate(st.session_state.students) if s['id'] == sel_id)
                    cur = st.session_state.students[s_idx]
                    
                    with st.form("edit_student"):
                        c1, c2 = st.columns(2)
                        with c1:
                            e_name = st.text_input("نام:", value=cur.get('name', ''))
                            e_father = st.text_input("پدر:", value=cur.get('fatherName', ''))
                            e_nid = st.text_input("کدملی:", value=cur.get('nationalId', ''))
                            e_birth = st.text_input("تولد:", value=cur.get('birthDate', ''))
                            e_photo = st.file_uploader("عکس", type=['png', 'jpg'])
                        with c2:
                            e_phone = st.text_input("موبایل:", value=cur.get('phone', ''))
                            c_opts = st.session_state.coaches
                            c_idx_opt = [c['id'] for c in c_opts].index(cur['coachId']) + 1 if cur.get('coachId') and any(c['id'] == cur['coachId'] for c in c_opts) else 0
                            e_coach = st.selectbox("مربی:", options=[""] + [c['id'] for c in c_opts], index=c_idx_opt, format_func=lambda x: next((c['name'] for c in c_opts if c['id'] == x), "---"))
                            s_opts = active_specialties_names if active_specialties_names else ["نامشخص"]
                            s_idx_opt = s_opts.index(cur['specialty']) if cur.get('specialty') in s_opts else 0
                            e_spec = st.selectbox("رشته:", options=s_opts, index=s_idx_opt)
                            e_address = text_input = st.text_area("آدرس:", value=cur.get('address', ''))
                            
                        c3, c4, c5 = st.columns(3)
                        with c3: e_ins = st.text_input("انقضای بیمه:", value=cur.get('insuranceExpiry', ''))
                        with c4: e_tui = st.text_input("انقضای شهریه:", value=cur.get('tuitionExpiry', ''))
                        with c5: e_status = st.selectbox("وضعیت:", options=["فعال", "غیرفعال", "در انتظار تایید"], index=["فعال", "غیرفعال", "در انتظار تایید"].index(cur.get('status', 'فعال')))
                            
                        sub_edit, sub_del = st.columns(2)
                        with sub_edit:
                            if st.form_submit_button("💾 ذخیره تغییرات", type="primary"):
                                final_photo = image_to_base64(e_photo) if e_photo else cur.get('photo', '')
                                updates = {'name': e_name, 'fatherName': e_father, 'nationalId': e_nid, 'birthDate': e_birth, 'phone': e_phone, 'coachId': e_coach, 'specialty': e_spec, 'address': e_address, 'insuranceExpiry': e_ins, 'tuitionExpiry': e_tui, 'status': e_status, 'photo': final_photo}
                                supabase.table('students').update(updates).eq('id', cur['id']).execute()
                                st.session_state.students[s_idx].update(updates)
                                st.success("ویرایش شد.")
                                st.rerun()
                        with sub_del:
                            if st.form_submit_button("❌ حذف هنرجو"):
                                supabase.table('students').delete().eq('id', cur['id']).execute()
                                st.session_state.students.pop(s_idx)
                                st.warning("حذف شد.")
                                st.rerun()

            with tab_add:
                with st.form("add_student"):
                    st.info("فیلدهای مورد نیاز را پر کنید.")
                    name = st.text_input("نام:")
                    phone = st.text_input("موبایل:")
                    specialty = st.selectbox("رشته:", active_specialties_names if active_specialties_names else ["نامشخص"])
                    if st.form_submit_button("ثبت‌نام"):
                        new_s = {'id': f's-{int(time.time())}', 'name': name, 'fatherName': '', 'birthDate': '', 'phone': phone, 'nationalId': '', 'address': '', 'coachId': '', 'specialty': specialty, 'status': 'فعال', 'insuranceExpiry': '', 'tuitionExpiry': '', 'joinDate': TODAY_JALALI, 'photo': ''}
                        supabase.table('students').insert(new_s).execute()
                        st.session_state.students.append(new_s)
                        st.success("ثبت شد.")
                        st.rerun()

            with tab_excel:
                uploaded_excel = st.file_uploader("فایل اکسل (.xlsx)", type=['xlsx'])
                if uploaded_excel and st.button("شروع انتقال", type="primary"):
                    df_import = pd.read_excel(uploaded_excel)
                    for index, row in df_import.iterrows():
                        if not pd.isna(row.get('نام و نام خانوادگی')):
                            new_s = {'id': f's-{int(time.time()*1000)+index}', 'name': str(row.get('نام و نام خانوادگی', '')), 'fatherName': str(row.get('نام پدر', '')), 'birthDate': '', 'phone': str(row.get('شماره همراه', '')), 'nationalId': str(row.get('کد ملی', '')), 'address': '', 'coachId': '', 'specialty': str(row.get('رشته ورزشی', 'نامشخص')), 'status': 'فعال', 'insuranceExpiry': '', 'tuitionExpiry': '', 'joinDate': TODAY_JALALI, 'photo': ''}
                            supabase.table('students').insert(new_s).execute()
                            st.session_state.students.append(new_s)
                    st.success("اطلاعات وارد سیستم شد.")
                    st.rerun()

            with tab_card:
                if st.session_state.students:
                    sel_card = st.selectbox("صدور کارت هنرجو:", options=[s['id'] for s in st.session_state.students], format_func=lambda x: next(s['name'] for s in st.session_state.students if s['id'] == x))
                    s_data = next(s for s in st.session_state.students if s['id'] == sel_card)
                    coach_name = next((c['name'] for c in st.session_state.coaches if c['id'] == s_data.get('coachId')), "نامشخص")
                    coach_phone = next((c['phone'] for c in st.session_state.coaches if c['id'] == s_data.get('coachId')), "---")
                    logo_tag = f'<img src="data:image/png;base64,{st.session_state.club_logo}" width="50" style="position: absolute; left: 20px; top: 20px; border-radius: 8px;">' if st.session_state.club_logo else ''
                    photo_tag = f'<img src="data:image/png;base64,{s_data.get("photo", "")}" width="70" height="70" style="border-radius:50%; object-fit:cover; border: 2px solid #fbbf24;">' if s_data.get('photo') else '<div style="width:70px; height:70px; background:rgba(255,255,255,0.1); border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:35px; border: 2px solid #fbbf24;">👤</div>'
                    
                    st.markdown(f"""<div class="digital-card">{logo_tag}<h3 style="margin:0; font-size: 16px; color: white;">{st.session_state.club_name}</h3><p style="margin:2px 0 15px 0; font-size: 10px; color: rgba(255,255,255,0.6);">کارت هوشمند هواداری و عضویت</p><div style="display: flex; align-items: center; gap: 15px; margin-top: 20px;">{photo_tag}<div><h4 style="margin: 0; font-size: 18px; color: white;">{s_data['name']}</h4><p style="margin: 4px 0 0 0; font-size: 12px; color: #fbbf24;">رشته: {s_data['specialty']}</p></div></div><div style="margin-top: 20px; font-size: 11px; border-top: 1px dashed rgba(255,255,255,0.2); padding-top: 15px; display:flex; justify-content:space-between;"><div><b>کد ملی:</b> {to_persian_digits(s_data['nationalId'])}<br><div style="margin-top: 5px;"><b>نام پدر:</b> {s_data['fatherName']}</div></div><div style="text-align:left;"><b>مربی:</b> {coach_name}<br><div style="margin-top: 5px;"><b>تلفن مربی:</b> <span dir="ltr">{to_persian_digits(coach_phone)}</span></div></div></div></div>""", unsafe_allow_html=True)

        elif selection == "specialties":
            st.title("🎯 مدیریت رشته‌ها")
            c1, c2 = st.columns(2)
            with c1:
                new_spec = st.text_input("نام رشته جدید:")
                if st.button("ثبت رشته"):
                    new_id = f'sp-{int(time.time())}'
                    supabase.table('specialties').insert({'id': new_id, 'name': new_spec}).execute()
                    st.session_state.specialties.append({'id': new_id, 'name': new_spec})
                    st.rerun()
            with c2:
                for sp in st.session_state.specialties:
                    st.info(f"🔹 {sp['name']}")

        elif selection == "coaches":
            st.title("👔 مدیریت مربیان")
            t_list, t_add = st.tabs(["لیست و ویرایش", "ثبت مربی"])
            with t_list:
                for c in st.session_state.coaches:
                    st.info(f"**{c['name']}** (رشته: {c['specialty']}) - زمان: {c.get('schedule', '---')}")
                if st.session_state.coaches:
                    sel_c = st.selectbox("ویرایش مربی:", options=[c['id'] for c in st.session_state.coaches], format_func=lambda x: next(c['name'] for c in st.session_state.coaches if c['id'] == x))
                    c_idx = next(i for i, c in enumerate(st.session_state.coaches) if c['id'] == sel_c)
                    cur_c = st.session_state.coaches[c_idx]
                    with st.form("edit_c"):
                        en = st.text_input("نام:", value=cur_c['name'])
                        if st.form_submit_button("💾 ذخیره"):
                            supabase.table('coaches').update({'name': en}).eq('id', cur_c['id']).execute()
                            st.session_state.coaches[c_idx]['name'] = en
                            st.rerun()
            with t_add:
                with st.form("add_c"):
                    cn = st.text_input("نام:")
                    cs = st.text_input("زمان کلاس:")
                    cp = st.text_input("شماره:")
                    csp = st.selectbox("رشته:", active_specialties_names if active_specialties_names else ["نامشخص"])
                    cl = st.file_uploader("عکس", type=['png', 'jpg'])
                    if st.form_submit_button("ثبت مربی"):
                        new_c = {'id': f'c-{int(time.time())}', 'name': cn, 'phone': cp, 'specialty': csp, 'nationalId': '', 'salaryType': 'percentage', 'salaryValue': 50, 'status': 'فعال', 'joinDate': TODAY_JALALI, 'logo': image_to_base64(cl), 'schedule': cs, 'username': '', 'password': ''}
                        supabase.table('coaches').insert(new_c).execute()
                        st.session_state.coaches.append(new_c)
                        st.rerun()

        elif selection == "attendance":
            st.title("📋 حضور و غیاب")
            if active_specialties_names:
                sel_sp = st.selectbox("کلاس:", active_specialties_names)
                sel_dt = st.text_input("تاریخ:", value=TODAY_JALALI)
                cls_sts = [s for s in st.session_state.students if s['specialty'] == sel_sp and s['status'] == 'فعال']
                exist = next((r for r in st.session_state.attendance if r['date'] == sel_dt and r['specialty'] == sel_sp), None)
                init_p = exist['presentStudentIds'] if exist else []
                p_list = []
                for s in cls_sts:
                    if st.checkbox(s['name'], value=(s['id'] in init_p)): p_list.append(s['id'])
                if st.button("ذخیره حضور و غیاب", type="primary"):
                    if exist:
                        supabase.table('attendance').update({'presentStudentIds': json.dumps(p_list)}).eq('id', exist['id']).execute()
                    else:
                        new_att = {'id': f'att-{int(time.time())}', 'date': sel_dt, 'specialty': sel_sp, 'presentStudentIds': json.dumps(p_list)}
                        supabase.table('attendance').insert(new_att).execute()
                        st.session_state.attendance.append({'id': new_att['id'], 'date': sel_dt, 'specialty': sel_sp, 'presentStudentIds': p_list})
                    st.success("ثبت شد.")
                    st.rerun()

        elif selection == "tuition":
            st.title("💳 مالی")
            act_sts = [s for s in st.session_state.students if s['status'] == 'فعال']
            if act_sts:
                with st.form("pay"):
                    pst = st.selectbox("هنرجو:", [s['id'] for s in act_sts], format_func=lambda x: next(s['name'] for s in act_sts if s['id'] == x))
                    pam = st.number_input("مبلغ (ریال):", value=600000)
                    pex = st.text_input("سررسید جدید:", value="1405/05/11")
                    if st.form_submit_button("ثبت فیش"):
                        nt = {'id': f't-{int(time.time())}', 'studentId': pst, 'amount': int(pam), 'payDate': TODAY_JALALI, 'expiryDate': pex, 'paymentMethod': 'کارت خوان', 'notes': ''}
                        supabase.table('tuitions').insert(nt).execute()
                        supabase.table('students').update({'tuitionExpiry': pex}).eq('id', pst).execute()
                        st.session_state.tuitions.append(nt)
                        st.success("تمدید شد.")
                        st.rerun()

        elif selection == "sms":
            st.title("💬 پیامک")
            sid = st.selectbox("گیرنده:", [s['id'] for s in st.session_state.students], format_func=lambda x: next(s['name'] for s in st.session_state.students if s['id'] == x))
            st_info = next(s for s in st.session_state.students if s['id'] == sid)
            msg = st.text_area("متن پیام:", value=f"هنرجوی گرامی {st_info['name']}، مهلت شهریه شما رو به اتمام است.")
            if st.button("ارسال پیامک", type="primary"):
                n_log = {'id': f'sms-{int(time.time())}', 'recipientName': st_info['name'], 'recipientPhone': st_info['phone'], 'messageText': msg, 'date': TODAY_JALALI}
                supabase.table('sms_logs').insert(n_log).execute()
                st.session_state.sms_logs.insert(0, n_log)
                st.success("ارسال شد.")
                st.rerun()

        elif selection == "events":
            st.title("📅 رویدادها")
            with st.form("ev"):
                t = st.text_input("عنوان:")
                d = st.text_input("تاریخ:")
                if st.form_submit_button("ثبت"):
                    ne = {'id': f'ev-{int(time.time())}', 'title': t, 'date': d, 'time': '10', 'location': '', 'type': 'match'}
                    supabase.table('events').insert(ne).execute()
                    st.session_state.events.append(ne)
                    st.success("ثبت شد")
                    st.rerun()

        elif selection == "settings":
            st.title("⚙️ تنظیمات سیستم")
            c1, c2 = st.columns(2)
            with c1:
                with st.form("logo"):
                    lf = st.file_uploader("لوگو باشگاه", type=['png', 'jpg'])
                    if st.form_submit_button("ذخیره"):
                        b64 = image_to_base64(lf)
                        supabase.table('club_settings').upsert({'key': 'club_logo', 'value': b64}).execute()
                        st.session_state.club_logo = b64
                        st.rerun()
            with c2:
                with st.form("cred"):
                    u = st.text_input("نام کاربری:", value=st.session_state.admin_username)
                    p = st.text_input("رمز:", type="password", value=st.session_state.admin_password)
                    if st.form_submit_button("ذخیره رمز"):
                        supabase.table('club_settings').upsert({'key': 'admin_username', 'value': u}).execute()
                        supabase.table('club_settings').upsert({'key': 'admin_password', 'value': p}).execute()
                        st.session_state.admin_username = u; st.session_state.admin_password = p
                        st.rerun()
            if st.button("🚪 خروج", type="primary"):
                st.session_state.logged_in = False
                st.rerun()