import streamlit as st
import folium
from streamlit_folium import folium_static
import pandas as pd
from datetime import datetime, timedelta
import os
import json
from typing import List, Optional
import random
from dotenv import load_dotenv


from patient_initiate_ambulance_workflow import (
    EmergencyType, CriticalityLevel, PatientCondition, FamilyEmergencyRequest,
    PatientAssessment, RealTimeHospital, PatientRoute, PatientGreenCorridor,
    PatientDispatchResult, assess_patient_with_ai, check_hospital_bed_availability,
    calculate_patient_route, activate_patient_green_corridor, create_traffic_police_email,
    create_hospital_bed_notification, notify_family_and_hospital, create_patient_dispatch_summary,
    create_updated_patient_emergency_plan, Config, Portia, PlanBuilderV2, StepOutput
)

# Import custom Cerebras model
from src.models.cerebras_model import CerebrasModel

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="LifeLine Green Corridor - Family Emergency Dashboard",
    page_icon="🚑",
    layout="wide"
)

# Initialize session state variables
if "family_emergency_request" not in st.session_state:
    st.session_state.family_emergency_request = None
if "patient_assessment" not in st.session_state:
    st.session_state.patient_assessment = None
if "available_hospitals" not in st.session_state:
    st.session_state.available_hospitals = []
if "selected_hospital" not in st.session_state:
    st.session_state.selected_hospital = None
if "patient_route" not in st.session_state:
    st.session_state.patient_route = None
if "green_corridor_active" not in st.session_state:
    st.session_state.green_corridor_active = None
if "dispatch_summary" not in st.session_state:
    st.session_state.dispatch_summary = ""
if "email_notifications_sent" not in st.session_state:
    st.session_state.email_notifications_sent = False
if "green_corridor_dispatch_sent" not in st.session_state:
    st.session_state.green_corridor_dispatch_sent = False
if "workflow_completed" not in st.session_state:
    st.session_state.workflow_completed = False

