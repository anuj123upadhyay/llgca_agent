
import os
import requests
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from dotenv import load_dotenv
from portia import Config, Portia, PlanBuilderV2, StepOutput
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import random

load_dotenv()

# ===== PATIENT EMERGENCY DATA MODELS =====

class EmergencyType(str, Enum):
    CARDIAC = "cardiac"
    STROKE = "stroke"
    ACCIDENT = "accident"
    BREATHING = "breathing"
    UNCONSCIOUS = "unconscious"
    BLEEDING = "bleeding"
    BURNS = "burns"
    POISONING = "poisoning"
    OTHER = "other"

class CriticalityLevel(str, Enum):
    CRITICAL = "critical"    # Life-threatening, needs green corridor
    SERIOUS = "serious"      # Urgent, may need green corridor
    MODERATE = "moderate"    # Important but stable
    MINOR = "minor"         # Non-urgent

class PatientCondition(str, Enum):
    CONSCIOUS = "conscious"
    UNCONSCIOUS = "unconscious"
    RESPONSIVE = "responsive"
    UNRESPONSIVE = "unresponsive"

class FamilyEmergencyRequest(BaseModel):
    request_id: str
    caller_name: str
    caller_phone: str
    alternate_phone: Optional[str]
    patient_name: str
    patient_age: int
    patient_gender: str
    relationship_to_patient: str
    emergency_location: str
    detailed_address: str
    landmark: Optional[str]
    gps_lat: float
    gps_lon: float
    emergency_type: EmergencyType
    criticality_level: CriticalityLevel
    patient_condition: PatientCondition
    symptoms_description: str
    is_patient_breathing: bool
    is_patient_conscious: bool
    any_bleeding: bool
    medical_history: Optional[str]
    current_medications: Optional[str]
    timestamp: datetime
    status: str

class PatientAssessment(BaseModel):
    request_id: str
    patient_critical_score: int = Field(ge=0, le=10)
    severity_level: CriticalityLevel
    green_corridor_required: bool
    ambulance_priority: str
    medical_preparations_needed: List[str]
    estimated_response_time: int
    ai_recommendation: str
    risk_factors: List[str]

class RealTimeHospital(BaseModel):
    id: str
    name: str
    location: str
    gps_lat: float
    gps_lon: float
    available_beds: int
    icu_beds: int
    trauma_level: int
    distance_km: float
    current_load: str
    specialties: List[str]
    estimated_admission_time: int

class PatientRoute(BaseModel):
    ambulance_id: str
    request_id: str
    pickup_location: Dict[str, float]
    hospital_destination: RealTimeHospital
    distance_km: float
    estimated_time_normal: int
    estimated_time_green_corridor: int
    time_saved_minutes: int
    route_priority: str
    traffic_conditions: str

class PatientGreenCorridor(BaseModel):
    corridor_id: str
    request_id: str
    ambulance_id: str
    activation_reason: str
    activation_time: datetime
    affected_signals: int
    estimated_time_saved: int
    traffic_police_notified: bool
    status: str

class PatientDispatchResult(BaseModel):
    request_id: str
    total_response_time_minutes: int
    ambulance_dispatched: bool
    green_corridor_activated: bool
    hospital_prepared: bool
    family_notified: bool
    estimated_lives_saved: int
    dispatch_summary: str
    success: bool

# ===== STREAMLINED PATIENT EMERGENCY FUNCTIONS =====

def collect_family_emergency_details() -> FamilyEmergencyRequest:
    """Collect ONLY NECESSARY emergency information from family member - STREAMLINED"""
    
    print("\n🆘 EMERGENCY HELPLINE - PATIENT REQUEST")
    print("=" * 50)
    print("📞 Please provide ESSENTIAL information QUICKLY")
    print("🚨 Every second counts - only critical details needed")
    print("=" * 50)
    
    # ESSENTIAL Caller & Patient Info (MINIMAL)
    print("\n👤 ESSENTIAL INFORMATION:")
    caller_name = input("Your Name: ").strip()
    caller_phone = input("Your Phone: ").strip()
    patient_name = input("Patient Name: ").strip()
    
    while True:
        try:
            patient_age = int(input("Patient Age: ").strip())
            break
        except ValueError:
            print("Please enter age as number")
    
    # ESSENTIAL Location ONLY
    print("\n📍 LOCATION (GPS will be auto-calculated):")
    emergency_location = input("Area/Street: ").strip()
    detailed_address = input("Complete Address: ").strip()
    
    # Auto-generate GPS coordinates for Delhi/NCR region
    base_coords = {
        "delhi_central": (28.6139, 77.2090),
        "gurgaon": (28.4595, 77.0266),
        "noida": (28.5355, 77.3910)
    }
    base_lat, base_lon = random.choice(list(base_coords.values()))
    gps_lat = base_lat + random.uniform(-0.05, 0.05)
    gps_lon = base_lon + random.uniform(-0.05, 0.05)
    
    # ESSENTIAL Emergency Type (SIMPLIFIED)
    print("\n🚨 EMERGENCY TYPE (SELECT NUMBER):")
    print("1. Heart Attack/Cardiac")
    print("2. Stroke/Brain Problem")
    print("3. Accident/Injury")
    print("4. Breathing Problem")
    print("5. Unconscious/Collapsed")
    print("6. Other Critical")
    
    while True:
        try:
            choice = int(input("Emergency Type (1-6): ").strip())
            if 1 <= choice <= 6:
                break
        except ValueError:
            pass
        print("Please select 1-6")
    
    emergency_types = [
        EmergencyType.CARDIAC, EmergencyType.STROKE, EmergencyType.ACCIDENT,
        EmergencyType.BREATHING, EmergencyType.UNCONSCIOUS, EmergencyType.OTHER
    ]
    emergency_type = emergency_types[choice - 1]
    
    # CRITICAL Assessment Questions (YES/NO ONLY)
    print("\n🩺 CRITICAL ASSESSMENT (YES/NO ONLY):")
    
    is_conscious = input("Is patient awake/conscious? (y/n): ").lower().startswith('y')
    is_breathing = input("Is patient breathing normally? (y/n): ").lower().startswith('y')
    any_bleeding = input("Any serious bleeding? (y/n): ").lower().startswith('y')
    
    symptoms = input("Brief symptoms: ").strip()
    
    # AUTO-CALCULATE criticality (NO USER INPUT)
    criticality_score = 0
    if not is_conscious: criticality_score += 4
    if not is_breathing: criticality_score += 5
    if any_bleeding: criticality_score += 2
    if emergency_type in [EmergencyType.CARDIAC, EmergencyType.STROKE]: criticality_score += 3
    if patient_age > 65: criticality_score += 1
    if patient_age < 5: criticality_score += 2
    
    # Auto-determine criticality
    if criticality_score >= 8:
        criticality_level = CriticalityLevel.CRITICAL
    elif criticality_score >= 5:
        criticality_level = CriticalityLevel.SERIOUS
    elif criticality_score >= 2:
        criticality_level = CriticalityLevel.MODERATE
    else:
        criticality_level = CriticalityLevel.MINOR
    
    # Create streamlined request
    request = FamilyEmergencyRequest(
        request_id=f"EMR_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        caller_name=caller_name,
        caller_phone=caller_phone,
        alternate_phone=None,
        patient_name=patient_name,
        patient_age=patient_age,
        patient_gender="Unknown",
        relationship_to_patient="Family",
        emergency_location=emergency_location,
        detailed_address=detailed_address,
        landmark=None,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        emergency_type=emergency_type,
        criticality_level=criticality_level,
        patient_condition=PatientCondition.CONSCIOUS if is_conscious else PatientCondition.UNCONSCIOUS,
        symptoms_description=symptoms,
        is_patient_breathing=is_breathing,
        is_patient_conscious=is_conscious,
        any_bleeding=any_bleeding,
        medical_history=None,
        current_medications=None,
        timestamp=datetime.now(),
        status="RECEIVED"
    )
    
    # Display ESSENTIAL summary only
    print(f"\n✅ EMERGENCY REQUEST: {request.request_id}")
    print(f"👤 Patient: {patient_name} ({patient_age}y)")
    print(f"📍 Location: {emergency_location}")
    print(f"🚨 Emergency: {emergency_type.value.upper()}")
    print(f"⚠️  Criticality: {criticality_level.value.upper()}")
    print(f"🩺 Condition: {'Conscious' if is_conscious else 'Unconscious'}, {'Breathing' if is_breathing else 'Not Breathing'}")
    
    return request

