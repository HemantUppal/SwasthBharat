from flask import jsonify,Flask, request, render_template, redirect, url_for,session,flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_,or_
from flask_login import LoginManager, login_user, UserMixin, logout_user, login_required, current_user
from models import db, User, DoctorProfile, PatientProfile, Availability, Appointment,TreatmentRecord
from config import Config
from datetime import date, time, timedelta, datetime
import json
from werkzeug.security import generate_password_hash
from functools import wraps
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

    

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/patientlogin', methods=['GET','POST'])
def patientlogin():
    if request.method == 'POST':
        email=request.form['email']
        password=request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            if user.is_blacklisted:
                return 'Your account has been suspended. Contact admin. -> admin@swasthbharat.com'
            else:
                login_user(user)
                if user.role == "doctor":
                    return redirect(url_for("doctordash"))
                elif user.role == "patient":
                    return redirect(url_for("patientdash"))
                elif user.role == "admin":
                    return redirect(url_for("admindash"))
        else:
            return "Invalid credentials"        
    return render_template("patientlogin.html")


@app.route('/patientregister',methods=['GET','POST'])
def patientregister():
    if request.method == 'POST':
        fullname = request.form['name']
        emailid = request.form['email']
        password = request.form['password']
        address = request.form['address']
        pincode= request.form['pincode']
        phone=request.form['phone']
        age=request.form['age']
        gender=request.form['gender']
        new_user = User(email=emailid, password=password,name=fullname, pincode=pincode,phone=phone, address=address, role='patient')
        db.session.add(new_user)
        db.session.commit()
        new_patient_profile = PatientProfile(user_id=new_user.id, age=age, gender=gender, contact_info=phone)
        db.session.add(new_patient_profile)
        db.session.commit()
        return redirect ('/patientlogin')
    return render_template('patientregister.html')

@app.route('/doctorlogin', methods=['GET','POST']) 
def doctorlogin():
    if request.method == 'POST':
        email=request.form['email']
        password=request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            login_user(user)
            if user.role == "doctor":
                return redirect(url_for("doctordash"))
            elif user.role == "patient":
                return redirect(url_for("patientdash"))
            elif user.role == "admin":
                return redirect(url_for("admindash"))
        else:
            return "Invalid credentials"        
    return render_template("doctorlogin.html")

@app.route('/doctorregister',methods=['GET','POST'])
def doctorregister():
    if request.method == 'POST':
        fullname = request.form['name']
        emailid = request.form['email']
        password = request.form['password']
        address = request.form['address']
        pincode= request.form['pincode']
        phone=request.form['phone']
        specialization=request.form['specialization']
        experience=request.form['experience']
        # contact_info=request.form['contact_info']
        license=request.form['license']

        new_user = User(email=emailid, password=password,name=fullname, pincode=pincode,phone=phone, address=address, role='doctor')
        db.session.add(new_user)
        db.session.commit()

        doctor_profile = DoctorProfile(user_id=new_user.id, specialization=specialization, experience=experience, contact_info=phone,license=license)
        db.session.add(doctor_profile)
        db.session.commit()

        return redirect ('/doctorlogin')
    return render_template('doctorregister.html')





def _get_patient_profile():

    if current_user.role != 'patient':
        return None
    return PatientProfile.query.filter_by(user_id=current_user.id).first()


def _doctors_as_json(doctors, today_dt):

    next_week = today_dt + timedelta(days=7)
    result = []
    for d in doctors:
        slots = (
            Availability.query
            .filter_by(doctor_id=d.id)
            .filter(Availability.date >= today_dt, Availability.date <= next_week)
            .order_by(Availability.date, Availability.start_time)
            .all()
        )
        result.append({
            "id":             d.id,
            "name":           d.user.name,
            "specialization": d.specialization,
            "experience":     d.experience,
            "license":        d.license,
            "contact_info":   d.contact_info,
            "availability": [
                {
                    "id":         s.id,
                    "date":       s.date.strftime("%Y-%m-%d"),
                    "start_time": s.start_time.strftime("%H:%M"),
                    "end_time":   s.end_time.strftime("%H:%M"),
                }
                for s in slots
            ],
        })
    return result



