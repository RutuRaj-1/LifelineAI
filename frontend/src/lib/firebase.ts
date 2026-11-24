/**
 * LifeLine AI — Firebase & Firestore Integration Service
 * Configured for Project: lifeline-ai-cdabc
 * Storage Bucket: lifeline-ai-cdabc.firebasestorage.app
 */
import { initializeApp, getApps, getApp, FirebaseApp } from "firebase/app";
import { 
  getFirestore, 
  Firestore, 
  doc, 
  setDoc, 
  getDoc, 
  collection, 
  onSnapshot, 
  query, 
  where, 
  orderBy, 
  addDoc,
  serverTimestamp,
  Unsubscribe 
} from "firebase/firestore";
import { 
  getStorage, 
  FirebaseStorage, 
  ref, 
  uploadBytes, 
  getDownloadURL 
} from "firebase/storage";
import { getAuth, Auth } from "firebase/auth";

// Firebase web application configuration
export const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyA3cjS15yehxU7v0h5MEv2I4fMVQxwG5NQ",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "lifeline-ai-cdabc.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "lifeline-ai-cdabc",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "lifeline-ai-cdabc.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "150977914510",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:150977914510:web:e1d518020b24b282ea0bdf"
};

// Singleton initialization
export const app: FirebaseApp = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
export const auth: Auth = getAuth(app);
export const db: Firestore = getFirestore(app);
export const storage: FirebaseStorage = getStorage(app);

// ============================================================================
// 1. Firestore Real-Time Emergency Case Endpoints
// ============================================================================

export interface FirestoreEmergencyCase {
  id: number;
  status: string;
  emergency_type: string;
  patient_id: number;
  hospital_id?: number | null;
  assigned_doctor_id?: number | null;
  current_lat?: number;
  current_lng?: number;
  eta_seconds?: number;
  symptoms?: string;
  priority_score?: number;
  updated_at?: any;
}

/**
 * Synchronize an Emergency Case document to Firestore for real-time edge streaming.
 */
export async function syncEmergencyCaseToFirestore(caseData: Partial<FirestoreEmergencyCase> & { id: number }): Promise<void> {
  try {
    const caseRef = doc(db, "emergency_cases", String(caseData.id));
    await setDoc(caseRef, {
      ...caseData,
      updated_at: serverTimestamp(),
    }, { merge: true });
  } catch (error) {
    console.warn("[Firebase] Could not sync emergency case to Firestore:", error);
  }
}

/**
 * Real-time listener for emergency case status, location updates, and ETA.
 */
export function subscribeToEmergencyCase(
  caseId: number | string,
  onUpdate: (data: FirestoreEmergencyCase) => void,
  onError?: (err: Error) => void
): Unsubscribe {
  const caseRef = doc(db, "emergency_cases", String(caseId));
  return onSnapshot(caseRef, (snapshot) => {
    if (snapshot.exists()) {
      onUpdate(snapshot.data() as FirestoreEmergencyCase);
    }
  }, (err) => {
    console.warn(`[Firebase] Emergency case subscription error for case #${caseId}:`, err);
    if (onError) onError(err);
  });
}

// ============================================================================
// 2. Firestore Hospital Resource & Capacity Attestation Endpoints
// ============================================================================

export interface FirestoreHospitalCapacity {
  hospital_id: number;
  resource_type: string;
  staffed_capacity: number;
  occupied_count: number;
  available: number;
  operational_status: string;
  status_source: string;
  updated_at?: any;
}

/**
 * Sync hospital attested resource capacity to Firestore.
 */
export async function syncHospitalCapacityToFirestore(
  hospitalId: number,
  resourceType: string,
  capacityData: Partial<FirestoreHospitalCapacity>
): Promise<void> {
  try {
    const resRef = doc(db, "hospital_resources", `${hospitalId}_${resourceType}`);
    await setDoc(resRef, {
      hospital_id: hospitalId,
      resource_type: resourceType,
      ...capacityData,
      updated_at: serverTimestamp(),
    }, { merge: true });
  } catch (error) {
    console.warn("[Firebase] Could not sync hospital capacity to Firestore:", error);
  }
}