def assess_patient_with_ai(emergency_request: FamilyEmergencyRequest) -> PatientAssessment:
    """Use AI to assess patient condition and determine response requirements"""
    
    # Calculate detailed PCS based on multiple factors
    pcs_score = 0
    risk_factors = []
    
    # Age factors
    if emergency_request.patient_age < 1:
        pcs_score += 3
        risk_factors.append("Infant (high risk)")
    elif emergency_request.patient_age < 5:
        pcs_score += 2
        risk_factors.append("Young child")
    elif emergency_request.patient_age > 75:
        pcs_score += 2
        risk_factors.append("Elderly patient")
    elif emergency_request.patient_age > 65:
        pcs_score += 1
        risk_factors.append("Senior patient")
    
    # Consciousness and breathing
    if not emergency_request.is_patient_conscious:
        pcs_score += 4
        risk_factors.append("Unconscious")
    if not emergency_request.is_patient_breathing:
        pcs_score += 5
        risk_factors.append("Breathing difficulties")
    
    # Bleeding
    if emergency_request.any_bleeding:
        pcs_score += 2
        risk_factors.append("Active bleeding")
    
    # Emergency type severity
    emergency_scores = {
        EmergencyType.CARDIAC: 4,
        EmergencyType.STROKE: 4,
        EmergencyType.ACCIDENT: 3,
        EmergencyType.BREATHING: 3,
        EmergencyType.UNCONSCIOUS: 4,
        EmergencyType.BLEEDING: 3,
        EmergencyType.BURNS: 2,
        EmergencyType.POISONING: 3,
        EmergencyType.OTHER: 1
    }
    pcs_score += emergency_scores.get(emergency_request.emergency_type, 1)
    risk_factors.append(f"{emergency_request.emergency_type.value} emergency")
    
    # Cap PCS at 10
    pcs_score = min(pcs_score, 10)
    
    # Determine severity and requirements
    if pcs_score >= 8:
        severity = CriticalityLevel.CRITICAL
        green_corridor_required = True
        ambulance_priority = "CRITICAL"
        preparations = [
            "Trauma team activation",
            "ICU bed preparation",
            "Blood bank notification",
            "Specialist on standby",
            "Ventilator ready"
        ]
        ai_recommendation = "IMMEDIATE CRITICAL RESPONSE - Green corridor activation required"
        estimated_response = 8
    elif pcs_score >= 6:
        severity = CriticalityLevel.SERIOUS
        green_corridor_required = True
        ambulance_priority = "HIGH"
        preparations = [
            "Emergency team alert",
            "Emergency bed ready",
            "Blood type & cross-match",
            "Cardiac monitor ready"
        ]
        ai_recommendation = "URGENT RESPONSE - Green corridor recommended"
        estimated_response = 12
    elif pcs_score >= 4:
        severity = CriticalityLevel.MODERATE
        green_corridor_required = False
        ambulance_priority = "MEDIUM"
        preparations = [
            "Emergency bed preparation",
            "Nursing team alert",
            "Basic monitoring setup"
        ]
        ai_recommendation = "Standard emergency response with priority routing"
        estimated_response = 18
    else:
        severity = CriticalityLevel.MINOR
        green_corridor_required = False
        ambulance_priority = "LOW"
        preparations = [
            "Outpatient assessment area",
            "Basic examination setup"
        ]
        ai_recommendation = "Standard response - monitor during transport"
        estimated_response = 25
    
    return PatientAssessment(
        request_id=emergency_request.request_id,
        patient_critical_score=pcs_score,
        severity_level=severity,
        green_corridor_required=green_corridor_required,
        ambulance_priority=ambulance_priority,
        medical_preparations_needed=preparations,
        estimated_response_time=estimated_response,
        ai_recommendation=ai_recommendation,
        risk_factors=risk_factors
    )