#  ROUTE 1 — Patient Dashboard (main page)

@app.route('/patientdash')
@login_required
def patientdash():
    patient_profile = _get_patient_profile()
    if not patient_profile:
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))         

    today_dt  = date.today()
    next_week = today_dt + timedelta(days=7)


    upcoming_appointments = (
        Appointment.query
        .filter_by(patient_id=patient_profile.id, status='scheduled')
        .filter(Appointment.date >= today_dt)
        .order_by(Appointment.date.asc(), Appointment.time.asc())
        .all()
    )


    past_appointments = (
        Appointment.query
        .filter_by(patient_id=patient_profile.id)
        .filter(
            db.or_(
                Appointment.status.in_(['completed', 'cancelled']),
                db.and_(Appointment.status == 'scheduled', Appointment.date < today_dt)
            )
        )
        .order_by(Appointment.date.desc())
        .all()
    )


    all_doctors = (
        DoctorProfile.query
        .join(User)
        .order_by(DoctorProfile.specialization)
        .all()
    )
    treatmentrecords = TreatmentRecord.query.all()

    specializations = sorted({d.specialization for d in all_doctors})


    import json
    all_doctors_json = json.dumps(_doctors_as_json(all_doctors, today_dt))
    
    return render_template(
        'patientdash1.html',
        patient=current_user,
        patient_profile=patient_profile,
        upcoming_appointments=upcoming_appointments,
        past_appointments=past_appointments,
        all_doctors=all_doctors,
        all_doctors_json=all_doctors_json,
        specializations=specializations,
        today=today_dt,
        treatmentrecords=treatmentrecords
    )



#  ROUTE 2 — Book Appointment  (POST JSON)

@app.route('/patient/book', methods=['POST'])
@login_required
def book_appointment():
    patient_profile = _get_patient_profile()
    if not patient_profile:
        return jsonify(success=False, message='Access denied.'), 403

    data         = request.get_json(force=True)
    doctor_id    = data.get('doctor_id')
    avail_id     = data.get('availability_id')


    slot = Availability.query.filter_by(id=avail_id, doctor_id=doctor_id).first()
    if not slot:
        return jsonify(success=False, message='Slot not found.'), 404


    duplicate = Appointment.query.filter_by(
        patient_id=patient_profile.id,
        doctor_id=doctor_id,
        date=slot.date,
        time=slot.start_time,
        status='scheduled'
    ).first()
    if duplicate:
        return jsonify(success=False, message='You already have this slot booked.'), 409

    appt = Appointment(
        doctor_id=doctor_id,
        patient_id=patient_profile.id,
        date=slot.date,
        time=slot.start_time,
        status='scheduled',
    )
    db.session.add(appt)
    db.session.commit()

    return jsonify(
        success=True,
        message=f'Appointment booked for {slot.date.strftime("%d %b %Y")} at {slot.start_time.strftime("%I:%M %p")}',
        appointment={
            'id':     appt.id,
            'date':   slot.date.strftime('%Y-%m-%d'),
            'time':   slot.start_time.strftime('%H:%M'),
            'status': 'scheduled',
            'doctor': appt.doctor.user.name,
            'spec':   appt.doctor.specialization,
        }
    ), 201


#  ROUTE 3 — Cancel Appointment  (POST)

@app.route('/patient/appointment/<int:appt_id>/cancel', methods=['POST'])
@login_required
def cancel_appointment(appt_id):
    patient_profile = _get_patient_profile()
    if not patient_profile:
        return jsonify(success=False, message='Access denied.'), 403

    appt = Appointment.query.filter_by(
        id=appt_id, patient_id=patient_profile.id
    ).first_or_404()

    if appt.status != 'scheduled':
        return jsonify(success=False, message='Only scheduled appointments can be cancelled.'), 400

    appt.status = 'cancelled'
    db.session.commit()
    return jsonify(success=True, message='Appointment cancelled.')



#  ROUTE 4 — Update Patient Profile  

