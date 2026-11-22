-- LifeLine AI - Reference PostgreSQL Schema
-- Updated for Prompt 03 Domain Model Evolution:
-- Patient Intelligence, Hospital Readiness & Referral Coordination

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

CREATE TABLE hospital_departments (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    department_name VARCHAR(120) NOT NULL,
    department_code VARCHAR(40) NOT NULL,
    description TEXT,
    operational_status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    contact_information VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_hospital_dept_code UNIQUE (hospital_id, department_code)
);
CREATE INDEX ix_hospital_departments_hospital_id ON hospital_departments(hospital_id);

CREATE TABLE hospital_capabilities (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    department_id INTEGER REFERENCES hospital_departments(id) ON DELETE SET NULL,
    capability_code VARCHAR(60) NOT NULL,
    capability_name VARCHAR(120) NOT NULL,
    capability_category VARCHAR(60) NOT NULL,
    description TEXT,
    availability_mode VARCHAR(30) NOT NULL DEFAULT '24_7',
    verification_status VARCHAR(30) NOT NULL DEFAULT 'UNVERIFIED',
    verified_by_user_id INTEGER REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_hospital_capability UNIQUE (hospital_id, capability_code)
);
CREATE INDEX ix_hospital_capabilities_hospital_id ON hospital_capabilities(hospital_id);
CREATE INDEX ix_hospital_capabilities_department_id ON hospital_capabilities(department_id);
CREATE INDEX ix_hospital_capabilities_capability_code ON hospital_capabilities(capability_code);
CREATE INDEX ix_hospital_capabilities_capability_category ON hospital_capabilities(capability_category);

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