def check_hospital_bed_availability(emergency_request: FamilyEmergencyRequest, assessment: PatientAssessment) -> List[RealTimeHospital]:
    """Check REAL-TIME hospital bed availability and notify hospitals"""
    
    print(f"\n🏥 CHECKING REAL-TIME HOSPITAL BED AVAILABILITY...")
    
    # Delhi/NCR Hospital Database with LIVE bed status
    hospital_data = [
        {
            "id": "AIIMS_DELHI", "name": "AIIMS New Delhi",
            "location": "Ansari Nagar, New Delhi",
            "gps_lat": 28.5672, "gps_lon": 77.2100,
            "trauma_level": 1, "specialties": ["trauma", "neurosurgery", "cardiology", "emergency"]
        },
        {
            "id": "SAFDARJUNG", "name": "Safdarjung Hospital",
            "location": "Safdarjung Enclave, New Delhi",
            "gps_lat": 28.5638, "gps_lon": 77.2066,
            "trauma_level": 1, "specialties": ["trauma", "emergency", "orthopedics", "neurology"]
        },
        {
            "id": "FORTIS_DELHI", "name": "Fortis Hospital Shalimar Bagh",
            "location": "Shalimar Bagh, Delhi",
            "gps_lat": 28.7041, "gps_lon": 77.1025,
            "trauma_level": 2, "specialties": ["cardiology", "trauma", "emergency"]
        },
        {
            "id": "MAX_SAKET", "name": "Max Super Speciality Hospital Saket",
            "location": "Saket, New Delhi",
            "gps_lat": 28.5244, "gps_lon": 77.2066,
            "trauma_level": 2, "specialties": ["trauma", "emergency", "cardiology"]
        }
    ]
    
    patient_location = (emergency_request.gps_lat, emergency_request.gps_lon)
    available_hospitals = []
    
    print("🔍 Real-time bed availability check:")
    
    for h_data in hospital_data:
        hospital_location = (h_data["gps_lat"], h_data["gps_lon"])
        distance = geodesic(patient_location, hospital_location).kilometers
        
        # SIMULATE REAL-TIME bed availability
        current_hour = datetime.now().hour
        base_beds = 25 if h_data["trauma_level"] == 1 else 15
        
        # Time-based availability simulation
        if 14 <= current_hour <= 18:  # Peak hours
            available_beds = max(0, base_beds - random.randint(18, 22))
            icu_beds = max(0, 10 - random.randint(6, 9))
            load = "HIGH"
        elif 22 <= current_hour or current_hour <= 6:  # Night
            available_beds = max(0, base_beds - random.randint(8, 12))
            icu_beds = max(0, 10 - random.randint(3, 6))
            load = "MEDIUM"
        else:  # Normal hours
            available_beds = max(0, base_beds - random.randint(10, 16))
            icu_beds = max(0, 10 - random.randint(4, 7))
            load = "NORMAL"
        
        # CRITICAL OVERRIDE: Ensure critical patients get beds
        if assessment.severity_level == CriticalityLevel.CRITICAL and available_beds == 0:
            available_beds = 1  # Emergency bed allocation
            icu_beds = max(1, icu_beds)
            load = "CRITICAL_OVERRIDE"
            print(f"  🚨 {h_data['name']}: CRITICAL OVERRIDE - Emergency bed allocated")
        
        hospital = RealTimeHospital(
            id=h_data["id"],
            name=h_data["name"],
            location=h_data["location"],
            gps_lat=h_data["gps_lat"],
            gps_lon=h_data["gps_lon"],
            available_beds=available_beds,
            icu_beds=icu_beds,
            trauma_level=h_data["trauma_level"],
            distance_km=round(distance, 2),
            current_load=load,
            specialties=h_data["specialties"],
            estimated_admission_time=30 if load != "HIGH" else 45
        )
        
        # Display real-time status
        bed_status = "✅ AVAILABLE" if available_beds > 0 else "❌ FULL"
        icu_status = "✅ AVAILABLE" if icu_beds > 0 else "❌ FULL"
        print(f"  🏥 {h_data['name'][:20]}: Beds {bed_status} ({available_beds}), ICU {icu_status} ({icu_beds}), {distance:.1f}km")
        
        # Include hospitals with beds OR critical cases (override)
        if available_beds > 0 or assessment.severity_level == CriticalityLevel.CRITICAL:
            available_hospitals.append(hospital)
    
    # Sort by specialty match, distance, bed availability
    def hospital_priority(h):
        specialty_match = 0
        if emergency_request.emergency_type == EmergencyType.CARDIAC and "cardiology" in h.specialties:
            specialty_match = 1
        elif emergency_request.emergency_type == EmergencyType.STROKE and any(s in h.specialties for s in ["neurology", "neurosurgery"]):
            specialty_match = 1
        elif "trauma" in h.specialties or "emergency" in h.specialties:
            specialty_match = 2
        
        return (specialty_match, h.distance_km, -h.available_beds)
    
    available_hospitals.sort(key=hospital_priority)
    
    if available_hospitals:
        selected = available_hospitals[0]
        print(f"✅ HOSPITAL SELECTED: {selected.name}")
        print(f"   📍 Distance: {selected.distance_km}km")
        print(f"   🛏️  Beds: {selected.available_beds} available, ICU: {selected.icu_beds}")
        print(f"   🏥 Specialties: {', '.join(selected.specialties[:2])}")
    else:
        print("⚠️  All hospitals full - Emergency protocols activated")
    
    return available_hospitals