@app.route('/patient/profile/update', methods=['POST'])
@login_required
def update_patient_profile():
    patient_profile = _get_patient_profile()
    if not patient_profile:
        return jsonify(success=False, message='Access denied.'), 403

    data = request.get_json(force=True)


    current_user.name    = data.get('name',    current_user.name).strip()
    current_user.email   = data.get('email',   current_user.email).strip()
    current_user.phone   = data.get('phone',   current_user.phone)
    current_user.address = data.get('address', current_user.address)
    current_user.pincode = data.get('pincode', current_user.pincode)


    try:
        patient_profile.age    = int(data.get('age', patient_profile.age))
    except (ValueError, TypeError):
        pass
    patient_profile.gender       = data.get('gender',  patient_profile.gender)
    patient_profile.contact_info = data.get('phone',   patient_profile.contact_info)

    db.session.commit()
    return jsonify(success=True, message='Profile updated successfully.')



#  ROUTE 5 — Doctor Availability JSON  (called by modal)

@app.route('/patient/doctor/<int:doctor_id>/availability')
@login_required
def doctor_availability(doctor_id):
    today_dt  = date.today()
    next_week = today_dt + timedelta(days=7)

    slots = (
        Availability.query
        .filter_by(doctor_id=doctor_id)
        .filter(Availability.date >= today_dt, Availability.date <= next_week)
        .order_by(Availability.date, Availability.start_time)
        .all()
    )
    return jsonify([
        {
            'id':         s.id,
            'date':       s.date.strftime('%Y-%m-%d'),
            'start_time': s.start_time.strftime('%H:%M'),
            'end_time':   s.end_time.strftime('%H:%M'),
        }
        for s in slots
    ])


#  ROUTE 6 — All Doctors JSON  (GET, supports ?specialization= filter)

@app.route('/patient/doctors')
@login_required
def get_doctors():
    spec = request.args.get('specialization', '').strip()
    query = DoctorProfile.query.join(User)
    if spec:
        query = query.filter(DoctorProfile.specialization.ilike(f'%{spec}%'))
    doctors = query.all()
    return jsonify(_doctors_as_json(doctors, date.today()))




def _get_doctor_profile():
    if current_user.role != 'doctor':
        return None
    return DoctorProfile.query.filter_by(user_id=current_user.id).first()




@app.route('/doctordash')
@login_required
def doctordash():
    if current_user.role != 'doctor':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('home'))

    dp = _get_doctor_profile()
    if not dp:
        flash('Doctor profile not found.', 'danger')
        return redirect(url_for('home'))

    today_dt  = date.today()
    week_end  = today_dt + timedelta(days=7)


    all_appointments = (
        Appointment.query
        .filter_by(doctor_id=dp.id)
        .order_by(Appointment.date.desc(), Appointment.time.desc())
        .all()
    )

    today_appointments = [a for a in all_appointments if a.date == today_dt]
    week_appointments  = [a for a in all_appointments
                          if today_dt <= a.date <= week_end]


    today_count    = len(today_appointments)
    completed_today = sum(1 for a in today_appointments if a.status == 'completed')
    scheduled_today = sum(1 for a in today_appointments if a.status == 'scheduled')
    week_count     = len(week_appointments)
    cancelled_week = sum(1 for a in week_appointments if a.status == 'cancelled')

    availability = (
        Availability.query
        .filter_by(doctor_id=dp.id)
        .filter(Availability.date >= today_dt, Availability.date <= week_end)
        .order_by(Availability.date, Availability.start_time)
        .all()
    )
    open_slots = len(availability)


    patient_ids = list({a.patient_id for a in all_appointments})
    patients = PatientProfile.query.filter(PatientProfile.id.in_(patient_ids)).all()


    treatment_records = []
    try:
        from models import TreatmentRecord
        treatment_records = (
            TreatmentRecord.query
            .join(Appointment)
            .filter(Appointment.doctor_id == dp.id)
            .order_by(TreatmentRecord.created_at.desc())
            .all()
        )
    except ImportError:
        pass  

    appointments_json = json.dumps([{
        'id':           a.id,
        'patient_id':   a.patient_id,
        'patient_name': a.patient.user.name,
        'date':         a.date.strftime('%Y-%m-%d'),
        'time':         a.time.strftime('%H:%M'),
        'status':       a.status,
    } for a in all_appointments])

    availability_json = json.dumps([{
        'id':         s.id,
        'date':       s.date.strftime('%Y-%m-%d'),
        'start_time': s.start_time.strftime('%H:%M'),
        'end_time':   s.end_time.strftime('%H:%M'),
    } for s in availability])

    patients_json = json.dumps([{
        'id':          p.id,
        'name':        p.user.name,
        'email':       p.user.email,
        'age':         p.age,
        'gender':      p.gender,
        'contact_info': p.contact_info,
    } for p in patients])

    return render_template(
        'doctordash.html',
        doctor              = current_user,
        dp                  = dp,
        today_appointments  = today_appointments,
        all_appointments    = all_appointments,
        patients            = patients,
        treatment_records   = treatment_records,
        # stats
        today_count         = today_count,
        completed_today     = completed_today,
        scheduled_today     = scheduled_today,
        week_count          = week_count,
        cancelled_week      = cancelled_week,
        open_slots          = open_slots,
        # JSON for JS
        appointments_json   = appointments_json,
        availability_json   = availability_json,
        patients_json       = patients_json,
    )