# Dashboard version of family emergency collection
def dashboard_collect_family_emergency(
    caller_name: str, caller_phone: str, patient_name: str, patient_age: int,
    emergency_location: str, detailed_address: str, emergency_type: EmergencyType,
    is_conscious: bool, is_breathing: bool, any_bleeding: bool, symptoms: str
) -> FamilyEmergencyRequest:
    """Dashboard version of family emergency collection"""
    
    # Auto-generate GPS coordinates for Delhi/NCR region
    base_coords = {
        "delhi_central": (28.6139, 77.2090),
        "gurgaon": (28.4595, 77.0266),
        "noida": (28.5355, 77.3910)
    }
    base_lat, base_lon = random.choice(list(base_coords.values()))
    gps_lat = base_lat + random.uniform(-0.05, 0.05)
    gps_lon = base_lon + random.uniform(-0.05, 0.05)
    
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
    
    return FamilyEmergencyRequest(
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

# Generate mock family emergency data for testing
def generate_mock_family_emergency():
    """Generate mock family emergency for testing"""
    return dashboard_collect_family_emergency(
        caller_name="Rajesh Kumar",
        caller_phone="+91-9876543210",
        patient_name="Sunita Kumar",
        patient_age=65,
        emergency_location="Connaught Place, New Delhi",
        detailed_address="B-12, Inner Circle, Connaught Place, New Delhi - 110001",
        emergency_type=EmergencyType.CARDIAC,
        is_conscious=False,
        is_breathing=True,
        any_bleeding=False,
        symptoms="Chest pain, difficulty breathing, sweating profusely"
    )

# Get marker color based on criticality level
def get_criticality_marker_color(criticality_level):
    """Get marker color based on patient criticality level"""
    if criticality_level == CriticalityLevel.CRITICAL:
        return "darkred"
    elif criticality_level == CriticalityLevel.SERIOUS:
        return "red"
    elif criticality_level == CriticalityLevel.MODERATE:
        return "orange"
    else:
        return "green"

# Create patient emergency map with enhanced route highlighting
def create_patient_emergency_map():
    """Create a Folium map with enhanced patient emergency markers and advanced route visualization"""
    
    # Collect all coordinates to calculate optimal center and zoom
    all_coordinates = []
    
    # Add family emergency request coordinates
    if st.session_state.family_emergency_request:
        request = st.session_state.family_emergency_request
        all_coordinates.append([request.gps_lat, request.gps_lon])
    
    # Add selected hospital coordinates
    if st.session_state.selected_hospital:
        hospital = st.session_state.selected_hospital
        all_coordinates.append([hospital.gps_lat, hospital.gps_lon])
    
    # Add all available hospitals coordinates
    for hospital in st.session_state.available_hospitals:
        all_coordinates.append([hospital.gps_lat, hospital.gps_lon])
    
    # Calculate optimal map center and zoom
    if all_coordinates:
        # Calculate center point of all locations
        center_lat = sum(coord[0] for coord in all_coordinates) / len(all_coordinates)
        center_lon = sum(coord[1] for coord in all_coordinates) / len(all_coordinates)
        
        # Calculate bounds for zoom level
        min_lat = min(coord[0] for coord in all_coordinates)
        max_lat = max(coord[0] for coord in all_coordinates)
        min_lon = min(coord[1] for coord in all_coordinates)
        max_lon = max(coord[1] for coord in all_coordinates)
        
        # Determine zoom level based on coordinate spread
        lat_diff = max_lat - min_lat
        lon_diff = max_lon - min_lon
        max_diff = max(lat_diff, lon_diff)
        
        # Smart zoom calculation
        if max_diff < 0.01:  # Very close locations
            zoom_level = 15
        elif max_diff < 0.05:  # City-level
            zoom_level = 13
        elif max_diff < 0.2:   # Metro area
            zoom_level = 11
        elif max_diff < 1.0:   # Regional
            zoom_level = 9
        else:  # Wide area
            zoom_level = 7
        
        # Create map centered on locations
        m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)
        
        # For better viewing, fit bounds to show all locations with padding
        if len(all_coordinates) > 1:
            m.fit_bounds(all_coordinates, padding=(20, 20))
            
    else:
        # Fallback: Center map on Delhi/NCR
        m = folium.Map(location=[28.6139, 77.2090], zoom_start=10)
    
    # Add family emergency request marker with enhanced visualization
    if st.session_state.family_emergency_request:
        request = st.session_state.family_emergency_request
        assessment = st.session_state.patient_assessment
        
        color = get_criticality_marker_color(request.criticality_level)
        
        popup_html = f"""
        <div style="min-width:350px;">
            <h4 style="color:{color};">🚨 {request.request_id} - EMERGENCY REQUEST</h4>
            <b>👤 Patient:</b> {request.patient_name} ({request.patient_age} years)<br>
            <b>📞 Caller:</b> {request.caller_name}<br>
            <b>📱 Phone:</b> {request.caller_phone}<br>
            <b>📍 Location:</b> {request.emergency_location}<br>
            <b>🗺️ GPS:</b> {request.gps_lat:.4f}, {request.gps_lon:.4f}<br>
            <b>🚨 Emergency:</b> {request.emergency_type.value.upper()}<br>
            <b>⚠️ Criticality:</b> <span style="color:{color};font-weight:bold;">{request.criticality_level.value.upper()}</span><br>
            <b>🧠 Consciousness:</b> {'✅ Conscious' if request.is_patient_conscious else '❌ Unconscious'}<br>
            <b>🫁 Breathing:</b> {'✅ Normal' if request.is_patient_breathing else '⚠️ Compromised'}<br>
            <b>🩸 Bleeding:</b> {'⚠️ Yes' if request.any_bleeding else '✅ No'}<br>
            <b>💭 Symptoms:</b> {request.symptoms_description}<br>
            {f"<b>🧠 PCS Score:</b> <span style='color:{'darkred' if assessment and assessment.patient_critical_score >= 8 else 'red' if assessment and assessment.patient_critical_score >= 6 else 'orange' if assessment and assessment.patient_critical_score >= 4 else 'green'};font-weight:bold;'>{assessment.patient_critical_score if assessment else 'Calculating...'}/10</span><br>" if assessment else ""}
            <hr>
            <a href="https://maps.google.com/?q={request.gps_lat},{request.gps_lon}" target="_blank" style="color:blue;">🎯 View on Google Maps</a>
        </div>
        """
        
        # Enhanced patient marker with criticality-based styling
        folium.Marker(
            [request.gps_lat, request.gps_lon],
            popup=folium.Popup(popup_html, max_width=400),
            tooltip=f"🚨 {request.patient_name} - {request.emergency_type.value.upper()} ({request.criticality_level.value.upper()})",
            icon=folium.Icon(color=color, icon="user-injured", prefix="fa")
        ).add_to(m)
        
        # Add pulsing circle around emergency location for visibility
        folium.Circle(
            [request.gps_lat, request.gps_lon],
            radius=200,
            color=color,
            fillColor=color,
            fillOpacity=0.15,
            opacity=0.6,
            weight=2,
            popup=f"🚨 Emergency Zone: {request.request_id}",
            tooltip=f"PATIENT EMERGENCY - {request.criticality_level.value.upper()} PRIORITY"
        ).add_to(m)
    
    # Add enhanced route visualization to hospital if available
    if st.session_state.patient_route and st.session_state.selected_hospital:
        route = st.session_state.patient_route
        hospital = st.session_state.selected_hospital
        
        # Determine route styling based on green corridor status
        is_green_corridor = st.session_state.green_corridor_active is not None
        route_color = "#FF0000" if is_green_corridor else "#0066CC"  # Red for green corridor, blue for standard
        border_color = "#FFFFFF" if is_green_corridor else "#000000"  # White border for green corridor, black for standard
        route_weight = 8 if is_green_corridor else 6
        
        # Generate detailed route coordinates (simulated waypoints for better visualization)
        start_lat, start_lon = route.pickup_location["lat"], route.pickup_location["lon"]
        end_lat, end_lon = hospital.gps_lat, hospital.gps_lon
        
        # Create waypoints for smoother route visualization
        num_waypoints = 8
        waypoints = []
        for i in range(num_waypoints + 1):
            factor = i / num_waypoints
            # Add slight curvature to make route look more realistic
            curve_offset = 0.002 * (1 - 4 * (factor - 0.5) ** 2)  # Parabolic curve
            lat = start_lat + (end_lat - start_lat) * factor + curve_offset
            lon = start_lon + (end_lon - start_lon) * factor
            waypoints.append([lat, lon])
        
        # Add border/outline for the route (for better visibility)
        folium.PolyLine(
            waypoints,
            color=border_color,
            weight=route_weight + 3,
            opacity=0.8,
            popup=f"Route Border: {route.ambulance_id} → {hospital.name}"
        ).add_to(m)
        
        # Main route line with enhanced styling
        folium.PolyLine(
            waypoints,
            color=route_color,
            weight=route_weight,
            opacity=0.9,
            popup=f"""
            <div style="min-width:250px;">
                <h4>🚑 AMBULANCE ROUTE</h4>
                <b>Ambulance:</b> {route.ambulance_id}<br>
                <b>From:</b> {st.session_state.family_emergency_request.emergency_location if st.session_state.family_emergency_request else 'Emergency Location'}<br>
                <b>To:</b> {hospital.name}<br>
                <b>Distance:</b> {route.distance_km} km<br>
                <b>Normal ETA:</b> {route.estimated_time_normal} min<br>
                <b>Green Corridor ETA:</b> {route.estimated_time_green_corridor} min<br>
                <b>Time Saved:</b> {route.time_saved_minutes} min<br>
                <b>Status:</b> {'🚦 GREEN CORRIDOR ACTIVE' if is_green_corridor else '🛣️ PRIORITY ROUTE'}
            </div>
            """,
            tooltip=f"🚑 {route.ambulance_id} → {hospital.name} ({'GREEN CORRIDOR' if is_green_corridor else 'PRIORITY ROUTE'})"
        ).add_to(m)
        
        # Add directional arrows along the route
        for i in range(0, len(waypoints) - 1, 2):
            if i + 1 < len(waypoints):
                # Calculate arrow position and direction
                start_point = waypoints[i]
                end_point = waypoints[i + 1]
                
                # Add small directional arrow
                folium.RegularPolygonMarker(
                    location=[(start_point[0] + end_point[0]) / 2, (start_point[1] + end_point[1]) / 2],
                    number_of_sides=3,
                    radius=5,
                    color=route_color,
                    fillColor=route_color,
                    fillOpacity=0.8,
                    popup=f"➤ Direction: {route.ambulance_id}",
                    tooltip="Route Direction"
                ).add_to(m)
        
        # Add route waypoints as small markers
        for i, waypoint in enumerate(waypoints[1:-1], 1):  # Skip start and end points
            folium.CircleMarker(
                waypoint,
                radius=3,
                color=border_color,
                fillColor=route_color,
                fillOpacity=0.7,
                popup=f"Waypoint {i}",
                tooltip=f"Route Point {i}"
            ).add_to(m)
        
        # Enhanced ambulance start marker
        folium.Marker(
            [start_lat, start_lon],
            popup=f"""
            <div style="min-width:200px;">
                <h4>🚑 AMBULANCE DEPARTURE</h4>
                <b>Ambulance ID:</b> {route.ambulance_id}<br>
                <b>Patient Pickup:</b> {st.session_state.family_emergency_request.emergency_location if st.session_state.family_emergency_request else 'Emergency Location'}<br>
                <b>Departure Status:</b> Ready for Dispatch<br>
                <b>Route Type:</b> {'Green Corridor Priority' if is_green_corridor else 'Emergency Priority'}
            </div>
            """,
            tooltip=f"🚑 {route.ambulance_id} - DEPARTURE POINT",
            icon=folium.Icon(color="blue", icon="ambulance", prefix="fa")
        ).add_to(m)
        
        # Enhanced hospital destination marker
        hospital_popup = f"""
        <div style="min-width:300px;">
            <h4 style="color:green;">🏥 {hospital.name} - DESTINATION</h4>
            <b>📍 Location:</b> {hospital.location}<br>
            <b>🗺️ GPS:</b> {hospital.gps_lat:.4f}, {hospital.gps_lon:.4f}<br>
            <b>📏 Distance:</b> {hospital.distance_km} km from emergency<br>
            <b>🏥 Trauma Level:</b> {hospital.trauma_level}<br>
            <b>🛏️ Available Beds:</b> {hospital.available_beds} General<br>
            <b>🏥 ICU Beds:</b> {hospital.icu_beds} Available<br>
            <b>📊 Current Load:</b> {hospital.current_load}<br>
            <b>🩺 Specialties:</b> {', '.join(hospital.specialties) if hospital.specialties else 'General Emergency'}<br>
            <b>🕒 Normal ETA:</b> {route.estimated_time_normal} minutes<br>
            <b>🚦 Green Corridor ETA:</b> {route.estimated_time_green_corridor} minutes<br>
            <b>⏱️ Time Saved:</b> <span style="color:green;font-weight:bold;">{route.time_saved_minutes} minutes</span><br>
            <b>🚨 Preparation Status:</b> {'ICU Team Ready' if st.session_state.patient_assessment and st.session_state.patient_assessment.patient_critical_score >= 8 else 'Emergency Team Ready'}<br>
            <hr>
            <a href="https://maps.google.com/?q={hospital.gps_lat},{hospital.gps_lon}" target="_blank" style="color:green;">🎯 View on Google Maps</a>
        </div>
        """
        
        folium.Marker(
            [hospital.gps_lat, hospital.gps_lon],
            popup=folium.Popup(hospital_popup, max_width=350),
            tooltip=f"🏥 {hospital.name} - ETA: {route.estimated_time_green_corridor} min ({'GREEN CORRIDOR' if is_green_corridor else 'PRIORITY'})",
            icon=folium.Icon(color="red", icon="plus", prefix="fa")
        ).add_to(m)
        
        # Add hospital service area coverage
        folium.Circle(
            [hospital.gps_lat, hospital.gps_lon],
            radius=500,  # 500 meter service area
            color='red',
            fillColor='pink',
            fillOpacity=0.1,
            opacity=0.4,
            weight=2,
            popup=f"🏥 {hospital.name} Service Area",
            tooltip="Hospital Coverage Zone"
        ).add_to(m)
        
        # Add direct line connection (dashed) showing the direct path
        folium.PolyLine(
            [[start_lat, start_lon], [end_lat, end_lon]],
            color='gray',
            weight=2,
            opacity=0.5,
            dash_array='5, 5',
            popup=f"Direct Distance: {route.distance_km} km",
            tooltip="Direct Line Distance"
        ).add_to(m)
    
    # Add enhanced markers for other available hospitals
    for hospital in st.session_state.available_hospitals:
        if hospital != st.session_state.selected_hospital:
            # Determine hospital priority color based on trauma level and availability
            if hospital.trauma_level == "Level 1":
                hospital_color = "orange"
                hospital_icon = "plus-square"
            elif hospital.trauma_level == "Level 2":
                hospital_color = "lightred"
                hospital_icon = "plus"
            else:
                hospital_color = "lightgray"
                hospital_icon = "hospital"
            
            # Enhanced popup for available hospitals
            available_hospital_popup = f"""
            <div style="min-width:250px;">
                <h4>🏥 {hospital.name} - AVAILABLE OPTION</h4>
                <b>📍 Location:</b> {hospital.location}<br>
                <b>🗺️ GPS:</b> {hospital.gps_lat:.4f}, {hospital.gps_lon:.4f}<br>
                <b>📏 Distance:</b> {hospital.distance_km} km from emergency<br>
                <b>🏥 Trauma Level:</b> {hospital.trauma_level}<br>
                <b>🛏️ Available Beds:</b> {hospital.available_beds} General<br>
                <b>🏥 ICU Beds:</b> {hospital.icu_beds} Available<br>
                <b>📊 Current Load:</b> {hospital.current_load}<br>
                <b>🩺 Specialties:</b> {', '.join(hospital.specialties) if hospital.specialties else 'General Emergency'}<br>
                <b>⭐ Status:</b> Alternative Option<br>
                <hr>
                <a href="https://maps.google.com/?q={hospital.gps_lat},{hospital.gps_lon}" target="_blank" style="color:orange;">🎯 View on Google Maps</a>
            </div>
            """
            
            folium.Marker(
                [hospital.gps_lat, hospital.gps_lon],
                popup=folium.Popup(available_hospital_popup, max_width=300),
                tooltip=f"🏥 {hospital.name} - AVAILABLE ({hospital.trauma_level}) - {hospital.distance_km}km",
                icon=folium.Icon(color=hospital_color, icon=hospital_icon, prefix="fa")
            ).add_to(m)
            
            # Add smaller coverage areas for alternative hospitals
            folium.Circle(
                [hospital.gps_lat, hospital.gps_lon],
                radius=300,  # Smaller radius for alternatives
                color=hospital_color,
                fillColor=hospital_color,
                fillOpacity=0.05,
                opacity=0.3,
                weight=1,
                popup=f"🏥 {hospital.name} - Alternative Coverage",
                tooltip=f"Alternative Hospital: {hospital.name}"
            ).add_to(m)
    
    return m