/**
 * Real-time listener for hospital operational availability.
 */
export function subscribeToHospitalResources(
  hospitalId: number | string,
  onUpdate: (resources: FirestoreHospitalCapacity[]) => void
): Unsubscribe {
  const q = query(collection(db, "hospital_resources"), where("hospital_id", "==", Number(hospitalId)));
  return onSnapshot(q, (snapshot) => {
    const list: FirestoreHospitalCapacity[] = [];
    snapshot.forEach((docSnap) => {
      list.push(docSnap.data() as FirestoreHospitalCapacity);
    });
    onUpdate(list);
  }, (err) => {
    console.warn(`[Firebase] Hospital resources subscription error for #${hospitalId}:`, err);
  });
}

// ============================================================================
// 3. Firestore Field Incident Updates (Bystander & Family Updates)
// ============================================================================

export interface FirestoreIncidentReport {
  id?: string;
  emergency_case_id: number;
  reporter_type: string;
  reported_text: string;
  created_at?: any;
}

/**
 * Post a bystander/family incident update to Firestore.
 */
export async function addIncidentReportToFirestore(report: FirestoreIncidentReport): Promise<string> {
  const colRef = collection(db, "incident_reports");
  const docRef = await addDoc(colRef, {
    ...report,
    created_at: serverTimestamp(),
  });
  return docRef.id;
}

/**
 * Listen to incident reports for a specific emergency case.
 */
export function subscribeToIncidentReports(
  caseId: number,
  onUpdate: (reports: FirestoreIncidentReport[]) => void
): Unsubscribe {
  const q = query(
    collection(db, "incident_reports"),
    where("emergency_case_id", "==", caseId),
    orderBy("created_at", "asc")
  );
  return onSnapshot(q, (snapshot) => {
    const list: FirestoreIncidentReport[] = [];
    snapshot.forEach((d) => list.push({ id: d.id, ...d.data() } as FirestoreIncidentReport));
    onUpdate(list);
  }, (err) => {
    console.warn(`[Firebase] Incident reports subscription error for case #${caseId}:`, err);
  });
}

// ============================================================================
// 4. Firebase Cloud Storage Endpoints
// ============================================================================

/**
 * Upload a medical report document directly to Firebase Storage bucket.
 * Destination: gs://lifeline-ai-cdabc.firebasestorage.app/patients/{patientId}/{timestamp}_{filename}
 */
export async function uploadMedicalReportToFirebaseStorage(
  patientId: number,
  file: File
): Promise<{ downloadUrl: string; storagePath: string }> {
  const timestamp = Date.now();
  const safeFilename = file.name.replace(/[^a-zA-Z0-9._-]/g, "_");
  const storagePath = `patients/${patientId}/${timestamp}_${safeFilename}`;
  const fileRef = ref(storage, storagePath);

  const snapshot = await uploadBytes(fileRef, file, {
    contentType: file.type || "application/octet-stream",
    customMetadata: {
      patientId: String(patientId),
      originalName: file.name,
      uploadedAt: new Date().toISOString(),
    },
  });

  const downloadUrl = await getDownloadURL(snapshot.ref);
  return { downloadUrl, storagePath };
}

/**
 * Upload an official discharge summary or clinical document to Firebase Storage.
 * Destination: gs://lifeline-ai-cdabc.firebasestorage.app/emergencies/{caseId}/discharge_{timestamp}_{filename}
 */
export async function uploadDischargeDocumentToFirebaseStorage(
  caseId: number,
  file: File
): Promise<{ downloadUrl: string; storagePath: string }> {
  const timestamp = Date.now();
  const safeFilename = file.name.replace(/[^a-zA-Z0-9._-]/g, "_");
  const storagePath = `emergencies/${caseId}/discharge_${timestamp}_${safeFilename}`;
  const fileRef = ref(storage, storagePath);

  const snapshot = await uploadBytes(fileRef, file, {
    contentType: file.type || "application/pdf",
    customMetadata: {
      caseId: String(caseId),
      uploadedAt: new Date().toISOString(),
    },
  });

  const downloadUrl = await getDownloadURL(snapshot.ref);
  return { downloadUrl, storagePath };
}