#  ROUTE: Update Appointment Status  (POST JSON)

@app.route('/doctor/appointment/update', methods=['POST'])
@login_required
def doctor_update_appointment():
    dp = _get_doctor_profile()
    if not dp:
        return jsonify(success=False, message='Access denied.'), 403

    data    = request.get_json(force=True)
    appt_id = data.get('appointment_id')
    status  = data.get('status')

    if status not in ('completed', 'cancelled'):
        return jsonify(success=False, message='Invalid status.'), 400

    appt = Appointment.query.filter_by(id=appt_id, doctor_id=dp.id).first()
    if not appt:
        return jsonify(success=False, message='Appointment not found.'), 404

    if appt.status != 'scheduled':
        return jsonify(success=False, message='Only scheduled appointments can be updated.'), 400

    appt.status = status
    db.session.commit()
    return jsonify(success=True, message=f'Appointment marked as {status}.')



#  ROUTE: Add Availability Slot  (POST JSON)

@app.route('/doctor/availability/add', methods=['POST'])
@login_required
def doctor_add_availability():
    dp = _get_doctor_profile()
    if not dp:
        return jsonify(success=False, message='Access denied.'), 403

    data = request.get_json(force=True)
    try:
        slot_date  = datetime.strptime(data['date'], '%Y-%m-%d').date()
        start_time = datetime.strptime(data['start_time'], '%H:%M').time()
        end_time   = datetime.strptime(data['end_time'],   '%H:%M').time()
    except (KeyError, ValueError):
        return jsonify(success=False, message='Invalid date/time format.'), 400

    if start_time >= end_time:
        return jsonify(success=False, message='End time must be after start time.'), 400

    if slot_date < date.today():
        return jsonify(success=False, message='Cannot add availability in the past.'), 400

    # Check for duplicate
    existing = Availability.query.filter_by(
        doctor_id=dp.id, date=slot_date, start_time=start_time
    ).first()
    if existing:
        return jsonify(success=False, message='This slot already exists.'), 409

    slot = Availability(
        doctor_id=dp.id,
        date=slot_date,
        start_time=start_time,
        end_time=end_time,
    )
    db.session.add(slot)
    db.session.commit()

    return jsonify(success=True, message='Slot added.', slot={
        'id':         slot.id,
        'date':       slot.date.strftime('%Y-%m-%d'),
        'start_time': slot.start_time.strftime('%H:%M'),
        'end_time':   slot.end_time.strftime('%H:%M'),
    }), 201



#  ROUTE: Delete Availability Slot  (POST JSON)

@app.route('/doctor/availability/delete', methods=['POST'])
@login_required
def doctor_delete_availability():
    dp = _get_doctor_profile()
    if not dp:
        return jsonify(success=False, message='Access denied.'), 403

    data    = request.get_json(force=True)
    slot_id = data.get('availability_id')

    slot = Availability.query.filter_by(id=slot_id, doctor_id=dp.id).first()
    if not slot:
        return jsonify(success=False, message='Slot not found.'), 404

    db.session.delete(slot)
    db.session.commit()
    return jsonify(success=True, message='Slot removed.')



#  ROUTE: Get Patient Appointments  (GET JSON — for modal)