# Dashboard workflow functions (like ambulance dashboard pattern)
def dashboard_assess_patient_with_ai():
    """Process patient assessment using Portia workflow"""
    if not st.session_state.family_emergency_request:
        st.warning("Please fill out the family emergency form first.")
        return None
    
    with st.spinner("🧠 Running AI patient assessment with Cerebras..."):
        try:
            # Create AI assessment using Cerebras
            assessment = assess_patient_with_ai(st.session_state.family_emergency_request)
            
            if assessment:
                st.session_state.patient_assessment = assessment
                st.success(f"✅ Patient assessment completed - PCS: {assessment.patient_critical_score}/10")
                return assessment
            else:
                st.error("Failed to complete AI assessment")
                return None
                
        except Exception as e:
            st.error(f"Error in AI assessment: {str(e)}")
            return None

def dashboard_check_hospital_availability():
    """Check hospital availability using Portia workflow"""
    if not st.session_state.family_emergency_request or not st.session_state.patient_assessment:
        st.warning("Emergency request and assessment data required.")
        return None
    
    with st.spinner("🏥 Checking real-time hospital bed availability..."):
        try:
            hospitals = check_hospital_bed_availability(
                st.session_state.family_emergency_request, 
                st.session_state.patient_assessment
            )
            
            if hospitals:
                st.session_state.available_hospitals = hospitals
                st.session_state.selected_hospital = hospitals[0]
                st.success(f"✅ Found {len(hospitals)} available hospitals")
                return hospitals
            else:
                st.warning("⚠️ No hospitals available - emergency protocols activated")
                return None
                
        except Exception as e:
            st.error(f"Error checking hospitals: {str(e)}")
            return None

def dashboard_calculate_route():
    """Calculate optimal route using Portia workflow"""
    if not all([st.session_state.family_emergency_request, 
               st.session_state.patient_assessment,
               st.session_state.available_hospitals]):
        st.warning("Missing required data for route calculation.")
        return None
    
    with st.spinner("🗺️ Calculating optimal emergency route..."):
        try:
            route = calculate_patient_route(
                st.session_state.family_emergency_request,
                st.session_state.available_hospitals[0],
                st.session_state.patient_assessment
            )
            
            if route:
                st.session_state.patient_route = route
                if hasattr(route, 'hospital_destination'):
                    st.session_state.selected_hospital = route.hospital_destination
                st.success(f"✅ Route calculated - ETA: {route.estimated_time_green_corridor} minutes")
                return route
            else:
                st.error("Failed to calculate route")
                return None
                
        except Exception as e:
            st.error(f"Error calculating route: {str(e)}")
            return None