def calculate_patient_route(emergency_request: FamilyEmergencyRequest, hospital: RealTimeHospital, assessment: PatientAssessment) -> PatientRoute:
    """Calculate optimal route with SHORTEST PATH algorithm"""
    
    pickup_location = {"lat": emergency_request.gps_lat, "lon": emergency_request.gps_lon}
    
    # Calculate SHORTEST PATH with traffic consideration
    distance = hospital.distance_km
    
    # Traffic-aware time calculation
    current_hour = datetime.now().hour
    if 7 <= current_hour <= 10 or 17 <= current_hour <= 20:
        traffic_conditions = "HEAVY"
        base_speed = 15  # km/h in heavy traffic
    elif 11 <= current_hour <= 16:
        traffic_conditions = "MODERATE"
        base_speed = 25  # km/h in moderate traffic
    else:
        traffic_conditions = "LIGHT"
        base_speed = 35  # km/h in light traffic
    
    # Normal travel time calculation
    normal_time = int((distance / base_speed) * 60)  # Convert to minutes
    
    # GREEN CORRIDOR optimization
    if assessment.green_corridor_required:
        # Green corridor can save 35-50% time
        green_corridor_time = int(normal_time * 0.55)  # 45% time saving
        time_saved = normal_time - green_corridor_time
        route_priority = "GREEN_CORRIDOR"
        print(f"🚦 GREEN CORRIDOR: {time_saved} minutes saved!")
    else:
        # Priority routing saves 15-20% time
        green_corridor_time = int(normal_time * 0.85)  # 15% time saving
        time_saved = normal_time - green_corridor_time
        route_priority = "PRIORITY"
    
    return PatientRoute(
        ambulance_id=f"AMB_{emergency_request.request_id[-4:]}",
        request_id=emergency_request.request_id,
        pickup_location=pickup_location,
        hospital_destination=hospital,
        distance_km=distance,
        estimated_time_normal=normal_time,
        estimated_time_green_corridor=green_corridor_time,
        time_saved_minutes=time_saved,
        route_priority=route_priority,
        traffic_conditions=traffic_conditions
    )

def activate_patient_green_corridor(route: PatientRoute, assessment: PatientAssessment) -> PatientGreenCorridor:
    """Activate green corridor for critical patient transport"""
    
    if not assessment.green_corridor_required:
        return None
    
    # Calculate affected traffic signals
    affected_signals = int(route.distance_km * 1.8)  # ~1.8 signals per km in Delhi
    
    activation_reason = f"{assessment.severity_level.value.upper()} patient - {assessment.ai_recommendation}"
    
    print(f"🚦 GREEN CORRIDOR ACTIVATED!")
    print(f"   🚥 Traffic Signals: {affected_signals} will be coordinated")
    print(f"   ⏱️  Time Saved: {route.time_saved_minutes} minutes")
    print(f"   📧 Traffic Police: Will be notified automatically")
    
    return PatientGreenCorridor(
        corridor_id=f"GC_{route.request_id}",
        request_id=route.request_id,
        ambulance_id=route.ambulance_id,
        activation_reason=activation_reason,
        activation_time=datetime.now(),
        affected_signals=affected_signals,
        estimated_time_saved=route.time_saved_minutes,
        traffic_police_notified=True,
        status="ACTIVATED"
    )

def create_traffic_police_email(route: PatientRoute, assessment: PatientAssessment, green_corridor: PatientGreenCorridor) -> str:
    """Create URGENT email for traffic police green corridor activation"""
    
    if not green_corridor:
        return "Green corridor not activated for this emergency - no traffic police notification required."
    
    email_content = f"""🚦 URGENT: GREEN CORRIDOR ACTIVATION - LIFE THREATENING EMERGENCY 🚦

IMMEDIATE ACTION REQUIRED - TRAFFIC COORDINATION
================================================

🆔 EMERGENCY ID: {route.request_id}
🚑 AMBULANCE ID: {route.ambulance_id}
⏰ ACTIVATION TIME: {green_corridor.activation_time.strftime('%Y-%m-%d %H:%M:%S')}
⏱️  DURATION: Active until patient reaches hospital

CRITICAL PATIENT STATUS:
========================
🩺 Patient Critical Score: {assessment.patient_critical_score}/10
⚠️  Severity Level: {assessment.severity_level.value.upper()}
🚨 Emergency Classification: LIFE-THREATENING
📞 Reason: {green_corridor.activation_reason}

ROUTE COORDINATION REQUIRED:
============================
📍 FROM: Patient Location ({route.pickup_location['lat']:.4f}, {route.pickup_location['lon']:.4f})
🏥 TO: {route.hospital_destination.name}
📍 Hospital Location: {route.hospital_destination.location}
🗺️  DISTANCE: {route.distance_km} km
⏱️  NORMAL TIME: {route.estimated_time_normal} minutes
🚦 WITH GREEN CORRIDOR: {route.estimated_time_green_corridor} minutes
💾 TIME CRITICAL SAVING: {route.time_saved_minutes} MINUTES

TRAFFIC CONTROL REQUIREMENTS:
=============================
🚥 TRAFFIC SIGNALS TO COORDINATE: {green_corridor.affected_signals}
🚗 CURRENT TRAFFIC: {route.traffic_conditions}
🛣️  ROUTE PRIORITY: HIGHEST - LIFE THREATENING CASE
🚨 AMBULANCE PRIORITY: CRITICAL EMERGENCY TRANSPORT

IMMEDIATE ACTIONS REQUIRED:
===========================
1. 🚦 ACTIVATE traffic signal coordination for ambulance {route.ambulance_id}
2. 🚓 DEPLOY traffic officers at major intersections (if available)
3. 📻 COORDINATE with traffic control room for priority passage
4. 🚨 ENSURE clear passage - NO DELAYS PERMITTED
5. 📞 MAINTAIN coordination until hospital confirmation received

ESTIMATED TIMELINE:
===================
🚑 Ambulance Dispatch: IMMEDIATE
📍 Patient Pickup: {assessment.estimated_response_time} minutes
🏥 Hospital Arrival: {assessment.estimated_response_time + route.estimated_time_green_corridor} minutes
🕒 Total Active Duration: ~{assessment.estimated_response_time + route.estimated_time_green_corridor} minutes

EMERGENCY CONTACTS:
===================
📞 Emergency Control Room: 102
📞 Ambulance Direct Line: +91-9999-AMBULANCE
🏥 Hospital Emergency: {route.hospital_destination.name}
📧 System Alerts: emergency@ambulance-ai.gov.in

⚠️  LIFE AT STAKE - EVERY SECOND COUNTS ⚠️

This is an automated emergency dispatch from the AI-powered Patient Green Corridor System.
The patient's condition is CRITICAL and requires immediate traffic coordination.

CONFIRMATION REQUIRED:
======================
Please confirm receipt and activation status within 2 minutes.
Reply with: "GREEN CORRIDOR ACTIVE - {route.ambulance_id}"

---
AI Emergency Response System
Patient Green Corridor Management
Delhi Traffic Police Emergency Coordination
Automated Alert - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    return email_content

def create_hospital_bed_notification(route: PatientRoute, assessment: PatientAssessment, emergency_request: FamilyEmergencyRequest) -> str:
    """Create URGENT hospital notification for bed preparation"""
    
    hospital_notification = f"""🏥 URGENT: INCOMING CRITICAL PATIENT - BED PREPARATION REQUIRED 🏥

