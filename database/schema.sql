-- LifeLine AI - reference PostgreSQL schema (SQLAlchemy creates this automatically for dev/SQLite;
-- this file documents the production Postgres shape and is the base for Alembic migrations).

CREATE TABLE hospitals (
    id SERIAL PRIMARY KEY,
    name VARCHAR(160) NOT NULL,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(80) NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    phone VARCHAR(30),
    capabilities JSONB DEFAULT '[]'
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('patient','doctor','hospital','family')),
    phone VARCHAR(30),
    hospital_id INTEGER REFERENCES hospitals(id),
    linked_patient_id INTEGER,           -- FK added after patients exists
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_users_email ON users(email);
CREATE INDEX ix_users_role ON users(role);

CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
    dob VARCHAR(10),
    gender VARCHAR(20),
    blood_group VARCHAR(5),
    address VARCHAR(255),
    emergency_contacts JSONB DEFAULT '[]',
    known_conditions TEXT,
    known_allergies TEXT,
    current_medications TEXT,
    consent_ai_summary BOOLEAN DEFAULT true,
    family_code VARCHAR(10) UNIQUE NOT NULL
);
ALTER TABLE users ADD CONSTRAINT fk_users_patient FOREIGN KEY (linked_patient_id) REFERENCES patients(id);

CREATE TABLE doctors (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    specialty VARCHAR(80) NOT NULL,
    qualification VARCHAR(120),
    is_available BOOLEAN DEFAULT true
);
CREATE INDEX ix_doctors_hospital ON doctors(hospital_id);
CREATE INDEX ix_doctors_specialty ON doctors(specialty);

CREATE TABLE medical_reports (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    title VARCHAR(200) NOT NULL,
    report_type VARCHAR(40) NOT NULL,
    original_filename VARCHAR(255),
    storage_url VARCHAR(500),
    extracted_text TEXT,
    ocr_status VARCHAR(30) DEFAULT 'ok',
    report_date VARCHAR(10),
    uploaded_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_reports_patient ON medical_reports(patient_id);

CREATE TABLE hospital_resources (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    resource_type VARCHAR(30) NOT NULL,
    total INTEGER NOT NULL,
    available INTEGER NOT NULL,
    UNIQUE (hospital_id, resource_type)
);

CREATE TABLE emergency_cases (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    hospital_id INTEGER REFERENCES hospitals(id),
    doctor_id INTEGER REFERENCES doctors(id),
    status VARCHAR(30) NOT NULL DEFAULT 'CREATED'
        CHECK (status IN ('CREATED','PATIENT_IDENTIFIED','SUMMARY_GENERATED','DOCTOR_ASSIGNED',
                          'ROOM_RESERVED','PATIENT_ARRIVED','COMPLETED')),
    priority SMALLINT NOT NULL DEFAULT 3,
    emergency_type VARCHAR(20) NOT NULL,
    symptoms TEXT,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    current_lat DOUBLE PRECISION,
    current_lng DOUBLE PRECISION,
    eta_minutes INTEGER,
    initial_eta_minutes INTEGER,
    specialty VARCHAR(80),
    ai_summary JSONB,
    checklist JSONB DEFAULT '[]',
    reserved_resources JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    arrived_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
CREATE INDEX ix_cases_patient ON emergency_cases(patient_id);
CREATE INDEX ix_cases_hospital ON emergency_cases(hospital_id);
CREATE INDEX ix_cases_status ON emergency_cases(status);

CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    case_id INTEGER REFERENCES emergency_cases(id),
    title VARCHAR(160) NOT NULL,
    message TEXT NOT NULL,
    channel VARCHAR(20) DEFAULT 'dashboard',
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_notifications_user ON notifications(user_id);

CREATE TABLE activity_logs (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES emergency_cases(id),
    event VARCHAR(60) NOT NULL,
    detail TEXT NOT NULL,
    actor VARCHAR(60) DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_logs_case ON activity_logs(case_id);