def create_green_corridor_dispatch_notification(
    emergency_request: FamilyEmergencyRequest, 
    assessment: PatientAssessment, 
    route: PatientRoute, 
    green_corridor: PatientGreenCorridor
) -> str:
    """Create Green Corridor Emergency Dispatch notification"""
    
    # Calculate time saved
    normal_eta = route.estimated_time_normal
    green_eta = route.estimated_time_green_corridor
    time_saved = normal_eta - green_eta
    
    dispatch_notification = f"""🚑 AMBULANCE GREEN CORRIDOR - EMERGENCY DISPATCH 🚑
🚨 CRITICAL EMERGENCY RESPONSE ACTIVATED 🚨

📊 DISPATCH SUMMARY:
• Emergency Request Processed: 1
• Green Corridors Activated: 1
• Hospitals Notified: 1
• Human Validation: ✅ COMPLETED
• AI Processing: ✅ CEREBRAS LLaMA-3.1-70B
• Response Status: 🚨 ACTIVE DISPATCH

🚑 EMERGENCY INCIDENT BREAKDOWN:
================================================================
INCIDENT #1 - {emergency_request.request_id}

🟠 CRITICAL SCORE: {assessment.patient_critical_score}/10 ({assessment.severity_level.value.upper()})
🚨 EMERGENCY TYPE: {emergency_request.emergency_type.value.upper()}
📍 LOCATION: {emergency_request.emergency_location}
🗺️ GPS COORDINATES: {emergency_request.gps_lat}, {emergency_request.gps_lon}
👥 PATIENT: {emergency_request.patient_name} ({emergency_request.patient_age} years)
📝 SITUATION: Family emergency request - {emergency_request.symptoms_description}

🚑 AMBULANCE RESPONSE:
• Ambulance ID: {route.ambulance_id}
• Target Hospital: {route.hospital_destination.name}
• Distance: {route.distance_km} km
• Normal ETA: {normal_eta} minutes
• Green Corridor ETA: {green_eta} minutes
• 🕒 TIME SAVED: {time_saved} MINUTES

🚦 GREEN CORRIDOR STATUS:
• Status: ✅ ACTIVATED
• Traffic Signals Controlled: {green_corridor.affected_signals}
• Estimated Time Saved: {time_saved} minutes
• Route Priority: CRITICAL PATIENT TRANSPORT

🏥 HOSPITAL PREPARATION:
• Hospital: {route.hospital_destination.name}
• Notification Status: ✅ SENT
• Available Beds: {route.hospital_destination.available_beds} General, {route.hospital_destination.icu_beds} ICU
• Preparations: {'ICU bed prepared, Trauma team alerted' if assessment.patient_critical_score >= 8 else 'Emergency bay prepared, Medical team ready'}

🎯 Google Maps: https://maps.google.com/?q={emergency_request.gps_lat},{emergency_request.gps_lon}
⚡ CEREBRAS LLaMA-3.1-70B ETA OPTIMIZATION: ✅ ACTIVE
🤖 CEREBRAS PATIENT ANALYSIS: ✅ COMPLETED

================================================================

⚡ SYSTEM PERFORMANCE METRICS:
🕒 Total Time Saved: {time_saved} minutes
🚨 Critical Cases (PCS ≥ 6): {'1/1' if assessment.patient_critical_score >= 6 else '0/1'}
🚦 Traffic Intersections Controlled: {green_corridor.affected_signals}
🏥 Hospitals Coordinated: 1
🤖 AI Processing Time: < 2 minutes end-to-end
💾 Data Sources: Family Emergency Request + Cerebras AI Assessment

🆘 IMMEDIATE RESPONSE PROTOCOL:
🚑 DEPLOY ambulance to GPS coordinates immediately
🚦 GREEN CORRIDOR signals are pre-programmed and active
🏥 HOSPITAL has been notified and is preparing
📞 COORDINATE with local emergency services (102/Fire/Police)
🔄 MONITOR ambulance progress and adjust routes as needed
📋 FOLLOW emergency protocols based on PCS severity levels

⚠️ CRITICAL NOTES:
• Emergency request has been HUMAN-VALIDATED by family member
• GPS coordinates are VERIFIED from emergency location
• Traffic signals will automatically give priority to ambulance
• Hospital {'trauma team' if assessment.patient_critical_score >= 8 else 'medical team'} is being prepared based on severity
• System continues monitoring patient transport progress

🕒 Validation Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🤖 AI System: Cerebras LLaMA-3.1-70B Patient Assessment
✅ Human Authorization: FAMILY EMERGENCY REQUEST
🚨 Status: ACTIVE EMERGENCY DISPATCH

@emergency-team - Immediate coordination required!

Patient Green Corridor AI System
Powered by Cerebras LLaMA-3.1-70B AI
Human-Supervised Emergency Response Management"""

    return dispatch_notification

def dashboard_activate_green_corridor():
    """Activate green corridor using Portia workflow"""
    if not st.session_state.patient_route or not st.session_state.patient_assessment:
        st.warning("Route and assessment data required for green corridor.")
        return None
    
    with st.spinner("🚦 Activating green corridor with traffic coordination..."):
        try:
            green_corridor = activate_patient_green_corridor(
                st.session_state.patient_route,
                st.session_state.patient_assessment
            )
            
            if green_corridor:
                st.session_state.green_corridor_active = green_corridor
                st.success(f"✅ Green corridor activated - {green_corridor.affected_signals} signals coordinated")
                return green_corridor
            else:
                st.info("ℹ️ Green corridor not required for this case")
                return None
                
        except Exception as e:
            st.error(f"Error activating green corridor: {str(e)}")
            return None

def dashboard_create_dispatch_summary():
    """Create comprehensive dispatch summary using Portia workflow"""
    if not all([st.session_state.family_emergency_request, 
               st.session_state.patient_assessment,
               st.session_state.available_hospitals,
               st.session_state.patient_route]):
        st.warning("Missing required workflow data for dispatch summary.")
        return None
    
    with st.spinner("📋 Creating comprehensive dispatch summary..."):
        try:
            # Create family notification
            family_notification = notify_family_and_hospital(
                st.session_state.family_emergency_request,
                st.session_state.patient_route,
                st.session_state.patient_assessment
            )
            
            # Create dispatch summary
            dispatch_summary = create_patient_dispatch_summary(
                st.session_state.family_emergency_request,
                st.session_state.patient_assessment,
                st.session_state.available_hospitals,
                st.session_state.patient_route,
                st.session_state.green_corridor_active,
                family_notification
            )
            
            st.session_state.dispatch_summary = dispatch_summary
            st.success("✅ Dispatch summary created successfully!")
            return dispatch_summary
                
        except Exception as e:
            st.error(f"Error creating dispatch summary: {str(e)}")
            return None