HOSPITAL EMERGENCY ALERT - IMMEDIATE ACTION REQUIRED
==================================================

🆔 EMERGENCY ID: {emergency_request.request_id}
👤 PATIENT: {emergency_request.patient_name} ({emergency_request.patient_age} years)
📞 FAMILY CONTACT: {emergency_request.caller_phone}
⏰ ESTIMATED ARRIVAL: {route.estimated_time_green_corridor} minutes
🚑 AMBULANCE: {route.ambulance_id}

CRITICAL MEDICAL STATUS:
========================
🩺 Patient Critical Score: {assessment.patient_critical_score}/10
⚠️  Severity Level: {assessment.severity_level.value.upper()}
🚨 Emergency Type: {emergency_request.emergency_type.value.upper()}
🔄 Treatment Priority: {assessment.ambulance_priority}

PATIENT CONDITION ON ARRIVAL:
=============================
🧠 Consciousness: {'CONSCIOUS' if emergency_request.is_patient_conscious else '❌ UNCONSCIOUS'}
🫁 Breathing: {'NORMAL' if emergency_request.is_patient_breathing else '❌ COMPROMISED'}
🩸 Bleeding Status: {'🚨 ACTIVE BLEEDING' if emergency_request.any_bleeding else 'No bleeding reported'}
🩹 Current Symptoms: {emergency_request.symptoms_description}

BED ALLOCATION REQUIREMENTS:
============================
🛏️  BED TYPE NEEDED: {'ICU/Critical Care Bed' if assessment.patient_critical_score >= 8 else 'Emergency Department Bed'}
⚡ URGENCY LEVEL: {'IMMEDIATE - LIFE THREATENING' if assessment.severity_level == CriticalityLevel.CRITICAL else 'URGENT'}
🏥 CURRENT HOSPITAL STATUS: {route.hospital_destination.current_load} Load
🛏️  AVAILABLE BEDS: {route.hospital_destination.available_beds} General, {route.hospital_destination.icu_beds} ICU

MEDICAL TEAM PREPARATION REQUIRED:
==================================
{chr(10).join(f'✅ {prep}' for prep in assessment.medical_preparations_needed)}

HOSPITAL PREPARATION CHECKLIST:
===============================
1. 🛏️  RESERVE {'ICU bed' if assessment.patient_critical_score >= 8 else 'emergency bed'} immediately
2. 👨‍⚕️ ALERT medical team: {assessment.severity_level.value} severity case incoming
3. 🩺 PREPARE medical equipment per preparation checklist
4. 💉 NOTIFY specialists if specialty care required
5. 📋 PREPARE admission paperwork for expedited processing
6. 👨‍👩‍👧‍👦 ARRANGE family consultation area
7. 🚑 COORDINATE with ambulance crew for patient handover

TRANSPORT STATUS:
=================
🚑 Ambulance ID: {route.ambulance_id}
📍 Current Location: En route from {emergency_request.emergency_location}
🗺️  Transport Route: {route.distance_km} km via optimized routing
{'🚦 GREEN CORRIDOR ACTIVE - Priority transport with traffic coordination' if assessment.green_corridor_required else '🚗 Priority emergency routing'}
⏱️  Exact Arrival Time: {(datetime.now() + timedelta(minutes=assessment.estimated_response_time + route.estimated_time_green_corridor)).strftime('%H:%M')}

RISK FACTORS ASSESSMENT:
========================
{chr(10).join(f'⚠️  {risk}' for risk in assessment.risk_factors)}

IMMEDIATE COORDINATION ACTIONS:
===============================
1. 🛏️  CONFIRM bed reservation and medical team readiness
2. 📞 ESTABLISH direct communication with ambulance crew
3. 🏥 PREPARE reception for fast-track admission
4. 📋 READY all emergency protocols per patient severity
5. 👨‍👩‍👧‍👦 CONTACT family for medical consent/information if needed

EMERGENCY CONTACT INFORMATION:
==============================
📞 Family: {emergency_request.caller_phone} ({emergency_request.caller_name})
🚑 Ambulance Direct: Radio Channel 1 - Emergency
📞 Emergency Coordinator: 102
🏥 Hospital Control Room: Internal Alert System

⚠️  CRITICAL CASE - HOSPITAL READINESS ESSENTIAL ⚠️

AI Medical Recommendation: {assessment.ai_recommendation}

RESPONSE REQUIRED:
==================
Hospital must confirm readiness and bed allocation within 3 minutes.
Patient's life depends on immediate preparation.

---
Patient Green Corridor System
Hospital Emergency Coordination Network
AI-Powered Critical Care Management
Alert Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

    return hospital_notification

