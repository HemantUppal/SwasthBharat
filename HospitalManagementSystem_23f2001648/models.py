from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()



class User(db.Model, UserMixin):
    __tablename__ = "users"

    name= db.Column(db.String(150), nullable=False)
    pincode = db.Column(db.String(20), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    address=db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # admin / doctor / patient
    phone = db.Column(db.String(20))
    is_blacklisted = db.Column(db.Boolean, default=False, nullable=False)

    # One-to-One relationships
    doctor_profile = db.relationship(
        "DoctorProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete"
    )

    patient_profile = db.relationship(
        "PatientProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete"
    )



class DoctorProfile(db.Model):
    __tablename__ = "doctor_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    specialization = db.Column(db.String(150), nullable=False)
    experience = db.Column(db.Integer, nullable=False)
    contact_info = db.Column(db.String(150), nullable=False)
    license = db.Column(db.String(100), nullable=False)
    user = db.relationship("User", back_populates="doctor_profile")

    # One doctor → many availabilities
    availabilities = db.relationship(
        "Availability",
        back_populates="doctor",
        cascade="all, delete-orphan"
    )

    # One doctor → many appointments
    appointments = db.relationship(
        "Appointment",
        back_populates="doctor",
        cascade="all, delete-orphan"
    )



class PatientProfile(db.Model):
    __tablename__ = "patient_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    contact_info = db.Column(db.String(150), nullable=False)

    user = db.relationship("User", back_populates="patient_profile")

    # One patient → many appointments
    appointments = db.relationship(
        "Appointment",
        back_populates="patient",
        cascade="all, delete-orphan"
    )



class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)

    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor_profiles.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient_profiles.id"), nullable=False)

    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(50), default="scheduled")  # scheduled / completed / cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctor = db.relationship("DoctorProfile", back_populates="appointments")
    patient = db.relationship("PatientProfile", back_populates="appointments")


# ------------------------
# Availability Model
# ------------------------
class Availability(db.Model):
    __tablename__ = "availabilities"

    id = db.Column(db.Integer, primary_key=True)

    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor_profiles.id"), nullable=False)

    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    doctor = db.relationship("DoctorProfile", back_populates="availabilities")

    __table_args__ = (
        db.UniqueConstraint("doctor_id", "date", "start_time", name="unique_doctor_slot"),
    )


class TreatmentRecord(db.Model):
    __tablename__ = "treatment_records"

    id             = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"),
                               unique=True, nullable=False)

    diagnosis      = db.Column(db.Text, nullable=False)
    treatment      = db.Column(db.Text)
    prescription   = db.Column(db.Text)
    notes          = db.Column(db.Text)

    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow)

    appointment    = db.relationship("Appointment", backref=db.backref("treatment_record", uselist=False))