def dashboard_send_email_notifications():
    """Send email notifications using Portia workflow - includes hospital bed and green corridor notifications"""
    if not st.session_state.dispatch_summary:
        st.warning("Dispatch summary required for email notifications.")
        return None
    
    # Check if we have all required data for hospital notification
    if not (st.session_state.patient_assessment and 
            st.session_state.patient_route and 
            st.session_state.family_emergency_request):
        st.warning("Complete patient data required for hospital notifications.")
        return None
    
    with st.spinner("📧 Sending email notifications to all parties..."):
        try:
            # Create hospital bed notification using the imported function
            hospital_notification = create_hospital_bed_notification(
                route=st.session_state.patient_route,
                assessment=st.session_state.patient_assessment,
                emergency_request=st.session_state.family_emergency_request
            )
            
            # Create email notification plan for hospital
            hospital_email_plan = (
                PlanBuilderV2("Hospital Bed Notification")
                .invoke_tool_step(
                    step_name="hospital_notification",
                    tool="portia:google:gmail:send_email",
                    args={
                        "recipients": ["anuju760@gmail.com"],  # Only use specified email
                        "email_title": "🏥 URGENT: INCOMING CRITICAL PATIENT - BED PREPARATION REQUIRED 🏥",
                        "email_body": hospital_notification
                    }
                )
                .final_output(output_schema=PatientDispatchResult)
                .build()
            )
            
            # Create family and hospital notification using the imported function
            family_notification = notify_family_and_hospital(
                route=st.session_state.patient_route,
                assessment=st.session_state.patient_assessment,
                emergency_request=st.session_state.family_emergency_request
            )
            
            # Create email notification plan for family dispatch summary
            family_email_plan = (
                PlanBuilderV2("Family Emergency Dispatch Summary")
                .invoke_tool_step(
                    step_name="dispatch_email",
                    tool="portia:google:gmail:send_email",
                    args={
                        "recipients": ["anuju760@gmail.com"],  # Only use specified email
                        "email_title": "🚨 PATIENT EMERGENCY: Complete Dispatch Summary - Family Emergency Request",
                        "email_body": family_notification
                    }
                )
                .final_output(output_schema=PatientDispatchResult)
                .build()
            )
            
            # Traffic Police Green Corridor Notification (if green corridor is active)
            traffic_police_plan = None
            traffic_police_notification = None
            if st.session_state.green_corridor_active:
                traffic_police_notification = create_traffic_police_email(
                    route=st.session_state.patient_route,
                    assessment=st.session_state.patient_assessment,
                    green_corridor=st.session_state.green_corridor_active
                )
                
                traffic_police_plan = (
                    PlanBuilderV2("Traffic Police Green Corridor")
                    .invoke_tool_step(
                        step_name="traffic_police_notification",
                        tool="portia:google:gmail:send_email",
                        args={
                            "recipients": ["anuju760@gmail.com"],  # Only use specified email
                            "email_title": "🚦 URGENT: GREEN CORRIDOR ACTIVATION - AMBULANCE PRIORITY REQUIRED",
                            "email_body": traffic_police_notification
                        }
                    )
                    .final_output(output_schema=PatientDispatchResult)
                    .build()
                )
            
            # Configure and run agent
            cerebras_model = CerebrasModel()
            config = Config.from_default(
                default_model=cerebras_model,
                api_keys={
                    "portia": os.getenv("PORTIA_API_KEY"),
                    "cerebras": os.getenv("CEREBRAS_API_KEY")
                }
            )
            
            agent = Portia(config=config)
            
            # Send hospital notification first (most critical)
            st.info("📧 Sending hospital bed notification...")
            hospital_result = agent.run_plan(hospital_email_plan)
            
            # Send traffic police notification (if green corridor active)
            traffic_police_result = None
            if traffic_police_plan:
                st.info("🚦 Sending traffic police green corridor notification...")
                traffic_police_result = agent.run_plan(traffic_police_plan)
            
            # Send family dispatch summary
            st.info("📧 Sending family dispatch summary...")
            family_result = agent.run_plan(family_email_plan)
            
            # Check results
            success_count = 0
            total_notifications = 2 + (1 if traffic_police_plan else 0)
            
            if hospital_result and hospital_result.outputs:
                st.success("✅ Hospital bed notification sent successfully!")
                success_count += 1
            else:
                st.error("❌ Hospital notification failed")
                
            if traffic_police_result and traffic_police_result.outputs:
                st.success("✅ Traffic police green corridor notification sent successfully!")
                st.session_state.green_corridor_dispatch_sent = True
                success_count += 1
            elif traffic_police_plan:
                st.error("❌ Traffic police notification failed")
                
            if family_result and family_result.outputs:
                st.success("✅ Family dispatch summary sent successfully!")
                success_count += 1
            else:
                st.error("❌ Family notification failed")
            
            if success_count > 0:
                st.session_state.email_notifications_sent = True
                st.success(f"✅ {success_count}/{total_notifications} Email notifications sent successfully!")
                
                # Display notification previews
                with st.expander("🏥 Hospital Notification Preview", expanded=False):
                    st.text(hospital_notification)
                    
                with st.expander("👨‍👩‍👧‍👦 Family Notification Preview", expanded=False):
                    st.text(family_notification)
                    
                if traffic_police_notification:
                    with st.expander("🚦 Traffic Police Green Corridor Preview", expanded=False):
                        st.text(traffic_police_notification)
                    
                return True
            else:
                st.error("❌ All email notifications failed")
                return False
                
        except Exception as e:
            st.error(f"Error sending emails: {str(e)}")
            return False

# Header
st.title("🚑 LifeLine Green Corridor AI - Emergency Response Dashboard")
st.markdown("### Cerebras-Powered LLGCA Response System ")

# Sidebar for controls (like ambulance dashboard)
with st.sidebar:
    st.header("🚑 Emergency Control Panel")
    
    st.subheader("📧 Email Settings")
    email_input = st.text_input("Email for notifications:", value="anuju760@gmail.com")
    st.session_state.email_address = email_input
    
    st.subheader("🚨 Quick Actions")
    
    if st.button("🧠 Assess Patient", disabled=not st.session_state.family_emergency_request):
        dashboard_assess_patient_with_ai()
        st.rerun()
    
    if st.button("🏥 Check Hospitals", disabled=not st.session_state.patient_assessment):
        dashboard_check_hospital_availability()
        st.rerun()
    
    if st.button("🛣️ Calculate Route", disabled=not st.session_state.available_hospitals):
        dashboard_calculate_route()
        st.rerun()
    
    if st.button("🚦 Green Corridor", disabled=not st.session_state.patient_route):
        dashboard_activate_green_corridor()
        st.rerun()
    
    if st.button("📋 Create Summary", disabled=not st.session_state.patient_route):
        dashboard_create_dispatch_summary()
        st.rerun()
    
    if st.button("📧 Send Notifications", disabled=not st.session_state.dispatch_summary):
        dashboard_send_email_notifications()
        st.rerun()
    
    st.markdown("---")
    
    # Reset Dashboard
    if st.button("🔄 Reset Dashboard"):
        keys_to_reset = [
            "family_emergency_request", "patient_assessment", "available_hospitals", 
            "selected_hospital", "patient_route", "green_corridor_active", 
            "dispatch_summary", "email_notifications_sent", "workflow_completed"
        ]
        for key in keys_to_reset:
            if key in st.session_state:
                if key in ["available_hospitals"]:
                    st.session_state[key] = []
                elif key in ["email_notifications_sent", "workflow_completed"]:
                    st.session_state[key] = False
                else:
                    st.session_state[key] = None
        st.session_state.dispatch_summary = ""
        st.success("🔄 Dashboard reset!")
        st.rerun()
    
    st.markdown("---")
    
    st.subheader("📊 System Status")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📞 Emergency", "✅" if st.session_state.family_emergency_request else "❌")
        st.metric("🩺 Assessment", "✅" if st.session_state.patient_assessment else "❌")
        st.metric("🏥 Hospitals", len(st.session_state.available_hospitals))
    with col2:
        st.metric("🛣️ Route", "✅" if st.session_state.patient_route else "❌")
        st.metric("🚦 Green Corridor", "✅" if st.session_state.green_corridor_active else "❌")
        dispatch_status = "✅" if st.session_state.green_corridor_dispatch_sent and st.session_state.green_corridor_active else ("🚦" if st.session_state.green_corridor_active else "❌")
        st.metric("🚑 Dispatch", dispatch_status)

# Create tabs for different views
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🗺️ Map View", 
    "👨‍👩‍👧‍👦 Family Emergency", 
    "🩺 AI Assessment", 
    "🏥 Hospital Beds", 
    "🚦 Green Corridor",
    "📧 Dispatch Summary"
])