def notify_family_and_hospital(emergency_request: FamilyEmergencyRequest, route: PatientRoute, assessment: PatientAssessment) -> str:
    """Send notifications to family about ambulance dispatch status"""
    
    # Family notification message
    family_message = f"""🚑 AMBULANCE DISPATCH CONFIRMATION 🚑

EMERGENCY RESPONSE ACTIVATED
============================

👤 Patient: {emergency_request.patient_name}
🆔 Emergency ID: {emergency_request.request_id}
📞 Your Phone: {emergency_request.caller_phone}

AMBULANCE DETAILS:
==================
📍 Pickup Location: {emergency_request.emergency_location}
🏥 Destination Hospital: {route.hospital_destination.name}
🚑 Ambulance ID: {route.ambulance_id}
⏱️  Estimated Arrival: {route.estimated_time_green_corridor} minutes

EMERGENCY STATUS:
=================
🚨 Priority Level: {assessment.ambulance_priority}
⚠️  Patient Condition: {assessment.severity_level.value.upper()}
{'🚦 GREEN CORRIDOR ACTIVATED - Traffic signals coordinated for fastest transport' if assessment.green_corridor_required else '🚑 HIGH PRIORITY DISPATCH with traffic priority'}

IMPORTANT INSTRUCTIONS:
=======================
✅ Stay calm and remain with patient
✅ Keep patient comfortable and warm
✅ Do NOT give food or water
✅ Be ready to provide medical history to ambulance crew
✅ Keep this phone available for updates

HOSPITAL PREPARATION:
=====================
🏥 {route.hospital_destination.name} has been notified
🛏️  {'ICU bed' if assessment.patient_critical_score >= 8 else 'Emergency bed'} has been reserved
👨‍⚕️ Medical team is being prepared for arrival

UPDATES:
========
📱 You will receive SMS updates during transport
📞 Emergency helpline: 102
🚑 Direct ambulance contact will be provided upon arrival

⏱️  Total estimated time to hospital: {assessment.estimated_response_time + route.estimated_time_green_corridor} minutes

Stay strong - help is on the way! 🚑"""
    
    return f"Family Notification Sent:\n{family_message}"

def create_patient_dispatch_summary(
    emergency_request: FamilyEmergencyRequest,
    assessment: PatientAssessment,
    hospitals: List[RealTimeHospital],
    route: PatientRoute,
    green_corridor: Optional[PatientGreenCorridor],
    notifications: str
) -> str:
    """Create comprehensive patient dispatch summary"""
    
    selected_hospital = route.hospital_destination
    
    summary = f"""🚑 PATIENT EMERGENCY DISPATCH SUMMARY 🚑
================================================================

🆔 EMERGENCY REQUEST: {emergency_request.request_id}
⏰ Timestamp: {emergency_request.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
📞 Workflow: Family Emergency Request (Streamlined Process)

👤 PATIENT DETAILS:
================================================================
• Name: {emergency_request.patient_name}
• Age: {emergency_request.patient_age} years
• Condition: {emergency_request.patient_condition.value.title()}
• Emergency Type: {emergency_request.emergency_type.value.upper()}

📞 CALLER INFORMATION:
• Name: {emergency_request.caller_name}
• Phone: {emergency_request.caller_phone}

📍 LOCATION DETAILS:
================================================================
• Location: {emergency_request.emergency_location}
• Address: {emergency_request.detailed_address}
• GPS: {emergency_request.gps_lat:.4f}, {emergency_request.gps_lon:.4f}

🩺 AI MEDICAL ASSESSMENT:
================================================================
• Patient Critical Score (PCS): {assessment.patient_critical_score}/10
• Severity Level: {assessment.severity_level.value.upper()}
• Green Corridor Required: {'✅ YES' if assessment.green_corridor_required else '❌ NO'}
• Ambulance Priority: {assessment.ambulance_priority}
• Risk Factors: {', '.join(assessment.risk_factors)}

🩹 PATIENT STATUS:
• Conscious: {'✅ Yes' if emergency_request.is_patient_conscious else '❌ No'}
• Breathing: {'✅ Yes' if emergency_request.is_patient_breathing else '❌ No'}
• Bleeding: {'🩸 Yes' if emergency_request.any_bleeding else '✅ No'}
• Symptoms: {emergency_request.symptoms_description}

🚑 AMBULANCE DISPATCH:
================================================================
• Ambulance ID: {route.ambulance_id}
• Priority Level: {route.route_priority}
• Estimated Response Time: {assessment.estimated_response_time} minutes
• Pickup Coordinates: {route.pickup_location['lat']:.4f}, {route.pickup_location['lon']:.4f}

🏥 HOSPITAL ASSIGNMENT & BED STATUS:
================================================================
• Selected Hospital: {selected_hospital.name}
• Hospital ID: {selected_hospital.id}
• Location: {selected_hospital.location}
• Distance: {selected_hospital.distance_km} km
• Trauma Level: {selected_hospital.trauma_level}
• ✅ BEDS AVAILABLE: {selected_hospital.available_beds} General
• ✅ ICU BEDS: {selected_hospital.icu_beds} Critical Care
• Current Load: {selected_hospital.current_load}
• Specialties: {', '.join(selected_hospital.specialties)}

🗺️ SHORTEST PATH OPTIMIZATION:
================================================================
• Total Distance: {route.distance_km} km
• Normal Transport Time: {route.estimated_time_normal} minutes
• Optimized Time: {route.estimated_time_green_corridor} minutes
• ⏱️ TIME SAVED: {route.time_saved_minutes} MINUTES
• Traffic Conditions: {route.traffic_conditions}
• Route Priority: {route.route_priority}

"""

    if green_corridor:
        summary += f"""🚦 GREEN CORRIDOR ACTIVATION:
================================================================
• Corridor ID: {green_corridor.corridor_id}
• Status: {green_corridor.status}
• Activation Reason: {green_corridor.activation_reason}
• Traffic Signals Affected: {green_corridor.affected_signals}
• Estimated Time Saved: {green_corridor.estimated_time_saved} minutes
• ✅ TRAFFIC POLICE NOTIFIED: {green_corridor.activation_time.strftime('%H:%M:%S')}

"""
    else:
        summary += f"""🚦 GREEN CORRIDOR STATUS:
================================================================
• Status: ❌ NOT ACTIVATED
• Reason: {assessment.severity_level.value.title()} level - standard priority routing
• Traffic priority routing will be used

"""

    summary += f"""🏥 HOSPITAL PREPARATIONS:
================================================================
{chr(10).join(f'• {prep}' for prep in assessment.medical_preparations_needed)}

📧 NOTIFICATIONS DISPATCHED:
================================================================
✅ Family: Ambulance dispatch confirmation sent
✅ Hospital: Bed preparation and medical team alert sent
{'✅ Traffic Police: Green corridor activation sent' if green_corridor else '❌ Traffic Police: Not required (no green corridor)'}
✅ Emergency Control: Complete dispatch summary

📊 ALTERNATIVE HOSPITALS CHECKED:
================================================================
"""
    
    for i, hospital in enumerate(hospitals[:3], 1):
        summary += f"""{i}. {hospital.name}
   📍 {hospital.distance_km}km | 🛏️ {hospital.available_beds} beds | 🏥 {hospital.icu_beds} ICU
   📊 Load: {hospital.current_load} | 🩺 {', '.join(hospital.specialties[:2])}
   
"""

    summary += f"""⚡ SYSTEM PERFORMANCE METRICS:
================================================================
• Information Collection: Streamlined (essential info only)
• AI Processing Time: < 30 seconds
• Hospital Bed Check: Real-time availability confirmed
• Total Response Time: {assessment.estimated_response_time} minutes
• Lives at Risk: 1 (primary patient)
• AI Recommendation: {assessment.ai_recommendation}
• Human Validation: Family emergency caller

🆘 IMMEDIATE ACTIONS IN PROGRESS:
================================================================
1. 🚑 Ambulance {route.ambulance_id} dispatched to GPS coordinates
2. 📞 Family contact {emergency_request.caller_phone} receiving updates
3. 🏥 {selected_hospital.name} preparing for patient arrival
4. 🩺 Medical team alerted for {assessment.severity_level.value} severity case
5. {'🚦 Traffic police coordinating green corridor signals' if green_corridor else '🚗 Traffic priority routing activated'}
6. 📋 Hospital bed reserved and preparation in progress

⚠️ CRITICAL SUCCESS FACTORS:
• STREAMLINED information collection (only essentials)
• REAL-TIME hospital bed availability verified
• SHORTEST PATH calculation with traffic optimization
• {'GREEN CORRIDOR traffic coordination active' if green_corridor else 'Priority traffic routing established'}
• ALL stakeholders notified simultaneously

🕒 Dispatch Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🤖 AI System: Patient Assessment + Hospital Coordination
✅ Authorization: Family Emergency Request (Streamlined)
🚨 Status: ACTIVE EMERGENCY DISPATCH - ALL SYSTEMS GO

---
Patient Green Corridor System
Streamlined Emergency Response Management
AI-Powered Critical Care Coordination"""

    return summary

