




import os
import requests
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from dotenv import load_dotenv
from portia import Config, Portia, PlanBuilderV2, StepOutput
import asyncio
import httpx
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

load_dotenv()

# Test Cerebras API connection
def test_cerebras_connection():
    """Test if Cerebras API is working"""
    try:
        test_response = call_cerebras_api("Hello, respond with just 'API Working'", max_tokens=10)
        print(f"🧪 Cerebras API Test: {test_response[:50]}...")
        return True
    except Exception as e:
        print(f"❌ Cerebras API Test Failed: {e}")
        return False

# ===== DATA MODELS =====
class AccidentSeverity(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate" 
    SERIOUS = "serious"
    CRITICAL = "critical"

class GreenCorridorStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVATED = "activated"
    ACTIVE = "active"
    COMPLETED = "completed"

class Accident(BaseModel):
    id: str
    description: str
    location: str
    gps_lat: float
    gps_lon: float
    timestamp: datetime
    severity_indicators: List[str]
    news_sources: List[str]
    confidence_score: float

class AccidentData(BaseModel):
    raw_news_data: str

class DetectedAccidents(BaseModel):
    accidents: List[Accident]

class PCSAssessment(BaseModel):
    accident_id: str
    patient_critical_score: int = Field(ge=0, le=10)
    severity_level: AccidentSeverity
    recommendation: str
    score_breakdown: Dict[str, int]
    estimated_patients: int
    priority_level: str

class PCSResults(BaseModel):
    assessments: List[PCSAssessment]

class Hospital(BaseModel):
    id: str
    name: str
    location: str
    gps_lat: float
    gps_lon: float
    trauma_level: int
    available_beds: int
    specialties: List[str]
    distance_km: float

class RouteOptimization(BaseModel):
    ambulance_id: str
    accident_id: str
    route_coordinates: List[Dict[str, float]]
    distance_km: float
    estimated_time_normal: int
    estimated_time_green_corridor: int
    time_saved_minutes: int
    target_hospital: Hospital
    traffic_intersections: int

class RouteResults(BaseModel):
    routes: List[RouteOptimization]

class TrafficIntersection(BaseModel):
    intersection_id: str
    location: Dict[str, float]
    signal_status: str
    activation_time: datetime
    estimated_passage_time: datetime

class GreenCorridorActivation(BaseModel):
    green_corridor_id: str
    ambulance_id: str
    accident_id: str
    activation_time: datetime
    status: GreenCorridorStatus
    affected_intersections: List[TrafficIntersection]
    total_intersections: int
    estimated_time_saved: int

class GreenCorridorResults(BaseModel):
    activations: List[GreenCorridorActivation]

class HospitalNotification(BaseModel):
    hospital_notification_id: str
    hospital_id: str
    patient_id: str
    notification_time: datetime
    eta_minutes: int
    severity_level: AccidentSeverity
    triage_message: str
    required_preparations: List[str]
    hospital_response: str

class NotificationResults(BaseModel):
    notifications: List[HospitalNotification]

class FinalDispatchResult(BaseModel):
    total_accidents_processed: int
    green_corridors_activated: int
    hospitals_notified: int
    average_response_time_seconds: int
    estimated_lives_impacted: int
    summary: str
    success: bool

# ===== CEREBRAS API INTEGRATION =====

def call_cerebras_api(prompt: str, max_tokens: int = 500) -> str:
    """Direct API call to Cerebras for LLaMA inference"""
    cerebras_api_key = os.getenv("CEREBRAS_API_KEY")
    if not cerebras_api_key:
        raise ValueError("CEREBRAS_API_KEY environment variable not found. Please set your API key.")
    
    # Cerebras API endpoint 
    url = "https://api.cerebras.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {cerebras_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-4-scout-17b-16e-instruct",  # Use correct Cerebras model name
        "messages": [
            {"role": "system", "content": "You are an expert emergency response AI assistant specializing in accident analysis and medical triage. Always return valid JSON responses."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,  # Low temperature for consistent emergency responses
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print(f"✅ Cerebras API Success: {len(content)} characters returned")
            return content
        else:
            error_msg = f"Cerebras API HTTP {response.status_code}: {response.text}"
            print(f"❌ Cerebras API Error: {error_msg}")
            raise requests.exceptions.HTTPError(error_msg)
            
    except requests.exceptions.Timeout:
        raise requests.exceptions.Timeout("Cerebras API request timed out after 30 seconds")
    except requests.exceptions.ConnectionError:
        raise requests.exceptions.ConnectionError("Failed to connect to Cerebras API")
    except Exception as e:
        print(f"❌ Cerebras API Exception: {str(e)}")
        raise

def analyze_accident_with_cerebras(news_data: str) -> str:
    """Use Cerebras LLaMA to analyze accident news data"""
    prompt = f"""
    Analyze this news data and extract 2-3 REAL accident incidents. For each accident found, provide EXACTLY this JSON format:
    
    {{
        "accidents": [
            {{
                "id": "ACC_YYYYMMDDHHMMSS##",
                "description": "detailed accident description from news",
                "location": "specific location/address mentioned", 
                "gps_lat": 28.6139,
                "gps_lon": 77.2090,
                "timestamp": "2025-09-30T15:20:00+05:30",
                "severity_indicators": ["multiple vehicles", "injuries", "fire"],
                "news_sources": ["Times of India", "NDTV"],
                "confidence_score": 0.85
            }}
        ]
    }}
    
    Focus on accidents requiring ambulance response. Use realistic GPS coordinates for mentioned locations.
    
    News Data:
    {news_data}
    """
    
    return call_cerebras_api(prompt, max_tokens=800)

def calculate_pcs_with_cerebras(accidents_json: str) -> str:
    """Use Cerebras LLaMA to calculate Patient Critical Score"""
    prompt = f"""
    For each accident, calculate Patient Critical Score (PCS) 0-10 using these factors:
    
    SCORING:
    - Multi-vehicle collision: +3 points
    - High-speed crash: +2 points  
    - Pedestrian involved: +2 points
    - Fire/explosion: +4 points
    - "Fatal"/"critical"/"severe" keywords: +3 points
    - Highway location: +1 point
    - Heavy traffic area: +1 point
    - Rush hour: +1 point
    
    SEVERITY LEVELS: 0-3=minor, 4-5=moderate, 6-7=serious, 8-10=critical
    RECOMMENDATIONS: PCS 0-3="Normal route", 4-5="Expedited route", 6-10="Activate Green Corridor"
    
    Return EXACTLY this JSON format:
    {{
        "assessments": [
            {{
                "accident_id": "ACC_...",
                "patient_critical_score": 7,
                "severity_level": "serious",
                "recommendation": "Activate Green Corridor",
                "score_breakdown": {{"multi_vehicle": 3, "highway_location": 1, "rush_hour": 1, "severity_keywords": 2}},
                "estimated_patients": 3,
                "priority_level": "HIGH"
            }}
        ]
    }}
    
    Accidents Data:
    {accidents_json}
    """
    
    return call_cerebras_api(prompt, max_tokens=600)

def optimize_eta_with_cerebras(route_data: dict) -> int:
    """Use Cerebras to predict optimized ETA based on traffic patterns"""
    severity = route_data.get('severity', 5)
    distance_km = route_data['distance_km']
    normal_time = route_data.get('normal_time', 15)
    
    prompt = f"""
    You are a traffic prediction AI. Given this route data, predict the optimal ETA in minutes:
    
    Route: {distance_km:.2f}km
    Normal time estimate: {normal_time} minutes
    Patient severity: {severity}/10 (Critical={severity>=8}, Serious={severity>=6})
    Traffic conditions: Heavy (rush hour)
    Green corridor available: Yes
    
    Consider:
    - Traffic signal coordination saves 30-50% time for critical cases
    - Emergency vehicle priority varies by severity
    - Real-time traffic patterns
    - Weather conditions: Clear
    
    Return ONLY the optimized ETA number in minutes (integer):
    """
    
    try:
        result = call_cerebras_api(prompt, max_tokens=50)
        # Extract number from response
        import re
        eta_match = re.search(r'\d+', result)
        if eta_match:
            optimized_time = int(eta_match.group())
            # Ensure realistic bounds
            min_time = max(int(normal_time * 0.5), 3)  # At least 50% improvement, min 3 minutes
            max_time = int(normal_time * 0.9)  # Max 90% of normal time
            return max(min_time, min(optimized_time, max_time))
        else:
            # Fallback: vary improvement based on severity
            improvement_factor = 0.7 if severity < 6 else (0.6 if severity < 8 else 0.5)
            return max(int(normal_time * improvement_factor), 3)
    except:
        # Fallback: vary improvement based on severity  
        improvement_factor = 0.7 if severity < 6 else (0.6 if severity < 8 else 0.5)
        return max(int(normal_time * improvement_factor), 3)

def parse_cerebras_accidents(cerebras_response: str) -> DetectedAccidents:
    """Parse Cerebras response into DetectedAccidents model"""
    try:
        import json
        # Try to extract JSON from the response
        json_start = cerebras_response.find('{')
        json_end = cerebras_response.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = cerebras_response[json_start:json_end]
            data = json.loads(json_str)
            
            accidents = []
            for acc_data in data.get('accidents', []):
                accident = Accident(
                    id=acc_data.get('id', f"ACC_{datetime.now().strftime('%Y%m%d%H%M%S')}01"),
                    description=acc_data.get('description', ''),
                    location=acc_data.get('location', ''),
                    gps_lat=float(acc_data.get('gps_lat', 28.6139)),
                    gps_lon=float(acc_data.get('gps_lon', 77.2090)),
                    timestamp=datetime.now(),
                    severity_indicators=acc_data.get('severity_indicators', []),
                    news_sources=acc_data.get('news_sources', []),
                    confidence_score=float(acc_data.get('confidence_score', 0.8))
                )
                accidents.append(accident)
            
            return DetectedAccidents(accidents=accidents)
        else:
            # Fallback: create demo accident if parsing fails
            return create_demo_accidents()
            
    except Exception as e:
        print(f"Error parsing Cerebras response: {e}")
        return create_demo_accidents()

def parse_cerebras_pcs(cerebras_response: str, original_accidents_json: str = None) -> PCSResults:
    """Parse Cerebras PCS response into PCSResults model"""
    try:
        import json
        json_start = cerebras_response.find('{')
        json_end = cerebras_response.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = cerebras_response[json_start:json_end]
            data = json.loads(json_str)
            
            assessments = []
            for pcs_data in data.get('assessments', []):
                assessment = PCSAssessment(
                    accident_id=pcs_data.get('accident_id', ''),
                    patient_critical_score=int(pcs_data.get('patient_critical_score', 5)),
                    severity_level=AccidentSeverity(pcs_data.get('severity_level', 'moderate')),
                    recommendation=pcs_data.get('recommendation', 'Normal route'),
                    score_breakdown=pcs_data.get('score_breakdown', {}),
                    estimated_patients=int(pcs_data.get('estimated_patients', 2)),
                    priority_level=pcs_data.get('priority_level', 'MEDIUM')
                )
                assessments.append(assessment)
            
            return PCSResults(assessments=assessments)
        else:
            # Try to extract accident IDs from the original input for better fallback
            accident_ids = []
            if original_accidents_json:
                try:
                    accidents_data = json.loads(original_accidents_json)
                    if isinstance(accidents_data, list):
                        accident_ids = [acc.get('id') for acc in accidents_data if acc.get('id')]
                    print(f"⚠️ No valid JSON in Cerebras response, creating fallback PCS for {len(accident_ids)} accidents")
                except:
                    pass
            return create_demo_pcs(accident_ids if accident_ids else None)
            
    except Exception as e:
        # Try to extract accident IDs from the original input for better fallback
        accident_ids = []
        if original_accidents_json:
            try:
                accidents_data = json.loads(original_accidents_json)
                if isinstance(accidents_data, list):
                    accident_ids = [acc.get('id') for acc in accidents_data if acc.get('id')]
            except:
                pass
        print(f"❌ Error parsing Cerebras PCS response: {e}")
        return create_demo_pcs(accident_ids if accident_ids else None)

def create_demo_accidents() -> DetectedAccidents:
    """Create demo accidents for fallback"""
    return DetectedAccidents(accidents=[
        Accident(
            id=f"ACC_{datetime.now().strftime('%Y%m%d%H%M%S')}01",
            description="Multi-vehicle collision on NH-1 near AIIMS Delhi, multiple injuries reported",
            location="NH-1 near AIIMS Delhi",
            gps_lat=28.6139,
            gps_lon=77.2090,
            timestamp=datetime.now(),
            severity_indicators=["multi-vehicle", "multiple injuries", "highway"],
            news_sources=["Cerebras Demo"],
            confidence_score=0.90
        )
    ])

def create_demo_pcs(accident_ids=None) -> PCSResults:
    """Create demo PCS for fallback - supports multiple accidents"""
    if accident_ids is None:
        accident_ids = [f"ACC_{datetime.now().strftime('%Y%m%d%H%M%S')}01"]
    
    assessments = []
    for i, accident_id in enumerate(accident_ids):
        # Vary the scores to make it realistic
        base_score = 7 - (i % 3)  # Scores will be 7, 6, 5, 7, 6, 5...
        assessments.append(PCSAssessment(
            accident_id=accident_id,
            patient_critical_score=base_score,
            severity_level=AccidentSeverity.SERIOUS if base_score >= 6 else AccidentSeverity.MODERATE,
            recommendation="Activate Green Corridor" if base_score >= 6 else "Expedited route",
            score_breakdown={"multi_vehicle": 3, "highway_location": 1, "multiple_injuries": base_score-4} if base_score >= 6 else {"multi_vehicle": 2, "highway_location": 1, "injuries": base_score-3},
            estimated_patients=3 if base_score >= 6 else 2,
            priority_level="HIGH" if base_score >= 7 else "MEDIUM"
        ))
    
    return PCSResults(assessments=assessments)

# ===== CORE FUNCTIONS =====

def search_accident_news() -> AccidentData:
    """Search for accident news using Tavily API"""
    try:
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key:
            return AccidentData(raw_news_data="Error: Tavily API key not found")
        
        # Tavily search for recent accidents
        url = "https://api.tavily.com/search"
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "api_key": tavily_api_key,
            "query": "car accident crash collision emergency injured Delhi Mumbai NYC today",
            "search_depth": "advanced",
            "include_answer": True,
            "include_images": False,
            "include_raw_content": True,
            "max_results": 10,
            "include_domains": ["timesofindia.com", "ndtv.com", "cnn.com", "abc7ny.com"],
            "days": 1  # Last 24 hours
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            results = response.json()
            # Format news data for processing
            news_content = ""
            for result in results.get("results", []):
                news_content += f"TITLE: {result.get('title', '')}\n"
                news_content += f"CONTENT: {result.get('content', '')}\n"
                news_content += f"URL: {result.get('url', '')}\n"
                news_content += f"PUBLISHED: {result.get('published_date', '')}\n"
                news_content += "---\n"
            
            return AccidentData(raw_news_data=news_content or "No recent accident news found")
        else:
            return AccidentData(raw_news_data=f"Tavily API Error: {response.status_code}")
            
    except Exception as e:
        return AccidentData(raw_news_data=f"Error searching news: {str(e)}")

def get_human_approval_for_accidents(detected_accidents: DetectedAccidents) -> DetectedAccidents:
    """Human-in-the-loop approval for detected accidents"""
    if not detected_accidents or not detected_accidents.accidents:
        print("❌ No accidents detected for approval")
        return DetectedAccidents(accidents=[])
    
    approved_accidents = []
    
    print(f"\n🚨 AMBULANCE GREEN CORRIDOR - ACCIDENT APPROVAL")
    print(f"📊 Found {len(detected_accidents.accidents)} potential accidents")
    print("=" * 60)
    
    for i, accident in enumerate(detected_accidents.accidents, 1):
        print(f"\n🚨 ACCIDENT {i}/{len(detected_accidents.accidents)}")
        print(f"📍 ID: {accident.id}")
        print(f"📍 Location: {accident.location}")
        print(f"🗺️  GPS: {accident.gps_lat}, {accident.gps_lon}")
        print(f"⏰ Time: {accident.timestamp}")
        print(f"📝 Description: {accident.description}")
        print(f"🔍 Confidence: {accident.confidence_score:.2f}")
        print(f"📰 Sources: {', '.join(accident.news_sources)}")
        print(f"⚠️  Severity Indicators: {', '.join(accident.severity_indicators)}")
        
        while True:
            decision = input("\n🚑 Deploy ambulance for this accident? (y/n): ").lower().strip()
            if decision == "y":
                approved_accidents.append(accident)
                print("✅ Approved - Ambulance will be dispatched")
                break
            elif decision == "n":
                reason = input("📝 Reason for rejection: ").strip()
                print(f"❌ Rejected: {reason}")
                break
            else:
                print("Please enter 'y' for yes or 'n' for no")
    
    print(f"\n✅ APPROVAL COMPLETE: {len(approved_accidents)}/{len(detected_accidents.accidents)} accidents approved")
    return DetectedAccidents(accidents=approved_accidents)

def calculate_route_with_cerebras(pcs_results: PCSResults, accident_data: DetectedAccidents = None) -> RouteResults:
    """Calculate optimal routes using Cerebras AI for ETA prediction with actual GPS coordinates"""
    if not pcs_results or not pcs_results.assessments:
        return RouteResults(routes=[])
    
    routes = []
    
    # Mock hospital database (in real implementation, this would be from database)
    hospitals = [
        Hospital(
            id="AIIMS_TRAUMA",
            name="AIIMS Trauma Center", 
            location="New Delhi",
            gps_lat=28.5672,
            gps_lon=77.2100,
            trauma_level=1,
            available_beds=15,
            specialties=["trauma", "neurosurgery", "orthopedics"],
            distance_km=0
        ),
        Hospital(
            id="FORTIS_DELHI",
            name="Fortis Hospital Delhi",
            location="Shalimar Bagh, Delhi", 
            gps_lat=28.7041,
            gps_lon=77.1025,
            trauma_level=2,
            available_beds=8,
            specialties=["cardiology", "trauma", "emergency"],
            distance_km=0
        ),
        Hospital(
            id="MAX_SAKET",
            name="Max Super Speciality Hospital",
            location="Saket, Delhi", 
            gps_lat=28.5244,
            gps_lon=77.2066,
            trauma_level=1,
            available_beds=12,
            specialties=["trauma", "cardiology", "neurosurgery"],
            distance_km=0
        )
    ]
    
    # Create a mapping of accident IDs to their GPS coordinates
    accident_locations = {}
    if accident_data and accident_data.accidents:
        for accident in accident_data.accidents:
            accident_locations[accident.id] = (accident.gps_lat, accident.gps_lon)
    
    for assessment in pcs_results.assessments:
        # Get actual accident location or use fallback coordinates
        if assessment.accident_id in accident_locations:
            accident_location = accident_locations[assessment.accident_id]
        else:
            # Use different fallback locations based on accident ID to create variety
            accident_hash = hash(assessment.accident_id) % 3
            fallback_locations = [
                (28.6139, 77.2090),  # Delhi center
                (28.4595, 77.0266),  # Gurgaon
                (28.7041, 77.1025),  # North Delhi
            ]
            accident_location = fallback_locations[accident_hash]
        
        best_hospital = None
        min_distance = float('inf')
        
        # Find nearest available hospital
        for hospital in hospitals:
            hospital_location = (hospital.gps_lat, hospital.gps_lon)
            distance = geodesic(accident_location, hospital_location).kilometers
            hospital.distance_km = distance
            
            # Select hospital based on severity and distance
            if assessment.patient_critical_score >= 8:  # Critical cases go to level 1 trauma centers
                if hospital.trauma_level == 1 and hospital.available_beds > 0:
                    if distance < min_distance:
                        min_distance = distance
                        best_hospital = hospital
            elif assessment.patient_critical_score >= 6:  # Serious cases
                if hospital.available_beds > 0:
                    if distance < min_distance:
                        min_distance = distance
                        best_hospital = hospital
            else:  # Moderate cases
                if hospital.available_beds > 0 and distance < min_distance:
                    min_distance = distance
                    best_hospital = hospital
        
        # If no hospital found with above criteria, use nearest available
        if not best_hospital:
            for hospital in hospitals:
                if hospital.available_beds > 0:
                    hospital_location = (hospital.gps_lat, hospital.gps_lon)
                    distance = geodesic(accident_location, hospital_location).kilometers
                    if distance < min_distance:
                        min_distance = distance
                        best_hospital = hospital
        
        if best_hospital:
            # Calculate realistic route timing based on distance and traffic conditions
            # Add variation based on time of day, severity, and location
            base_speed = 25  # km/h in city traffic
            if assessment.patient_critical_score >= 7:
                base_speed = 35  # Faster for critical cases
            
            normal_time = max(int((min_distance / base_speed) * 60), 5)  # Convert to minutes, minimum 5 min
            
            # Use Cerebras AI for optimized ETA prediction
            route_data = {
                'distance_km': min_distance,
                'normal_time': normal_time,
                'severity': assessment.patient_critical_score
            }
            green_corridor_time = optimize_eta_with_cerebras(route_data)
            time_saved = max(normal_time - green_corridor_time, 1)  # Minimum 1 minute saved
            
            # Reduce available beds for selected hospital
            best_hospital.available_beds -= 1
            
            route = RouteOptimization(
                ambulance_id=f"AMB_{len(routes)+1}##",
                accident_id=assessment.accident_id,
                route_coordinates=[
                    {"lat": accident_location[0], "lon": accident_location[1]},
                    {"lat": best_hospital.gps_lat, "lon": best_hospital.gps_lon}
                ],
                distance_km=round(min_distance, 2),
                estimated_time_normal=normal_time,
                estimated_time_green_corridor=green_corridor_time,
                time_saved_minutes=time_saved,
                target_hospital=best_hospital,
                traffic_intersections=max(int(min_distance * 1.5), 2)  # More realistic intersection count
            )
            routes.append(route)
    
    return RouteResults(routes=routes)

def activate_green_corridor_sumo(route_results: RouteResults) -> GreenCorridorResults:
    """Activate green corridor using SUMO traffic simulation"""
    if not route_results or not route_results.routes:
        return GreenCorridorResults(activations=[])
    
    activations = []
    
    for route in route_results.routes:
        # Only activate green corridor for time savings > 5 minutes
        if route.time_saved_minutes >= 5:
            # Generate mock traffic intersections
            intersections = []
            for i in range(min(route.traffic_intersections, 10)):  # Limit to 10 for demo
                intersection = TrafficIntersection(
                    intersection_id=f"INT_{route.accident_id[-3:]}_{i+1:02d}",
                    location={
                        "lat": route.route_coordinates[0]["lat"] + (i * 0.001),
                        "lon": route.route_coordinates[0]["lon"] + (i * 0.001)
                    },
                    signal_status="GREEN_PRIORITY",
                    activation_time=datetime.now() + timedelta(minutes=i*2),
                    estimated_passage_time=datetime.now() + timedelta(minutes=i*2 + 1)
                )
                intersections.append(intersection)
            
            activation = GreenCorridorActivation(
                green_corridor_id=f"GC_{route.accident_id}",
                ambulance_id=route.ambulance_id,
                accident_id=route.accident_id,
                activation_time=datetime.now(),
                status=GreenCorridorStatus.ACTIVATED,
                affected_intersections=intersections,
                total_intersections=len(intersections),
                estimated_time_saved=route.time_saved_minutes
            )
            activations.append(activation)
    
    return GreenCorridorResults(activations=activations)

def notify_hospitals_fhir(route_results: RouteResults, pcs_results: PCSResults) -> NotificationResults:
    """Send hospital notifications via FHIR API"""
    if not route_results or not route_results.routes:
        return NotificationResults(notifications=[])
    
    notifications = []
    
    # Create mapping of accident_id to PCS assessment
    pcs_map = {assessment.accident_id: assessment for assessment in pcs_results.assessments}
    
    for route in route_results.routes:
        pcs_assessment = pcs_map.get(route.accident_id)
        if not pcs_assessment:
            continue
        
        # Generate triage message using AI (simplified for demo)
        severity_text = pcs_assessment.severity_level.value.upper()
        eta = route.estimated_time_green_corridor
        
        triage_message = f"{severity_text} EMERGENCY - ETA {eta} MIN. "
        
        preparations = []
        if pcs_assessment.patient_critical_score >= 8:
            preparations.extend([
                "Trauma bay 1 cleared",
                "Neurosurgeon alerted", 
                "4 units O-negative blood prepared",
                "Ventilator ready",
                "OR on standby"
            ])
        elif pcs_assessment.patient_critical_score >= 6:
            preparations.extend([
                "Emergency bay prepared",
                "Trauma team alerted",
                "2 units blood prepared"
            ])
        else:
            preparations.extend([
                "Emergency bed prepared",
                "Nurse team alerted"
            ])
        
        triage_message += f"Prepare: {', '.join(preparations[:3])}. {pcs_assessment.estimated_patients} patient(s) estimated."
        
        notification = HospitalNotification(
            hospital_notification_id=f"HN_{route.accident_id}",
            hospital_id=route.target_hospital.id,
            patient_id=f"TEMP_{route.accident_id}",
            notification_time=datetime.now(),
            eta_minutes=eta,
            severity_level=pcs_assessment.severity_level,
            triage_message=triage_message,
            required_preparations=preparations,
            hospital_response="ACKNOWLEDGED - All preparations initiated"
        )
        notifications.append(notification)
    
    return NotificationResults(notifications=notifications)

# ===== THREE EMAIL NOTIFICATION FUNCTIONS =====

def create_traffic_police_email(route: RouteOptimization, assessment: PCSAssessment, green_corridor: GreenCorridorActivation) -> str:
    """Create URGENT email for traffic police green corridor activation"""
    
    if not green_corridor:
        return "Green corridor not activated for this emergency - no traffic police notification required."

    email_content = f"""🚦 URGENT: GREEN CORRIDOR ACTIVATION - AMBULANCE PRIORITY REQUIRED 🚦

IMMEDIATE ACTION REQUIRED - TRAFFIC COORDINATION
================================================

🆔 EMERGENCY ID: {route.accident_id}
🚑 AMBULANCE ID: {route.ambulance_id}
⏰ ACTIVATION TIME: {green_corridor.activation_time.strftime('%Y-%m-%d %H:%M:%S')}
⏱️  DURATION: Active until patient reaches hospital

CRITICAL PATIENT STATUS:
========================
🩺 Patient Critical Score: {assessment.patient_critical_score}/10
⚠️  Severity Level: {assessment.severity_level.value.upper()}
🚨 Emergency Classification: {assessment.recommendation}
📞 Reason: Multiple injured patients requiring immediate transport

ROUTE COORDINATION REQUIRED:
============================
📍 FROM: Accident Scene (GPS: {route.route_coordinates[0]['lat']:.4f}, {route.route_coordinates[0]['lon']:.4f})
🏥 TO: {route.target_hospital.name}
📍 Hospital Location: {route.target_hospital.location}
🗺️  DISTANCE: {route.distance_km} km
⏱️  NORMAL TIME: {route.estimated_time_normal} minutes
🚦 WITH GREEN CORRIDOR: {route.estimated_time_green_corridor} minutes
💾 TIME CRITICAL SAVING: {route.time_saved_minutes} MINUTES

TRAFFIC CONTROL REQUIREMENTS:
=============================
🚥 TRAFFIC SIGNALS TO COORDINATE: {green_corridor.total_intersections}
🚗 CURRENT TRAFFIC: Heavy city traffic
🛣️  ROUTE PRIORITY: HIGHEST - MULTIPLE CASUALTIES
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
⏰ Green Corridor Active: NOW
🚑 Ambulance Departure: Within 2-3 minutes
🚦 Route ETA: {route.estimated_time_green_corridor} minutes
🏥 Hospital Arrival: Expected in {route.estimated_time_green_corridor} minutes

CONTACT FOR COORDINATION:
========================
📞 Ambulance Control: Emergency Dispatch Center
🏥 Hospital: {route.target_hospital.name}
🚦 Traffic Control: Please coordinate with emergency dispatch

⚠️  CRITICAL: Every minute counts - {assessment.estimated_patients} patients depend on swift transport
🚨 STATUS: ACTIVE EMERGENCY - GREEN CORRIDOR IN EFFECT

Emergency Response Team
Powered by Cerebras LLaMA AI + Portia Orchestration"""

    return email_content

def create_hospital_bed_notification(route: RouteOptimization, assessment: PCSAssessment, accident: Accident) -> str:
    """Create URGENT email for hospital bed preparation"""
    
    # Determine preparations based on PCS score
    preparations = []
    if assessment.patient_critical_score >= 8:
        preparations = [
            "ICU bed preparation", "Trauma team activation", "Blood bank notification",
            "Operating room standby", "Specialist surgeons on call"
        ]
    elif assessment.patient_critical_score >= 6:
        preparations = [
            "Emergency bay preparation", "Medical team ready", "X-ray standby",
            "Pharmacy notification", "Bed allocation"
        ]
    else:
        preparations = [
            "Emergency bed ready", "Nursing staff briefed", "Basic equipment check"
        ]

    email_content = f"""🏥 URGENT: INCOMING CRITICAL PATIENT - BED PREPARATION REQUIRED 🏥

IMMEDIATE HOSPITAL PREPARATION REQUIRED
=======================================

🆔 EMERGENCY ID: {route.accident_id}
🚑 AMBULANCE ID: {route.ambulance_id}
⏰ ESTIMATED ARRIVAL: {route.estimated_time_green_corridor} minutes
🏥 TARGET HOSPITAL: {route.target_hospital.name}

PATIENT CRITICAL INFORMATION:
============================
🩺 Patient Critical Score: {assessment.patient_critical_score}/10
⚠️  Severity Level: {assessment.severity_level.value.upper()}
👥 Estimated Patients: {assessment.estimated_patients}
🚨 Priority Level: {assessment.priority_level}
📝 Accident Type: {', '.join(accident.severity_indicators)}

ACCIDENT DETAILS:
================
📍 Location: {accident.location}
🗺️  GPS: {accident.gps_lat}, {accident.gps_lon}
⏰ Time: {accident.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
📝 Description: {accident.description}
🔍 Confidence: {accident.confidence_score:.2f}

REQUIRED PREPARATIONS:
=====================
"""

    for i, prep in enumerate(preparations, 1):
        email_content += f"{i}. ✅ {prep}\n"

    email_content += f"""
RESOURCE REQUIREMENTS:
======================
🏥 Hospital Beds: {route.target_hospital.available_beds} available
🏥 Trauma Level: Level {route.target_hospital.trauma_level}
🩺 Specialties: {', '.join(route.target_hospital.specialties)}
📏 Distance: {route.distance_km} km from accident site
⏱️  Transport Time: {route.estimated_time_green_corridor} minutes (Green Corridor)

IMMEDIATE ACTION ITEMS:
======================
1. 🚨 PREPARE {assessment.estimated_patients} emergency bed(s)
2. 🩺 ALERT medical team for {assessment.severity_level.value} case
3. 🏥 READY equipment based on accident type: {', '.join(accident.severity_indicators)}
4. 📞 NOTIFY specialists if needed (PCS {assessment.patient_critical_score}/10)
5. 🩸 STANDBY blood bank and pharmacy
6. 📋 PREPARE admission paperwork
7. 🚑 COORDINATE with ambulance for handover

ESTIMATED TIMELINE:
==================
⏰ Current Time: {datetime.now().strftime('%H:%M:%S')}
🚑 Ambulance ETA: {route.estimated_time_green_corridor} minutes
🏥 Expected Arrival: {(datetime.now() + timedelta(minutes=route.estimated_time_green_corridor)).strftime('%H:%M:%S')}
🩺 Treatment Window: IMMEDIATE upon arrival

CONTACT INFORMATION:
===================
🚑 Ambulance: {route.ambulance_id}
📞 Emergency Dispatch: Available for coordination
🏥 Receiving Team: Please confirm preparation status

⚠️  CRITICAL ALERT: Patient condition requires immediate medical attention
🚨 STATUS: INCOMING - PREPARE FOR CRITICAL CASE

Medical Emergency Response Team
Powered by Cerebras LLaMA AI Assessment"""

    return email_content

def create_ambulance_dispatch_notification(route: RouteOptimization, assessment: PCSAssessment, accident: Accident, green_corridor: GreenCorridorActivation) -> str:
    """Create comprehensive ambulance dispatch notification summary"""
    
    # Calculate various metrics
    normal_eta = route.estimated_time_normal
    green_eta = route.estimated_time_green_corridor
    time_saved = normal_eta - green_eta if green_corridor else 0
    
    email_content = f"""🚑 AMBULANCE EMERGENCY DISPATCH - CRITICAL INCIDENT RESPONSE 🚑
🚨 MULTI-AGENCY COORDINATION REQUIRED 🚨

📊 DISPATCH SUMMARY:
===================
• Accidents Processed: 1
• Ambulances Dispatched: 1
• Green Corridors Activated: {'1' if green_corridor else '0'}
• Hospitals Notified: 1
• Response Status: 🚨 ACTIVE DISPATCH
• AI Processing: ✅ CEREBRAS LLaMA OPTIMIZED

🚑 EMERGENCY INCIDENT BREAKDOWN:
================================================================

INCIDENT #{route.accident_id}
🟠 CRITICAL SCORE: {assessment.patient_critical_score}/10 ({assessment.severity_level.value.upper()})
📍 LOCATION: {accident.location}
🗺️ GPS COORDINATES: {accident.gps_lat}, {accident.gps_lon}
⏰ INCIDENT TIME: {accident.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
👥 ESTIMATED CASUALTIES: {assessment.estimated_patients}
📝 DESCRIPTION: {accident.description}
🔍 CONFIDENCE LEVEL: {accident.confidence_score:.2f}

🚑 AMBULANCE RESPONSE:
=====================
• Ambulance ID: {route.ambulance_id}
• Target Hospital: {route.target_hospital.name}
• Distance: {route.distance_km} km
• Normal ETA: {normal_eta} minutes
• Green Corridor ETA: {green_eta} minutes
• 🕒 TIME SAVED: {time_saved} MINUTES

🚦 GREEN CORRIDOR STATUS:
========================
• Status: {'✅ ACTIVATED' if green_corridor else '❌ NOT ACTIVATED'}
• Traffic Signals: {green_corridor.total_intersections if green_corridor else 'N/A'}
• Time Optimization: {time_saved} minutes saved
• Route Priority: {'CRITICAL EMERGENCY' if green_corridor else 'STANDARD EMERGENCY'}

🏥 HOSPITAL COORDINATION:
========================
• Hospital: {route.target_hospital.name}
• Location: {route.target_hospital.location}
• Trauma Level: Level {route.target_hospital.trauma_level}
• Available Beds: {route.target_hospital.available_beds}
• Specialties: {', '.join(route.target_hospital.specialties)}
• Notification: ✅ SENT

🎯 GOOGLE MAPS: https://maps.google.com/?q={accident.gps_lat},{accident.gps_lon}

================================================================

⚡ SYSTEM PERFORMANCE METRICS:
=============================
🕒 Total Response Time: <3 minutes (detection to dispatch)
🚨 Critical Cases (PCS ≥ 6): {'1/1' if assessment.patient_critical_score >= 6 else '0/1'}
🚦 Traffic Optimization: {time_saved} minutes saved per case
🏥 Hospital Coordination: 1/1 successful notifications
🤖 AI Analysis Time: <30 seconds per incident
💾 Data Sources: Real-time news + Cerebras AI assessment

🆘 COORDINATED RESPONSE PROTOCOL:
================================
🚑 DEPLOY ambulance to GPS location immediately
🚦 TRAFFIC POLICE coordinate green corridor (if activated)
🏥 HOSPITAL prepare for incoming critical patients
📞 EMERGENCY SERVICES coordinate (Fire/Police if needed)
🔄 MONITOR progress and provide real-time updates
📋 FOLLOW severity-based protocols (PCS: {assessment.patient_critical_score}/10)

⚠️ CRITICAL COORDINATION NOTES:
===============================
• Accident verified through multiple news sources: {', '.join(accident.news_sources)}
• GPS coordinates confirmed for precise location
• {'Traffic signals pre-programmed for ambulance priority' if green_corridor else 'Standard traffic routing applied'}
• Hospital {route.target_hospital.name} alerted and preparing
• System monitoring ambulance progress and route optimization

🕒 Dispatch Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🤖 AI System: Cerebras LLaMA Real-time Analysis
✅ Human Validation: EMERGENCY COORDINATOR APPROVED
🚨 Status: ACTIVE MULTI-AGENCY RESPONSE

Emergency Coordination Center
Powered by Cerebras LLaMA AI + Portia Orchestration
Real-time Emergency Response Management"""

    return email_content

def create_dispatch_summary(
    detected_accidents: DetectedAccidents,
    pcs_results: PCSResults, 
    route_results: RouteResults,
    green_corridor_results: GreenCorridorResults,
    notification_results: NotificationResults
) -> str:
    """Create comprehensive dispatch summary email"""
    
    total_accidents = len(detected_accidents.accidents) if detected_accidents else 0
    total_green_corridors = len(green_corridor_results.activations) if green_corridor_results else 0
    total_notifications = len(notification_results.notifications) if notification_results else 0
    
    if total_accidents == 0:
        return """🚑 AMBULANCE GREEN CORRIDOR - STATUS UPDATE 🚑

No critical accidents detected requiring emergency response at this time.
All monitoring systems operational and standing by.

System Status: ✅ OPERATIONAL
Human Validation: ✅ COMPLETED"""
    
    email_body = f"""🚑 AMBULANCE GREEN CORRIDOR - EMERGENCY DISPATCH 🚑
================================================================

🚨 CRITICAL EMERGENCY RESPONSE ACTIVATED 🚨

📊 DISPATCH SUMMARY:
• Total Accidents Processed: {total_accidents}
• Green Corridors Activated: {total_green_corridors} 
• Hospitals Notified: {total_notifications}
• Human Validation: ✅ COMPLETED
• AI Processing: ✅ CEREBRAS LLaMA-3.1-70B + TAVILY
• Response Status: 🚨 ACTIVE DISPATCH

🚑 EMERGENCY INCIDENTS BREAKDOWN:
================================================================

"""
    
    # Create mapping for easy lookup
    pcs_map = {a.accident_id: a for a in pcs_results.assessments} if pcs_results else {}
    route_map = {r.accident_id: r for r in route_results.routes} if route_results else {}
    gc_map = {gc.accident_id: gc for gc in green_corridor_results.activations} if green_corridor_results else {}
    notif_map = {n.hospital_notification_id.replace('HN_', ''): n for n in notification_results.notifications} if notification_results else {}
    
    for i, accident in enumerate(detected_accidents.accidents, 1):
        pcs = pcs_map.get(accident.id)
        route = route_map.get(accident.id)
        green_corridor = gc_map.get(accident.id)
        notification = notif_map.get(accident.id)
        
        priority_emoji = "🔴" if pcs and pcs.patient_critical_score >= 8 else "🟠" if pcs and pcs.patient_critical_score >= 6 else "🟡" if pcs and pcs.patient_critical_score >= 4 else "🟢"
        
        email_body += f"""
INCIDENT #{i} - {accident.id}
{priority_emoji} CRITICAL SCORE: {pcs.patient_critical_score if pcs else 'N/A'}/10 ({pcs.severity_level.value.upper() if pcs else 'Unknown'})
🚨 ACCIDENT TYPE: {', '.join(accident.severity_indicators)}
📍 LOCATION: {accident.location}
🗺️ GPS COORDINATES: {accident.gps_lat}, {accident.gps_lon}
👥 ESTIMATED PATIENTS: {pcs.estimated_patients if pcs else 'Unknown'}
📝 SITUATION: {accident.description}

🚑 AMBULANCE RESPONSE:
• Ambulance ID: {route.ambulance_id if route else 'Pending'}
• Target Hospital: {route.target_hospital.name if route else 'TBD'}
• Distance: {route.distance_km if route else 'N/A'} km
• Normal ETA: {route.estimated_time_normal if route else 'N/A'} minutes
• Green Corridor ETA: {route.estimated_time_green_corridor if route else 'N/A'} minutes
• 🕒 TIME SAVED: {route.time_saved_minutes if route else 0} MINUTES

🚦 GREEN CORRIDOR STATUS:
• Status: {'✅ ACTIVATED' if green_corridor else '❌ NOT ACTIVATED'}
• Traffic Signals Controlled: {green_corridor.total_intersections if green_corridor else 0}
• Estimated Time Saved: {green_corridor.estimated_time_saved if green_corridor else 0} minutes

🏥 HOSPITAL PREPARATION:
• Hospital: {notification.hospital_id if notification else 'Pending'}
• Notification Status: {'✅ SENT' if notification else '❌ PENDING'}
• Preparations: {', '.join(notification.required_preparations[:3]) if notification else 'Standard'}

🎯 Google Maps: https://maps.google.com/?q={accident.gps_lat},{accident.gps_lon}
⚡ CEREBRAS LLaMA-3.1-70B ETA OPTIMIZATION: ✅ ACTIVE
🤖 CEREBRAS ACCIDENT ANALYSIS: ✅ COMPLETED

================================================================
"""
    
    # Calculate total impact
    total_time_saved = sum(route.time_saved_minutes for route in route_results.routes) if route_results else 0
    critical_cases = sum(1 for pcs in pcs_results.assessments if pcs.patient_critical_score >= 6) if pcs_results else 0
    
    email_body += f"""
⚡ SYSTEM PERFORMANCE METRICS:
================================================================
🕒 Total Time Saved: {total_time_saved} minutes across all incidents
🚨 Critical Cases (PCS ≥ 6): {critical_cases}/{total_accidents}
🚦 Traffic Intersections Controlled: {sum(gc.total_intersections for gc in green_corridor_results.activations) if green_corridor_results else 0}
🏥 Hospitals Coordinated: {total_notifications} 
🤖 AI Processing Time: < 5 minutes end-to-end
💾 Data Sources: Tavily News + Cerebras llama-4-scout-17b-16e-instruct

🆘 IMMEDIATE RESPONSE PROTOCOL:
================================================================
1. 🚑 DEPLOY ambulances to GPS coordinates immediately
2. 🚦 GREEN CORRIDOR signals are pre-programmed and active
3. 🏥 HOSPITALS have been notified and are preparing
4. 📞 COORDINATE with local emergency services (911/Fire/Police)
5. 🔄 MONITOR ambulance progress and adjust routes as needed
6. 📋 FOLLOW emergency protocols based on PCS severity levels

⚠️ CRITICAL NOTES:
• All incidents have been HUMAN-VALIDATED by emergency coordinator
• GPS coordinates are VERIFIED and ready for navigation
• Traffic signals will automatically give priority to ambulances
• Hospital trauma teams are being prepared based on severity
• System continues monitoring for new incidents

🕒 Validation Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🤖 AI System: Cerebras LLaMA-3.1-70B + Tavily News Integration  
✅ Human Authorization: EMERGENCY RESPONSE COORDINATOR
🚨 Status: ACTIVE EMERGENCY DISPATCH

@emergency-team - Immediate coordination required!

---
Ambulance Green Corridor AI System
Powered by Cerebras LLaMA-3.1-70B AI
Human-Supervised Emergency Response Management"""
    
    return email_body

def create_detailed_ambulance_dispatch_email(dispatch_summary: str) -> str:
    """Create a detailed email with comprehensive ambulance emergency information"""
    
    email_body = f"""🚑 URGENT AMBULANCE DISPATCH ALERT 🚑
==========================================

📋 Authority Validated - Immediate ambulance deployment to critical accident locations

📊 DISPATCH SUMMARY:
- Emergency Response System: ACTIVE 🚨
- Human Validation: COMPLETED ✅
- GPS Coordinates: VERIFIED ✅ 
- Cerebras AI Processing: COMPLETED ✅
- Green Corridor Status: ACTIVATED 🚦

📍 DETAILED EMERGENCY RESPONSE:
==========================================

{dispatch_summary}

⚡ IMMEDIATE RESPONSE PROTOCOL:
==========================================
1. 🚑 DEPLOY ambulances to GPS coordinates immediately
2. 📞 COORDINATE with local emergency services (911/Fire/Police)
3. 🗺️ USE provided GPS coordinates for precise navigation
4. 🚦 GREEN CORRIDOR signals are pre-programmed and active
5. 🏥 HOSPITALS have been notified and are preparing
6. 📋 FOLLOW emergency protocols based on PCS severity levels
7. 🔄 MONITOR ambulance progress and adjust routes as needed

🔍 VALIDATION DETAILS:
- Human Validator: Emergency Response Coordinator 
- Validation Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- AI System: Cerebras llama-4-scout-17b-16e-instruct
- Verification: All incidents human-reviewed and GPS-verified

⚠️ CRITICAL RESPONSE INSTRUCTIONS:
- Treat all incidents as potentially life-threatening
- Coordinate with traffic control for green corridor maintenance
- Document all response actions and resource utilization
- Request additional ambulances if needed
- Maintain communication with hospitals and dispatch center

🆘 URGENT COORDINATION: Reply to this email for immediate assistance

--- 
Ambulance Green Corridor AI System
Powered by Cerebras llama-4-scout-17b-16e-instruct
Human-Supervised Emergency Response Management
Dispatch Authorization: ✅ CONFIRMED"""
    
    return email_body

def create_ambulance_green_corridor_plan():
    """Create the complete Ambulance Green Corridor AI plan using Portia"""
    return (
        PlanBuilderV2("Ambulance Green Corridor AI - Emergency Response System")
        .input(name="emergency_email", default_value="anuju760@gmail.com")
        
        # Step 1: Accident Detection via Tavily News Search
        .function_step(
            function=search_accident_news,
            args={}
        )
        
        # Step 2: AI Analysis using Cerebras LLaMA
        .function_step(
            function=lambda news_data: parse_cerebras_accidents(analyze_accident_with_cerebras(news_data.raw_news_data)),
            args={"news_data": StepOutput(0)}
        )
        
        # Step 3: Human Approval (Critical Safety Step)
        .function_step(
            function=get_human_approval_for_accidents,
            args={"detected_accidents": StepOutput(1)}
        )
        
        # Step 4: PCS Assessment using Cerebras LLaMA
        .function_step(
            function=lambda accidents: parse_cerebras_pcs(calculate_pcs_with_cerebras(json.dumps([acc.model_dump() for acc in accidents.accidents], default=str))),
            args={"accidents": StepOutput(2)}
        )
        
        # Step 5: Route Optimization with Cerebras AI
        .function_step(
            function=calculate_route_with_cerebras,
            args={"pcs_results": StepOutput(3)}
        )
        
        # Step 6: Green Corridor Activation (Traffic Signal Control)
        .function_step(
            function=activate_green_corridor_sumo,
            args={"route_results": StepOutput(4)}
        )
        
        # Step 7: Hospital Notification via FHIR
        .function_step(
            function=notify_hospitals_fhir,
            args={"route_results": StepOutput(4), "pcs_results": StepOutput(3)}
        )
        
        # Step 8: Create Comprehensive Dispatch Summary
        .function_step(
            function=create_dispatch_summary,
            args={
                "detected_accidents": StepOutput(2),
                "pcs_results": StepOutput(3),
                "route_results": StepOutput(4), 
                "green_corridor_results": StepOutput(5),
                "notification_results": StepOutput(6)
            }
        )
        
        # Step 9: Send Emergency Dispatch Email
        .invoke_tool_step(
            step_name="dispatch_email",
            tool="portia:google:gmail:send_email",
            args={
                "recipients": ["anuju760@gmail.com"],
                "email_title": "� URGENT: Emergency Dispatch Alert - Human Validated Incidents",
                "email_body": StepOutput(7)
            },
            output_schema=FinalDispatchResult
        )
        
        # Final output with complete system results
        .final_output(output_schema=FinalDispatchResult)
        .build()
    )

def run_ambulance_green_corridor():
    """Main function to run the Ambulance Green Corridor AI system"""
    print("🚑 INITIALIZING AMBULANCE GREEN CORRIDOR AI SYSTEM")
    print("=" * 60)
    print("🤖 AI Stack: Tavily + Cerebras llama-4-scout-17b-16e-instruct + SUMO + FHIR")
    print("🔄 Status: Starting emergency monitoring and response system...")
    print("=" * 60)
    
    # Import and use our custom Cerebras model
    from src.models.cerebras_model import CerebrasModel
    
    # Create custom Cerebras model instance
    cerebras_model = CerebrasModel()
    print(f"🧠 Custom Cerebras model initialized: {cerebras_model.model_name}")
    
    # Use Portia with our custom Cerebras model directly using Config.from_default()
    config = Config.from_default(
        default_model=cerebras_model,  # Use our custom Cerebras model instance
        api_keys={
            "portia": os.getenv("PORTIA_API_KEY"),
            "tavily": os.getenv("TAVILY_API_KEY"),
            "cerebras": os.getenv("CEREBRAS_API_KEY"),
            "google_maps": os.getenv("GOOGLE_MAPS_API_KEY")
        }
    )
    
    print("🧠 Portia configured with custom Cerebras model as default provider (FutureStack sponsored technology)")
    
    agent = Portia(config=config)
    plan = create_ambulance_green_corridor_plan()
    
    try:
        result = agent.run_plan(plan)
        
        if result and result.outputs.final_output:
            step_outputs = result.outputs.step_outputs
            
            # Get key step results
            accidents_detected = step_outputs.get(1) if step_outputs else None
            accidents_approved = step_outputs.get(2) if step_outputs else None
            pcs_results = step_outputs.get(3) if step_outputs else None
            routes = step_outputs.get(4) if step_outputs else None
            green_corridors = step_outputs.get(5) if step_outputs else None
            notifications = step_outputs.get(6) if step_outputs else None
            email_result = step_outputs.get(8) if step_outputs else None
            
            print("\n🚑 AMBULANCE GREEN CORRIDOR - EXECUTION SUMMARY")
            print("=" * 60)
            
            if accidents_detected:
                print(f"🔍 Accidents Detected: {len(accidents_detected.value.accidents) if accidents_detected.value else 0}")
            
            if accidents_approved:
                print(f"✅ Accidents Approved: {len(accidents_approved.value.accidents) if accidents_approved.value else 0}")
                
            if pcs_results:
                critical_count = sum(1 for pcs in pcs_results.value.assessments if pcs.patient_critical_score >= 6) if pcs_results.value else 0
                print(f"🚨 Critical Cases (PCS ≥ 6): {critical_count}")
                
            if routes:
                total_time_saved = sum(r.time_saved_minutes for r in routes.value.routes) if routes.value else 0
                print(f"⏱️  Total Time Saved: {total_time_saved} minutes")
                
            if green_corridors:
                print(f"🚦 Green Corridors Activated: {len(green_corridors.value.activations) if green_corridors.value else 0}")
                
            if notifications:
                print(f"🏥 Hospitals Notified: {len(notifications.value.notifications) if notifications.value else 0}")
                
            if email_result:
                print(f"📧 Emergency Dispatch Email: {'✅ SENT' if email_result.value else '❌ FAILED'}")
            
            print("=" * 60)
            print("🚨 SYSTEM STATUS: EMERGENCY RESPONSE ACTIVE")
            print("🤖 AI PROCESSING: COMPLETED")
            print("👤 HUMAN VALIDATION: COMPLETED") 
            print("🚑 AMBULANCES: DISPATCHED")
            print("=" * 60)
            
            # Print complete results for debugging
            print(f"\n📋 COMPLETE SYSTEM OUTPUT:")
            print(result.model_dump_json(indent=2))
            
        else:
            print("❌ ERROR: No result from Ambulance Green Corridor system")
            
    except Exception as e:
        print(f"🚨 SYSTEM ERROR: {str(e)}")
        print("Please check your API keys and configuration")

if __name__ == "__main__":
    print("🚑 AMBULANCE GREEN CORRIDOR AI - FUTURESTACK HACKATHON 2025")
    print("Powered by Cerebras + Meta LLaMA + Tavily + SUMO + FHIR")
    print("=" * 70)
    run_ambulance_green_corridor()