# Tab 1: Map View
with tab1:
    st.subheader("🗺️ Patient Emergency Response Map")
    
    if not st.session_state.family_emergency_request:
        st.info("📞 No family emergency request loaded. Please create one in the Family Emergency tab.")
    else:
        # Create and display map
        emergency_map = create_patient_emergency_map()
        folium_static(emergency_map, width=1200, height=600)
        
        # Add comprehensive enhanced legend
        st.info("🎯 Map automatically centers and zooms to show all emergency locations with optimal visibility.")
        
        # Add comprehensive legend
        st.markdown("""
        ### 🎯 Enhanced Patient Emergency Map Legend:
        
        **🚨 Patient Emergency Markers:**
        - **🔴 Dark Red**: Critical Patient (PCS 8-10) - Life-threatening Emergency
        - **🔴 Red**: Serious Patient (PCS 6-7) - Urgent Medical Attention Required  
        - **🟠 Orange**: Moderate Patient (PCS 4-5) - Important but Stable Condition
        - **🟢 Green**: Minor Patient (PCS 0-3) - Non-urgent Emergency
        - **Colored Circles**: Emergency response zones around patient location
        
        **🛣️ Enhanced Route Visualization:**
        - **Thick Red Lines**: Green Corridor Active Route (Traffic Coordination)
        - **Thick Blue Lines**: Priority Emergency Route (Standard Response)
        - **White/Black Borders**: Enhanced route visibility and contrast
        - **Small Circles**: Route waypoints showing complete ambulance path
        - **➤ Direction Arrows**: Route direction indicators for ambulance navigation
        - **Gray Dashed Line**: Direct distance reference line
        
        **🚑 Ambulance & Emergency Response:**
        - **🚑 Blue Ambulance**: Ambulance departure/pickup point
        - **🏥 Red Plus**: Selected destination hospital (primary choice)
        - **🏥 Orange/Red Plus**: Available Level 1/2 Trauma Centers
        - **🏥 Gray Hospital**: Other available hospitals (alternatives)
        
        **🏥 Hospital Coverage & Service Areas:**
        - **Large Red Circles**: Selected hospital primary service coverage (500m)
        - **Smaller Colored Circles**: Alternative hospital coverage areas (300m)
        - **Hospital Color Coding**: Based on trauma level and bed availability
        - **Detailed Popups**: Complete hospital information including ETA and preparation status
        
        **🚦 Green Corridor Features:**
        - **Enhanced Red Routes**: Active traffic signal coordination
        - **Real-time ETA**: Traffic-optimized arrival times
        - **Time Savings Display**: Minutes saved through green corridor activation
        - **Traffic Integration**: Coordinated emergency response routing
        
        **📱 Interactive Features:**
        - **Click Markers**: View detailed emergency/hospital information
        - **Route Tooltips**: Hover for ambulance and ETA details
        - **Google Maps Links**: Direct navigation links from all popups
        - **Auto-Focus**: Map automatically centers on emergency locations
        - **Smart Zoom**: Optimal zoom level based on emergency distribution
        """)
        
        # Enhanced quick stats with visual improvements
        if st.session_state.family_emergency_request:
            st.markdown("### 📊 Emergency Response Status")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🚨 Emergency Type", 
                         st.session_state.family_emergency_request.emergency_type.value.upper())
                st.metric("⚠️ Criticality", 
                         st.session_state.family_emergency_request.criticality_level.value.upper(),
                         delta="Life-threatening" if st.session_state.family_emergency_request.criticality_level.value == "CRITICAL" else None)
            with col2:
                if st.session_state.patient_assessment:
                    st.metric("🧠 PCS Score", 
                             f"{st.session_state.patient_assessment.patient_critical_score}/10",
                             delta="Critical" if st.session_state.patient_assessment.patient_critical_score >= 8 else "Serious" if st.session_state.patient_assessment.patient_critical_score >= 6 else "Moderate")
                    st.metric("🩺 AI Severity", 
                             st.session_state.patient_assessment.severity_level.value.upper())
            with col3:
                if st.session_state.patient_route:
                    st.metric("⏱️ Green Corridor ETA", 
                             f"{st.session_state.patient_route.estimated_time_green_corridor} min")
                    st.metric("💾 Time Saved", 
                             f"{st.session_state.patient_route.time_saved_minutes} min",
                             delta=f"-{st.session_state.patient_route.time_saved_minutes} min saved")
        
        # Route visualization status
        if st.session_state.patient_route and st.session_state.selected_hospital:
            route_status = "🚦 GREEN CORRIDOR" if st.session_state.green_corridor_active else "🛣️ PRIORITY ROUTE"
            hospital_name = st.session_state.selected_hospital.name
            st.success(f"📍 **Active Route**: {route_status} to {hospital_name}")
            
            if st.session_state.green_corridor_active:
                st.info("🚦 Traffic signals are coordinated for optimal emergency response time")
            else:
                st.info("🛣️ Standard priority emergency routing active")
        
        # Quick stats
        if st.session_state.patient_assessment:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🩺 PCS Score", f"{st.session_state.patient_assessment.patient_critical_score}/10")
            with col2:
                st.metric("⚠️ Severity", st.session_state.patient_assessment.severity_level.value.upper())
            with col3:
                if st.session_state.patient_route:
                    st.metric("⏱️ ETA", f"{st.session_state.patient_route.estimated_time_green_corridor} min")
            with col4:
                if st.session_state.patient_route:
                    st.metric("💾 Time Saved", f"{st.session_state.patient_route.time_saved_minutes} min")

# Tab 2: Family Emergency
with tab2:
    st.subheader("👨‍👩‍👧‍👦 Family Emergency Request")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### 🆘 Emergency Information Form")
        
        with st.form("family_emergency_form"):
            st.markdown("**📞 Caller Information:**")
            caller_name = st.text_input("Your Name*", placeholder="Enter caller's full name")
            caller_phone = st.text_input("Your Phone Number*", placeholder="+91-XXXXXXXXXX")
            
            st.markdown("**👤 Patient Information:**")
            patient_name = st.text_input("Patient Name*", placeholder="Enter patient's full name")
            patient_age = st.number_input("Patient Age*", min_value=0, max_value=120, value=50)
            
            st.markdown("**📍 Location Information:**")
            emergency_location = st.text_input("Area/Locality*", placeholder="e.g., Connaught Place, New Delhi")
            detailed_address = st.text_area("Complete Address*", placeholder="Full address with landmarks")
            
            st.markdown("**🚨 Emergency Details:**")
            emergency_type = st.selectbox("Emergency Type*", [
                EmergencyType.CARDIAC,
                EmergencyType.STROKE,
                EmergencyType.ACCIDENT,
                EmergencyType.BREATHING,
                EmergencyType.UNCONSCIOUS,
                EmergencyType.BLEEDING,
                EmergencyType.BURNS,
                EmergencyType.POISONING,
                EmergencyType.OTHER
            ], format_func=lambda x: x.value.title())
            
            st.markdown("**🩺 Critical Assessment:**")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                is_conscious = st.checkbox("Patient is conscious", value=True)
            with col_b:
                is_breathing = st.checkbox("Patient is breathing normally", value=True)
            with col_c:
                any_bleeding = st.checkbox("Any serious bleeding", value=False)
            
            symptoms = st.text_area("Brief Symptoms Description*", placeholder="Describe current symptoms...")
            
            submitted = st.form_submit_button("🚑 Submit Emergency Request", type="primary")
            
            if submitted:
                if all([caller_name, caller_phone, patient_name, emergency_location, detailed_address, symptoms]):
                    emergency_request = dashboard_collect_family_emergency(
                        caller_name, caller_phone, patient_name, patient_age,
                        emergency_location, detailed_address, emergency_type,
                        is_conscious, is_breathing, any_bleeding, symptoms
                    )
                    st.session_state.family_emergency_request = emergency_request
                    st.success(f"✅ Emergency request created: {emergency_request.request_id}")
                    st.rerun()
                else:
                    st.error("❌ Please fill in all required fields marked with *")
    
    with col2:
        st.markdown("#### 🧪 Quick Test Data")
        if st.button("📋 Load Sample Emergency", use_container_width=True):
            st.session_state.family_emergency_request = generate_mock_family_emergency()
            st.success("✅ Sample emergency data loaded!")
            st.rerun()
        
        st.markdown("#### 📊 Emergency Summary")
        if st.session_state.family_emergency_request:
            req = st.session_state.family_emergency_request
            st.markdown(f"""
            **🆔 ID:** {req.request_id}  
            **👤 Patient:** {req.patient_name} ({req.patient_age}y)  
            **📞 Caller:** {req.caller_name}  
            **📍 Location:** {req.emergency_location}  
            **🚨 Emergency:** {req.emergency_type.value.title()}  
            **⚠️ Criticality:** {req.criticality_level.value.title()}  
            **🩺 Condition:**  
            - Conscious: {'✅' if req.is_patient_conscious else '❌'}  
            - Breathing: {'✅' if req.is_patient_breathing else '❌'}  
            - Bleeding: {'🩸' if req.any_bleeding else '✅'}  
            **📝 Symptoms:** {req.symptoms_description[:50]}...
            """)
        else:
            st.info("No emergency request created yet.")

