"""Five demo emergency scenarios (patient e-mails match database/seed.py)."""
SCENARIOS = [
    {"key": "stroke", "title": "Stroke-like symptoms - Hinjewadi", "emergency_type": "stroke",
     "symptoms": "Sudden facial drooping and slurred speech, weakness in left arm", "patient_email": "patient1@lifeline.demo",
     "lat": 18.5912, "lng": 73.7389},
    {"key": "cardiac", "title": "Chest pain - Baner", "emergency_type": "cardiac",
     "symptoms": "Severe chest pain radiating to left arm, sweating", "patient_email": "patient2@lifeline.demo",
     "lat": 18.5590, "lng": 73.7868},
    {"key": "trauma", "title": "Fall from height - Wakad", "emergency_type": "trauma",
     "symptoms": "Fall from scaffolding, severe bleeding from leg", "patient_email": "patient3@lifeline.demo",
     "lat": 18.5989, "lng": 73.7600},
    {"key": "diabetic", "title": "Diabetic emergency - Hadapsar", "emergency_type": "diabetic",
     "symptoms": "Confusion, shaking and excessive sweating; insulin user", "patient_email": "patient4@lifeline.demo",
     "lat": 18.5089, "lng": 73.9260},
    {"key": "accident", "title": "Road accident - Katraj", "emergency_type": "accident",
     "symptoms": "Two-wheeler collision, unconscious for a short time", "patient_email": "patient5@lifeline.demo",
     "lat": 18.4575, "lng": 73.8677},
]