@app.route('/doctor/patient/<int:patient_id>/appointments')
@login_required
def doctor_patient_appointments(patient_id):
    dp = _get_doctor_profile()
    if not dp:
        return jsonify([]), 403

    appts = (
        Appointment.query
        .filter_by(doctor_id=dp.id, patient_id=patient_id)
        .order_by(Appointment.date.desc())
        .all()
    )
    return jsonify([{
        'id':           a.id,
        'patient_id':   a.patient_id,
        'patient_name': a.patient.user.name,
        'date':         a.date.strftime('%Y-%m-%d'),
        'time':         a.time.strftime('%H:%M'),
        'status':       a.status,
    } for a in appts])



#  ROUTE: Save Treatment Record  (POST JSON)
#
#  Requires TreatmentRecord model — see bottom of this file.

@app.route('/doctor/treatment/save', methods=['POST'])
@login_required
def doctor_save_treatment():
    dp = _get_doctor_profile()
    if not dp:
        return jsonify(success=False, message='Access denied.'), 403

    data    = request.get_json(force=True)
    appt_id = data.get('appointment_id')

    appt = Appointment.query.filter_by(id=appt_id, doctor_id=dp.id).first()
    if not appt:
        return jsonify(success=False, message='Appointment not found.'), 404

    try:
        from models import TreatmentRecord
    except ImportError:
        return jsonify(success=False, message='TreatmentRecord model not found. Please add it to models.py.'), 500


    existing = TreatmentRecord.query.filter_by(appointment_id=appt_id).first()
    if existing:

        existing.diagnosis   = data.get('diagnosis', existing.diagnosis)
        existing.treatment   = data.get('treatment', existing.treatment)
        existing.prescription= data.get('prescription', existing.prescription)
        existing.notes       = data.get('notes', existing.notes)
        existing.updated_at  = datetime.utcnow()
        db.session.commit()
        record = existing
    else:
        record = TreatmentRecord(
            appointment_id = appt_id,
            diagnosis      = data.get('diagnosis', ''),
            treatment      = data.get('treatment', ''),
            prescription   = data.get('prescription', ''),
            notes          = data.get('notes', ''),
        )
        db.session.add(record)
        db.session.commit()

    if appt.status == 'scheduled':
        appt.status = 'completed'
        db.session.commit()

    return jsonify(success=True, message='Record saved.', record={
        'id':           record.id,
        'date':         appt.date.strftime('%d %b %Y'),
        'patient_name': appt.patient.user.name,
        'diagnosis':    record.diagnosis,
        'treatment':    record.treatment,
        'prescription': record.prescription,
        'notes':        record.notes,
    }), 201

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify(success=False, message='Unauthorized.'), 403
    return decorated



# JSON-serialisable lists for the JS layer


def _doctor_json(dp):
    return {
        'id':             dp.id,
        'user_id':        dp.user_id,
        'name':           dp.user.name,
        'email':          dp.user.email,
        'phone':          dp.user.phone or '',
        'address':        dp.user.address or '',
        'pincode':        dp.user.pincode or '',
        'specialization': dp.specialization,
        'experience':     dp.experience,
        'license':        dp.license,
        'is_blacklisted': getattr(dp.user, 'is_blacklisted', False),
    }

def _patient_json(pp):
    return {
        'id':           pp.id,
        'user_id':      pp.user_id,
        'name':         pp.user.name,
        'email':        pp.user.email,
        'phone':        pp.user.phone or '',
        'address':      pp.user.address or '',
        'pincode':      pp.user.pincode or '',
        'age':          pp.age,
        'gender':       pp.gender,
        'contact_info': pp.contact_info or '',
        'is_blacklisted': getattr(pp.user, 'is_blacklisted', False),
    }



#  ROUTE — Admin Dashboard  (GET)