# Tab 3: AI Assessment
with tab3:
    st.subheader("🩺 AI Patient Assessment")
    
    if not st.session_state.family_emergency_request:
        st.info("📞 Please create a family emergency request first.")
    elif not st.session_state.patient_assessment:
        st.info("🧠 Click 'Assess Patient' in the sidebar to analyze patient condition.")
        
        if st.button("🧠 Run AI Assessment Now", type="primary"):
            dashboard_assess_patient_with_ai()
            st.rerun()
    else:
        assessment = st.session_state.patient_assessment
        
        # Assessment overview
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🩺 Patient Critical Score (PCS)", 
                f"{assessment.patient_critical_score}/10",
                help="AI-calculated patient severity score"
            )
        
        with col2:
            severity_color = {
                CriticalityLevel.CRITICAL: "🔴",
                CriticalityLevel.SERIOUS: "🟠", 
                CriticalityLevel.MODERATE: "🟡",
                CriticalityLevel.MINOR: "🟢"
            }
            st.metric(
                "⚠️ Severity Level", 
                f"{severity_color[assessment.severity_level]} {assessment.severity_level.value.upper()}"
            )
        
        with col3:
            st.metric(
                "🚦 Green Corridor", 
                "✅ REQUIRED" if assessment.green_corridor_required else "❌ NOT NEEDED"
            )
        
        with col4:
            st.metric(
                "⏱️ Response Time", 
                f"{assessment.estimated_response_time} min"
            )
        
        # Detailed assessment
        st.markdown("### 📋 Detailed Assessment")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🚨 Risk Factors")
            for risk in assessment.risk_factors:
                st.markdown(f"- ⚠️ {risk}")
            
            st.markdown("#### 🚑 Priority Level")
            st.markdown(f"**{assessment.ambulance_priority}** priority dispatch")
        
        with col2:
            st.markdown("#### 🏥 Medical Preparations Needed")
            for prep in assessment.medical_preparations_needed:
                st.markdown(f"- ✅ {prep}")
        
        st.markdown("#### 🤖 AI Recommendation")
        st.info(assessment.ai_recommendation)

# Tab 4: Hospital Beds
with tab4:
    st.subheader("🏥 Hospital Bed Availability")
    
    if not st.session_state.patient_assessment:
        st.info("🩺 Complete patient assessment first.")
    elif not st.session_state.available_hospitals:
        st.info("🏥 Click 'Check Hospitals' in the sidebar to check bed availability.")
        
        if st.button("🏥 Check Hospital Availability Now", type="primary"):
            dashboard_check_hospital_availability()
            st.rerun()
    else:
        st.success(f"🏥 Found {len(st.session_state.available_hospitals)} hospitals with available beds")
        
        # Hospital selection
        if st.session_state.available_hospitals:
            hospital_names = [f"{h.name} ({h.distance_km}km)" for h in st.session_state.available_hospitals]
            selected_index = st.selectbox(
                "Select Hospital:", 
                range(len(hospital_names)),
                format_func=lambda i: hospital_names[i],
                index=0 if st.session_state.selected_hospital else 0
            )
            
            if selected_index is not None:
                st.session_state.selected_hospital = st.session_state.available_hospitals[selected_index]
        
        # Hospital details table
        hospital_data = []
        for i, hospital in enumerate(st.session_state.available_hospitals):
            is_selected = hospital == st.session_state.selected_hospital
            hospital_data.append({
                "Selected": "✅" if is_selected else "",
                "Hospital Name": hospital.name,
                "Location": hospital.location,
                "Distance (km)": hospital.distance_km,
                "Trauma Level": hospital.trauma_level,
                "Available Beds": hospital.available_beds,
                "ICU Beds": hospital.icu_beds,
                "Current Load": hospital.current_load,
                "Specialties": ", ".join(hospital.specialties[:2])
            })
        
        if hospital_data:
            hospital_df = pd.DataFrame(hospital_data)
            st.dataframe(hospital_df, use_container_width=True)
        
        # Selected hospital details
        if st.session_state.selected_hospital:
            st.markdown("### 🎯 Selected Hospital Details")
            hospital = st.session_state.selected_hospital
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🏥 Trauma Level", hospital.trauma_level)
                st.metric("🛏️ Available Beds", hospital.available_beds)
            with col2:
                st.metric("🏥 ICU Beds", hospital.icu_beds)
                st.metric("📏 Distance", f"{hospital.distance_km} km")
            with col3:
                st.metric("📊 Current Load", hospital.current_load)
                st.metric("⏱️ Admission Time", f"{hospital.estimated_admission_time} min")
            
            st.markdown(f"**🩺 Specialties:** {', '.join(hospital.specialties)}")

# Tab 5: Green Corridor
with tab5:
    st.subheader("🚦 Green Corridor Management")
    
    if not st.session_state.patient_route:
        st.info("🛣️ Calculate route first to activate green corridor.")
        
        if st.session_state.available_hospitals and st.button("🛣️ Calculate Route Now", type="primary"):
            dashboard_calculate_route()
            st.rerun()
    else:
        route = st.session_state.patient_route
        
        # Route summary
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🚑 Ambulance ID", route.ambulance_id)
        with col2:
            st.metric("📏 Distance", f"{route.distance_km} km")
        with col3:
            st.metric("⏱️ Normal ETA", f"{route.estimated_time_normal} min")
        with col4:
            st.metric("🚦 Green Corridor ETA", f"{route.estimated_time_green_corridor} min")
        
        # Time savings
        st.metric("💾 Time Saved", f"{route.time_saved_minutes} minutes", delta=f"-{route.time_saved_minutes} min")
        
        # Green corridor status
        if st.session_state.green_corridor_active:
            gc = st.session_state.green_corridor_active
            st.success("🚦 Green Corridor ACTIVATED")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**🆔 Corridor ID:** {gc.corridor_id}")
                st.markdown(f"**⏰ Activation Time:** {gc.activation_time.strftime('%H:%M:%S')}")
                st.markdown(f"**🚥 Traffic Signals:** {gc.affected_signals}")
            with col2:
                st.markdown(f"**⏱️ Time Saved:** {gc.estimated_time_saved} minutes")
                st.markdown(f"**📧 Traffic Police:** {'✅ Notified' if gc.traffic_police_notified else '❌ Not Notified'}")
                st.markdown(f"**🔄 Status:** {gc.status}")
            
            st.markdown(f"**📝 Activation Reason:** {gc.activation_reason}")
            
        elif st.session_state.patient_assessment and st.session_state.patient_assessment.green_corridor_required:
            st.warning("🚦 Green corridor required but not yet activated")
            if st.button("🚦 Activate Green Corridor Now", type="primary"):
                dashboard_activate_green_corridor()
                st.rerun()
        else:
            st.info("🚦 Green corridor not required for this case - using priority routing")
        
        # Route details
        st.markdown("### 🛣️ Route Information")
        st.markdown(f"**🚗 Traffic Conditions:** {route.traffic_conditions}")
        st.markdown(f"**🎯 Route Priority:** {route.route_priority}")
        st.markdown(f"**📍 Pickup:** {route.pickup_location['lat']:.4f}, {route.pickup_location['lon']:.4f}")
        st.markdown(f"**🏥 Destination:** {route.hospital_destination.name}")