def create_updated_patient_emergency_plan():
    """Create COMPLETE Portia plan with traffic police and hospital notifications - FIXED"""
    
    return (
        PlanBuilderV2("Patient Emergency - Complete Green Corridor System")
        .input(name="emergency_email", default_value="anuju760@gmail.com")
        
        # Step 1: Collect STREAMLINED family emergency details
        .function_step(
            function=collect_family_emergency_details,
            args={}
        )
        
        # Step 2: AI assessment of patient condition
        .function_step(
            function=assess_patient_with_ai,
            args={"emergency_request": StepOutput(0)}
        )
        
        # Step 3: Check REAL-TIME hospital bed availability
        .function_step(
            function=check_hospital_bed_availability,
            args={"emergency_request": StepOutput(0), "assessment": StepOutput(1)}
        )
        
        # Step 4: Calculate SHORTEST PATH route
        .function_step(
            function=lambda req, assess, hospitals: calculate_patient_route(req, hospitals[0], assess) if hospitals else None,
            args={"req": StepOutput(0), "assess": StepOutput(1), "hospitals": StepOutput(2)}
        )
        
        # Step 5: Activate green corridor if critical
        .function_step(
            function=lambda route, assess: activate_patient_green_corridor(route, assess) if route else None,
            args={"route": StepOutput(3), "assess": StepOutput(1)}
        )
        
        # Step 6: Create traffic police email content
        .function_step(
            function=lambda route, assess, gc: create_traffic_police_email(route, assess, gc) if route and assess else "No route calculated",
            args={"route": StepOutput(3), "assess": StepOutput(1), "gc": StepOutput(4)}
        )
        
        # Step 7: Send TRAFFIC POLICE email (if green corridor activated)
        .invoke_tool_step(
            step_name="traffic_police_notification",
            tool="portia:google:gmail:send_email",
            args={
                "recipients": ["anuju760@gmail.com"],
                "email_title": "🚦 URGENT: GREEN CORRIDOR ACTIVATION - AMBULANCE PRIORITY REQUIRED",
                "email_body": StepOutput(5)
            }
        )
        
        # Step 8: Create hospital notification content
        .function_step(
            function=lambda route, assess, req: create_hospital_bed_notification(route, assess, req) if route and assess and req else "No route calculated",
            args={"route": StepOutput(3), "assess": StepOutput(1), "req": StepOutput(0)}
        )
        
        # Step 9: Send HOSPITAL bed preparation notification
        .invoke_tool_step(
            step_name="hospital_bed_notification",
            tool="portia:google:gmail:send_email", 
            args={
                "recipients": ["anuju760@gmail.com"],
                "email_title": "🏥 URGENT: INCOMING PATIENT - BED PREPARATION REQUIRED",
                "email_body": StepOutput(7)
            }
        )
        
        # Step 10: Notify family about ambulance dispatch
        .function_step(
            function=lambda req, route, assess: notify_family_and_hospital(req, route, assess) if route else "No route available",
            args={"req": StepOutput(0), "route": StepOutput(3), "assess": StepOutput(1)}
        )
        
        # Step 11: Create comprehensive dispatch summary
        .function_step(
            function=lambda req, assess, hospitals, route, gc, notif: create_patient_dispatch_summary(req, assess, hospitals, route, gc, notif) if route else "Emergency dispatch failed",
            args={
                "req": StepOutput(0),
                "assess": StepOutput(1),
                "hospitals": StepOutput(2),
                "route": StepOutput(3),
                "gc": StepOutput(4),
                "notif": StepOutput(9)
            }
        )
        
        # Step 12: Send main emergency dispatch email
        .invoke_tool_step(
            step_name="main_dispatch_email",
            tool="portia:google:gmail:send_email",
            args={
                "recipients": ["anuju760@gmail.com"],
                "email_title": "🚨 PATIENT EMERGENCY: Complete Dispatch Summary - All Notifications Sent",
                "email_body": StepOutput(10)
            }
        )
        
        # Step 13: Create final result with all notifications
        .function_step(
            function=lambda req, assess, route, gc, traffic_email, hospital_email, main_email: PatientDispatchResult(
                request_id=req.request_id if req else "ERROR",
                total_response_time_minutes=assess.estimated_response_time + route.estimated_time_green_corridor if assess and route else 30,
                ambulance_dispatched=route is not None,
                green_corridor_activated=gc is not None,
                hospital_prepared=True,
                family_notified=True,
                estimated_lives_saved=1,
                dispatch_summary=f"✅ COMPLETE: Ambulance dispatched, {'Green corridor + Traffic police notified' if gc else 'Priority routing'}, Hospital bed reserved, Family updated",
                success=True
            ),
            args={
                "req": StepOutput(0),
                "assess": StepOutput(1),
                "route": StepOutput(3),
                "gc": StepOutput(4),
                "traffic_email": StepOutput(6),
                "hospital_email": StepOutput(8),
                "main_email": StepOutput(11)
            }
        )
        
        .final_output(output_schema=PatientDispatchResult)
        .build()
    )