@app.route('/admindash')
@login_required
def admindash():
    if current_user.role != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('home'))

    today_dt = date.today()


    doctors = DoctorProfile.query.join(User).order_by(User.name).all()

    patients = PatientProfile.query.join(User).order_by(User.name).all()


    all_appointments = (
        Appointment.query
        .order_by(Appointment.date.desc(), Appointment.time.desc())
        .all()
    )

    total_doctors           = len(doctors)
    active_doctors          = sum(1 for d in doctors if not getattr(d.user, 'is_blacklisted', False))
    total_patients          = len(patients)
    active_patients         = sum(1 for p in patients if not getattr(p.user, 'is_blacklisted', False))
    total_appointments      = len(all_appointments)
    scheduled_appointments  = sum(1 for a in all_appointments if a.status == 'scheduled')
    completed_appointments  = sum(1 for a in all_appointments if a.status == 'completed')
    cancelled_appointments  = sum(1 for a in all_appointments if a.status == 'cancelled')


    recent_appointments = all_appointments[:5]
    recent_users = (
        User.query
        .filter(User.role.in_(['doctor', 'patient']))
        .order_by(User.id.desc())
        .limit(5)
        .all()
    )


    specializations = sorted({d.specialization for d in doctors if d.specialization})
    DEFAULT_SPECS   = [
        'Cardiology', 'Neurology', 'Orthopedics', 'Pediatrics',
        'Dermatology', 'General Medicine', 'Ophthalmology', 'ENT',
        'Psychiatry', 'Oncology', 'Radiology', 'Urology',
    ]
    for s in DEFAULT_SPECS:
        if s not in specializations:
            specializations.append(s)
    specializations.sort()

    doctors_json  = json.dumps([_doctor_json(d)  for d in doctors])
    patients_json = json.dumps([_patient_json(p) for p in patients])

    return render_template(
        'admindash.html',
        admin                   = current_user,
        doctors                 = doctors,
        patients                = patients,
        all_appointments        = all_appointments,
        recent_appointments     = recent_appointments,
        recent_users            = recent_users,
        specializations         = specializations,
        # stats
        total_doctors           = total_doctors,
        active_doctors          = active_doctors,
        total_patients          = total_patients,
        active_patients         = active_patients,
        total_appointments      = total_appointments,
        scheduled_appointments  = scheduled_appointments,
        completed_appointments  = completed_appointments,
        cancelled_appointments  = cancelled_appointments,
        # JSON for JS
        doctors_json            = doctors_json,
        patients_json           = patients_json,
    )



#  ROUTE — Add Doctor  (POST JSON)



@app.route('/admin/doctor/add', methods=['POST'])
@login_required
def admin_add_doctor():
    if current_user.role != 'admin':
        return jsonify(success=False, message='Unauthorized.'), 403

    data = request.get_json(force=True)

    required = ['name', 'email', 'password', 'specialization', 'license']
    for field in required:
        if not data.get(field, '').strip():
            return jsonify(success=False, message=f'{field} is required.'), 400


    if User.query.filter_by(email=data['email'].strip()).first():
        return jsonify(success=False, message='Email already registered.'), 409

    try:
        new_user = User(
            name     = data['name'].strip(),
            email    = data['email'].strip(),
            password = generate_password_hash(data['password']),
            role     = 'doctor',
            phone    = data.get('phone', '').strip(),
            address  = data.get('address', '').strip(),
            pincode  = data.get('pincode', '').strip(),
            is_blacklisted = False,
        )
        db.session.add(new_user)
        db.session.flush()  

        dp = DoctorProfile(
            user_id        = new_user.id,
            specialization = data['specialization'].strip(),
            experience     = int(data.get('experience') or 0),
            contact_info   = data.get('phone', '').strip(),
            license        = data['license'].strip(),
        )
        db.session.add(dp)
        db.session.commit()

        return jsonify(success=True, message='Doctor added.', doctor=_doctor_json(dp)), 201

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500



#  ROUTE — Edit Doctor  (POST JSON)