CREATE TABLE specialist_availabilities (
    id SERIAL PRIMARY KEY,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    department_id INTEGER REFERENCES hospital_departments(id) ON DELETE SET NULL,
    availability_status VARCHAR(30) NOT NULL DEFAULT 'AVAILABLE',
    shift_start TIMESTAMPTZ NOT NULL,
    shift_end TIMESTAMPTZ NOT NULL,
    on_call BOOLEAN NOT NULL DEFAULT false,
    last_verified_at TIMESTAMPTZ,
    verified_by_user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_specialist_availabilities_doctor_id ON specialist_availabilities(doctor_id);
CREATE INDEX ix_specialist_availabilities_hospital_id ON specialist_availabilities(hospital_id);
CREATE INDEX ix_specialist_availabilities_department_id ON specialist_availabilities(department_id);
CREATE INDEX ix_specialist_avail_lookup ON specialist_availabilities(hospital_id, doctor_id, availability_status);

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

CREATE TABLE patient_clinical_facts (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    fact_type VARCHAR(50) NOT NULL,
    fact_code VARCHAR(80),
    fact_value VARCHAR(255) NOT NULL,
    normalized_value VARCHAR(255),
    clinical_status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    effective_from VARCHAR(20),
    effective_to VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_patient_clinical_facts_patient_id ON patient_clinical_facts(patient_id);
CREATE INDEX ix_patient_clinical_facts_fact_type ON patient_clinical_facts(fact_type);

CREATE TABLE clinical_provenance (
    id SERIAL PRIMARY KEY,
    clinical_fact_id INTEGER NOT NULL REFERENCES patient_clinical_facts(id) ON DELETE CASCADE,
    source_type VARCHAR(40) NOT NULL,
    source_report_id INTEGER REFERENCES medical_reports(id) ON DELETE SET NULL,
    source_user_id INTEGER REFERENCES users(id),
    source_reference VARCHAR(255),
    source_excerpt TEXT,
    extracted_at TIMESTAMPTZ DEFAULT now(),
    verification_status VARCHAR(30) NOT NULL DEFAULT 'UNVERIFIED',
    verified_by_user_id INTEGER REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    verification_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_clinical_provenance_clinical_fact_id ON clinical_provenance(clinical_fact_id);
CREATE INDEX ix_clinical_provenance_source_report_id ON clinical_provenance(source_report_id);

CREATE TABLE hospital_resources (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    resource_type VARCHAR(30) NOT NULL,
    total INTEGER NOT NULL CHECK (total >= 0),
    available INTEGER NOT NULL CHECK (available >= 0),
    department_id INTEGER REFERENCES hospital_departments(id) ON DELETE SET NULL,
    operational_status VARCHAR(30) NOT NULL DEFAULT 'FUNCTIONAL',
    staffed_capacity INTEGER,
    occupied_count INTEGER NOT NULL DEFAULT 0,
    maintenance_count INTEGER NOT NULL DEFAULT 0,
    last_verified_at TIMESTAMPTZ,
    verified_by_user_id INTEGER REFERENCES users(id),
    status_source VARCHAR(40) NOT NULL DEFAULT 'MANUAL',
    freshness_window_minutes INTEGER NOT NULL DEFAULT 60,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (hospital_id, resource_type)
);
CREATE INDEX ix_hospital_resources_department_id ON hospital_resources(department_id);

CREATE TABLE resource_status_history (
    id SERIAL PRIMARY KEY,
    hospital_resource_id INTEGER NOT NULL REFERENCES hospital_resources(id) ON DELETE CASCADE,
    previous_status VARCHAR(30),
    new_status VARCHAR(30) NOT NULL,
    previous_available_count INTEGER,
    new_available_count INTEGER NOT NULL,
    verification_source VARCHAR(40) NOT NULL DEFAULT 'MANUAL',
    verified_by_user_id INTEGER REFERENCES users(id),
    verified_at TIMESTAMPTZ DEFAULT now(),
    remarks TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_resource_status_history_resource_id ON resource_status_history(hospital_resource_id);
CREATE INDEX ix_resource_status_history_created_at ON resource_status_history(created_at);

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
    origin_type VARCHAR(40) NOT NULL DEFAULT 'PATIENT_SOS',
    referral_round INTEGER NOT NULL DEFAULT 1,
    case_closed_at TIMESTAMPTZ,
    handover_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    handover_signed_by VARCHAR(120),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    arrived_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
CREATE INDEX ix_cases_patient ON emergency_cases(patient_id);
CREATE INDEX ix_cases_hospital ON emergency_cases(hospital_id);
CREATE INDEX ix_cases_status ON emergency_cases(status);

CREATE TABLE referral_requests (
    id SERIAL PRIMARY KEY,
    emergency_case_id INTEGER NOT NULL REFERENCES emergency_cases(id) ON DELETE CASCADE,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    request_reference VARCHAR(60) UNIQUE NOT NULL,
    request_round INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(30) NOT NULL DEFAULT 'SENT',
    requested_by_user_id INTEGER REFERENCES users(id),
    requested_at TIMESTAMPTZ DEFAULT now(),
    response_deadline TIMESTAMPTZ,
    responded_at TIMESTAMPTZ,
    accepted_by_user_id INTEGER REFERENCES users(id),
    decline_reason_code VARCHAR(60),
    clarification_notes TEXT,
    is_active_acceptance BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_case_hosp_round UNIQUE (emergency_case_id, hospital_id, request_round)
);
CREATE INDEX ix_referral_requests_emergency_case_id ON referral_requests(emergency_case_id);
CREATE INDEX ix_referral_requests_hospital_id ON referral_requests(hospital_id);
CREATE INDEX ix_referral_requests_status ON referral_requests(status);
CREATE UNIQUE INDEX uq_case_single_active_accepted ON referral_requests(emergency_case_id) WHERE status = 'ACCEPTED';

CREATE TABLE referral_responses (
    id SERIAL PRIMARY KEY,
    referral_request_id INTEGER NOT NULL REFERENCES referral_requests(id) ON DELETE CASCADE,
    responding_user_id INTEGER REFERENCES users(id),
    response_type VARCHAR(30) NOT NULL,
    response_notes TEXT,
    reason_code VARCHAR(60),
    responded_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_referral_responses_referral_request_id ON referral_responses(referral_request_id);
CREATE INDEX ix_referral_responses_responded_at ON referral_responses(responded_at);

CREATE TABLE resource_reservations (
    id SERIAL PRIMARY KEY,
    referral_request_id INTEGER NOT NULL REFERENCES referral_requests(id) ON DELETE CASCADE,
    hospital_resource_id INTEGER NOT NULL REFERENCES hospital_resources(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    reservation_status VARCHAR(30) NOT NULL DEFAULT 'HELD',
    held_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,
    confirmed_by_user_id INTEGER REFERENCES users(id),
    released_at TIMESTAMPTZ,
    release_reason VARCHAR(120),
    idempotency_key VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_resource_reservations_referral_request_id ON resource_reservations(referral_request_id);
CREATE INDEX ix_resource_reservations_hospital_resource_id ON resource_reservations(hospital_resource_id);

CREATE TABLE emergency_incident_reports (
    id SERIAL PRIMARY KEY,
    emergency_case_id INTEGER NOT NULL REFERENCES emergency_cases(id) ON DELETE CASCADE,
    reporter_user_id INTEGER REFERENCES users(id),
    reporter_type VARCHAR(30) NOT NULL DEFAULT 'PATIENT',
    report_type VARCHAR(30) NOT NULL DEFAULT 'TEXT',
    reported_text TEXT NOT NULL,
    observed_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ DEFAULT now(),
    location_latitude DOUBLE PRECISION,
    location_longitude DOUBLE PRECISION,
    verification_status VARCHAR(30) NOT NULL DEFAULT 'UNVERIFIED',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_emergency_incident_reports_emergency_case_id ON emergency_incident_reports(emergency_case_id);

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