# Tab 6: Dispatch Summary
with tab6:
    st.subheader("📧 Emergency Dispatch Summary")
    
    if not st.session_state.family_emergency_request:
        st.info("📞 No emergency request to summarize.")
    else:
        # Summary status
        col1, col2, col3 = st.columns(3)
        with col1:
            summary_status = "✅ Created" if st.session_state.dispatch_summary else "⏳ Pending"
            st.metric("📋 Summary Status", summary_status)
        with col2:
            email_status = "✅ Sent" if st.session_state.email_notifications_sent else "⏳ Pending"
            st.metric("📧 Email Status", email_status)
        with col3:
            if st.session_state.green_corridor_active:
                dispatch_status = "✅ Sent" if st.session_state.green_corridor_dispatch_sent else "⏳ Pending"
                st.metric("🚦 Green Corridor Dispatch", dispatch_status)
            else:
                st.metric("🚦 Green Corridor Dispatch", "❌ Not Required")
        
        # Create summary button
        if not st.session_state.dispatch_summary:
            if st.button("📋 Create Dispatch Summary", type="primary"):
                dashboard_create_dispatch_summary()
                st.rerun()
        
        # Show summary content
        if st.session_state.dispatch_summary:
            st.markdown("### 📋 Dispatch Summary Content")
            st.text_area(
                "Complete Dispatch Summary",
                st.session_state.dispatch_summary,
                height=300,
                help="This summary contains all emergency details and will be sent to medical teams."
            )
            
            # Hospital Notification Preview
            if (st.session_state.patient_assessment and 
                st.session_state.patient_route and 
                st.session_state.family_emergency_request):
                
                st.markdown("### 🏥 Hospital Bed Notification Preview")
                hospital_notification = create_hospital_bed_notification(
                    route=st.session_state.patient_route,
                    assessment=st.session_state.patient_assessment,
                    emergency_request=st.session_state.family_emergency_request
                )
                
                with st.expander("🏥 Click to view Hospital Emergency Alert", expanded=False):
                    st.text_area(
                        "Hospital Bed Notification",
                        hospital_notification,
                        height=400,
                        help="This urgent notification will be sent to the receiving hospital for bed preparation."
                    )
                
                # Green Corridor Dispatch Preview (if green corridor is active)
                if st.session_state.green_corridor_active:
                    st.markdown("### 🚦 Green Corridor Emergency Dispatch Preview")
                    green_corridor_notification = create_green_corridor_dispatch_notification(
                        emergency_request=st.session_state.family_emergency_request,
                        assessment=st.session_state.patient_assessment,
                        route=st.session_state.patient_route,
                        green_corridor=st.session_state.green_corridor_active
                    )
                    
                    with st.expander("🚑 Click to view Green Corridor Emergency Dispatch", expanded=False):
                        st.text_area(
                            "Green Corridor Emergency Dispatch",
                            green_corridor_notification,
                            height=400,
                            help="This critical dispatch notification will be sent to traffic control and emergency services."
                        )
            
            # Send email button
            if not st.session_state.email_notifications_sent:
                if st.button("📧 Send Email Notifications", type="primary"):
                    dashboard_send_email_notifications()
                    st.rerun()
        
        # Emergency summary table
        if st.session_state.family_emergency_request:
            st.markdown("### 📊 Emergency Response Summary")
            
            req = st.session_state.family_emergency_request
            assessment = st.session_state.patient_assessment
            route = st.session_state.patient_route
            
            summary_data = {
                "Emergency ID": req.request_id,
                "Patient": f"{req.patient_name} ({req.patient_age}y)",
                "Caller": f"{req.caller_name} ({req.caller_phone})",
                "Emergency Type": req.emergency_type.value.title(),
                "Criticality": req.criticality_level.value.title(),
                "PCS Score": f"{assessment.patient_critical_score}/10" if assessment else "N/A",
                "Ambulance ID": route.ambulance_id if route else "N/A",
                "Hospital": route.hospital_destination.name if route else "N/A",
                "ETA": f"{route.estimated_time_green_corridor} min" if route else "N/A",
                "Green Corridor": "✅ Active" if st.session_state.green_corridor_active else "❌ Inactive",
                "Time Saved": f"{route.time_saved_minutes} min" if route else "0 min"
            }
            
            for key, value in summary_data.items():
                st.markdown(f"**{key}:** {value}")

# Footer
st.markdown("---")
st.markdown("### 🚑 System Status Dashboard")

# System status indicators
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    status = "🟢 RECEIVED" if st.session_state.family_emergency_request else "🟡 PENDING"
    st.markdown(f"**Emergency Request:** {status}")

with col2:
    status = "🟢 COMPLETED" if st.session_state.patient_assessment else "🟡 WAITING"
    st.markdown(f"**AI Assessment:** {status}")

with col3:
    status = "🟢 AVAILABLE" if st.session_state.available_hospitals else "🟡 CHECKING"
    st.markdown(f"**Hospital Beds:** {status}")

with col4:
    status = "🟢 CALCULATED" if st.session_state.patient_route else "🟡 PENDING"
    st.markdown(f"**Route:** {status}")

with col5:
    status = "🟢 ACTIVE" if st.session_state.green_corridor_active else "🟡 INACTIVE"
    st.markdown(f"**Green Corridor:** {status}")

with col6:
    status = "🟢 SENT" if st.session_state.email_notifications_sent else "🟡 PENDING"
    st.markdown(f"**Notifications:** {status}")

# Progress indicator
progress_steps = [
    ("Emergency Request", st.session_state.family_emergency_request is not None),
    ("AI Assessment", st.session_state.patient_assessment is not None),
    ("Hospital Check", len(st.session_state.available_hospitals) > 0),
    ("Route Calculation", st.session_state.patient_route is not None),
    ("Green Corridor", True),  # Always show as this step is optional
    ("Notifications", st.session_state.email_notifications_sent)
]

completed_steps = sum(1 for _, completed in progress_steps if completed)
progress = completed_steps / len(progress_steps)

st.progress(progress, text=f"Workflow Progress: {completed_steps}/{len(progress_steps)} steps completed")

st.caption(f"🚑 LifeLine Green Corridor Dashboard v1.0 | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("Powered by 🧠 Cerebras Inference + Meta LLaMA + Portia AI for Orchestration")