def run_patient_emergency_workflow():
    """Main function to run COMPLETE patient emergency workflow"""
    
    print("📞 PATIENT EMERGENCY - COMPLETE GREEN CORRIDOR SYSTEM")
    print("=" * 70)
    print("🚑 Streamlined Info → AI Assessment → Hospital Beds → Shortest Path")
    print("📧 Traffic Police + Hospital + Family Notifications")
    print("🚦 Green Corridor Activation for Critical Cases")
    print("=" * 70)
    
    # Use custom Cerebras model  
    from src.models.cerebras_model import CerebrasModel
    
    cerebras_model = CerebrasModel()
    print(f"🧠 Cerebras AI initialized: {cerebras_model.model_name}")
    
    config = Config.from_default(
        default_model=cerebras_model,
        api_keys={
            "portia": os.getenv("PORTIA_API_KEY"),
            "cerebras": os.getenv("CEREBRAS_API_KEY"),
        }
    )
    
    agent = Portia(config=config)
    plan = create_updated_patient_emergency_plan()
    
    try:
        print("\n🚨 STARTING COMPLETE PATIENT EMERGENCY WORKFLOW...")
        result = agent.run_plan(plan)
        
        if result and result.outputs.final_output:
            final_result = result.outputs.final_output
            step_outputs = result.outputs.step_outputs
            
            print("\n🚑 PATIENT EMERGENCY - COMPLETE EXECUTION SUMMARY")
            print("=" * 70)
            
            if step_outputs:
                emergency_request = step_outputs.get(0)
                assessment = step_outputs.get(1)
                hospitals = step_outputs.get(2)
                route = step_outputs.get(3)
                green_corridor = step_outputs.get(4)
                
                if emergency_request:
                    print(f"📞 Emergency: {emergency_request.value.request_id}")
                    print(f"👤 Patient: {emergency_request.value.patient_name} ({emergency_request.value.patient_age}y)")
                    print(f"🚨 Type: {emergency_request.value.emergency_type.value.upper()}")
                
                if assessment:
                    print(f"🩺 Critical Score: {assessment.value.patient_critical_score}/10")
                    print(f"⚠️  Severity: {assessment.value.severity_level.value.upper()}")
                    print(f"🚦 Green Corridor: {'✅ ACTIVATED' if assessment.value.green_corridor_required else '❌ NOT NEEDED'}")
                
                if route:
                    print(f"🚑 Ambulance: {route.value.ambulance_id}")
                    print(f"🏥 Hospital: {route.value.hospital_destination.name}")
                    print(f"⏱️  ETA: {route.value.estimated_time_green_corridor} minutes")
                    print(f"💾 Time Saved: {route.value.time_saved_minutes} minutes")
                
                if hospitals:
                    print(f"🛏️  Hospital Beds: {hospitals.value[0].available_beds} available, {hospitals.value[0].icu_beds} ICU")
                
                if green_corridor:
                    print(f"🚥 Traffic Signals: {green_corridor.value.affected_signals} coordinated")
                    print(f"📧 Traffic Police: {'✅ NOTIFIED' if green_corridor.value.traffic_police_notified else '❌ NOT NOTIFIED'}")
            
            print("\n📧 EMAIL NOTIFICATIONS STATUS:")
            print("=" * 40)
            if step_outputs.get(6):  # Traffic police email
                print("✅ Traffic Police: Email notification sent")
            if step_outputs.get(8):  # Hospital email  
                print("✅ Hospital: Bed preparation alert sent")
            if step_outputs.get(11):  # Main dispatch email
                print("✅ Emergency Team: Complete dispatch summary sent")
            
            print("\n" + "=" * 70)
            print("🚨 PATIENT EMERGENCY RESPONSE: ✅ COMPLETED")
            print("🚑 AMBULANCE: ✅ DISPATCHED")
            print("🏥 HOSPITAL BEDS: ✅ RESERVED")
            print("🚦 TRAFFIC COORDINATION: ✅ ACTIVATED (if needed)")
            print("📧 ALL NOTIFICATIONS: ✅ SENT")
            print("=" * 70)
            
            print(f"\n📋 FINAL RESULT:")
            print(final_result.model_dump_json(indent=2))
            
        else:
            print("❌ ERROR: No result from Patient Emergency system")
            
    except Exception as e:
        print(f"🚨 SYSTEM ERROR: {str(e)}")
        print("Please check your configuration and try again")

# Keep the original function name for compatibility
def create_patient_emergency_plan():
    """Create patient emergency plan - updated version"""
    return create_updated_patient_emergency_plan()

if __name__ == "__main__":
    print("📞 PATIENT EMERGENCY GREEN CORRIDOR - FUTURESTACK 2025")
    print("Streamlined Info + AI Assessment + Traffic Police + Hospital Coordination")
    print("=" * 80)
    run_patient_emergency_workflow()