@app.route('/admin/doctor/edit', methods=['POST'])
@login_required
def admin_edit_doctor():
    if current_user.role != 'admin':
        return jsonify(success=False, message='Unauthorized.'), 403

    data = request.get_json(force=True)
    dp   = DoctorProfile.query.get(data.get('doctor_id'))
    if not dp:
        return jsonify(success=False, message='Doctor not found.'), 404

    try:

        if 'name'    in data: dp.user.name    = data['name'].strip()
        if 'email'   in data: dp.user.email   = data['email'].strip()
        if 'phone'   in data: dp.user.phone   = data['phone'].strip()
        if 'address' in data: dp.user.address = data['address'].strip()
        if 'pincode' in data: dp.user.pincode = data['pincode'].strip()


        if 'specialization' in data:
            dp.specialization = data['specialization'].strip()
        if 'experience' in data:
            dp.experience = int(data['experience'] or 0)
        if 'license' in data:
            dp.license = data['license'].strip()
        if 'phone' in data:
            dp.contact_info = data['phone'].strip()

        db.session.commit()
        return jsonify(success=True, message='Doctor updated.', doctor=_doctor_json(dp))

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500



#  ROUTE — Edit Patient  (POST JSON)


@app.route('/admin/patient/edit', methods=['POST'])
@login_required
def admin_edit_patient():
    if current_user.role != 'admin':
        return jsonify(success=False, message='Unauthorized.'), 403

    data = request.get_json(force=True)
    pp   = PatientProfile.query.get(data.get('patient_id'))
    if not pp:
        return jsonify(success=False, message='Patient not found.'), 404

    try:
        if 'name'    in data: pp.user.name    = data['name'].strip()
        if 'email'   in data: pp.user.email   = data['email'].strip()
        if 'phone'   in data: pp.user.phone   = data['phone'].strip()
        if 'address' in data: pp.user.address = data['address'].strip()
        if 'pincode' in data: pp.user.pincode = data['pincode'].strip()
        if 'age'     in data: pp.age          = int(data['age'] or 0)
        if 'gender'  in data: pp.gender       = data['gender']
        if 'phone'   in data: pp.contact_info = data['phone'].strip()

        db.session.commit()
        return jsonify(success=True, message='Patient updated.', patient=_patient_json(pp))

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500



#  ROUTE — Blacklist / Unban User  (POST JSON)


@app.route('/admin/user/blacklist', methods=['POST'])
@login_required
def admin_blacklist_user():
    if current_user.role != 'admin':
        return jsonify(success=False, message='Unauthorized.'), 403

    data      = request.get_json(force=True)
    user_type = data.get('type')          # 'doctor' or 'patient'
    entity_id = data.get('id')            # DoctorProfile.id or PatientProfile.id

    if user_type == 'doctor':
        profile = DoctorProfile.query.get(entity_id)
    elif user_type == 'patient':
        profile = PatientProfile.query.get(entity_id)
    else:
        return jsonify(success=False, message='Invalid type.'), 400

    if not profile:
        return jsonify(success=False, message='User not found.'), 404

    # Toggle the flag
    current_status               = getattr(profile.user, 'is_blacklisted', False)
    profile.user.is_blacklisted  = not current_status
    db.session.commit()

    action = 'blacklisted' if profile.user.is_blacklisted else 'unbanned'
    return jsonify(
        success    = True,
        message    = f'User {action} successfully.',
        new_status = profile.user.is_blacklisted,
        action     = action,
    )



#  ROUTE — Search  (GET JSON — optional AJAX endpoint)


@app.route('/admin/search')
@login_required
def admin_search():
    if current_user.role != 'admin':
        return jsonify([]), 403

    q          = request.args.get('q', '').strip().lower()
    role_filter = request.args.get('role', 'all')   # 'all' | 'doctor' | 'patient'

    results = []

    if q and role_filter in ('all', 'doctor'):
        doctors = DoctorProfile.query.join(User).filter(
            db.or_(
                User.name.ilike(f'%{q}%'),
                User.email.ilike(f'%{q}%'),
                DoctorProfile.specialization.ilike(f'%{q}%'),
                DoctorProfile.license.ilike(f'%{q}%'),
            )
        ).all()
        results += [{'type': 'doctor', **_doctor_json(d)} for d in doctors]

    if q and role_filter in ('all', 'patient'):
        patients = PatientProfile.query.join(User).filter(
            db.or_(
                User.name.ilike(f'%{q}%'),
                User.email.ilike(f'%{q}%'),
                User.phone.ilike(f'%{q}%'),
            )
        ).all()
        results += [{'type': 'patient', **_patient_json(p)} for p in patients]

    return jsonify(results)

if __name__ == '__main__':

    app.run(debug=True)

