import streamlit as st
import folium
from streamlit_folium import folium_static
import pandas as pd
from datetime import datetime
import os
import json
from typing import List
from dotenv import load_dotenv


from realtime_incident_ambulance_workflow import (
    Accident, AccidentSeverity, DetectedAccidents, PCSAssessment, PCSResults,
    Hospital, RouteOptimization, RouteResults, GreenCorridorActivation, 
    GreenCorridorResults, HospitalNotification, NotificationResults,
    FinalDispatchResult, AccidentData,
    search_accident_news, analyze_accident_with_cerebras, parse_cerebras_accidents,
    calculate_pcs_with_cerebras, parse_cerebras_pcs, calculate_route_with_cerebras,
    activate_green_corridor_sumo, notify_hospitals_fhir, create_dispatch_summary,
    create_detailed_ambulance_dispatch_email, create_ambulance_green_corridor_plan,
    create_traffic_police_email, create_hospital_bed_notification, create_ambulance_dispatch_notification,
    Config, Portia, PlanBuilderV2, StepOutput
)

# Import custom Cerebras model
from src.models.cerebras_model import CerebrasModel

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="LifeLine Green Corridor - Emergency Response Dashboard",
    page_icon="🚑",
    layout="wide"
)

# Initialize session state variables
if "detected_accidents" not in st.session_state:
    st.session_state.detected_accidents = []
if "approved_accidents" not in st.session_state:
    st.session_state.approved_accidents = []
if "rejected_accidents" not in st.session_state:
    st.session_state.rejected_accidents = []
if "pcs_results" not in st.session_state:
    st.session_state.pcs_results = []
if "route_results" not in st.session_state:
    st.session_state.route_results = []
if "green_corridor_results" not in st.session_state:
    st.session_state.green_corridor_results = []
if "hospital_notifications" not in st.session_state:
    st.session_state.hospital_notifications = []
if "dispatch_summary" not in st.session_state:
    st.session_state.dispatch_summary = ""
if "email_sent" not in st.session_state:
    st.session_state.email_sent = False
if "agent_active" not in st.session_state:
    st.session_state.agent_active = False

# Dashboard version of human approval function
def dashboard_get_human_approval_for_accidents(detected_accidents: DetectedAccidents) -> DetectedAccidents:
    """
    This replaces the CLI approval function with a dashboard version
    that just passes through the data for UI approval
    """
    st.session_state.detected_accidents = detected_accidents.accidents
    # Return empty approval data since we'll handle actual approval in the UI
    return DetectedAccidents(accidents=[])

# Create data fetch plan that stops after accident detection and PCS calculation
def create_accident_detection_plan():
    """Create a modified plan that stops after accident detection"""
    return (
        PlanBuilderV2("Accident Detection and Analysis")
        .function_step(
            function=search_accident_news,
            args={}
        )
        .function_step(
            function=lambda news_data: parse_cerebras_accidents(analyze_accident_with_cerebras(news_data.raw_news_data)),
            args={"news_data": StepOutput(0)}
        )
        .final_output(output_schema=DetectedAccidents)
        .build()
    )

# Fetch real accident data
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_accident_data():
    """Fetch real accident data using the Portia agent with Cerebras"""
    try:
        st.info("🔍 Searching for recent accidents using Tavily + Cerebras AI... This may take a few moments.")
        
        # Import and use custom Cerebras model
        cerebras_model = CerebrasModel()
        
        # Configure agent with custom Cerebras model
        config = Config.from_default(
            default_model=cerebras_model,
            api_keys={
                "portia": os.getenv("PORTIA_API_KEY"),
                "tavily": os.getenv("TAVILY_API_KEY"),
                "cerebras": os.getenv("CEREBRAS_API_KEY")
            }
        )
        
        agent = Portia(config=config)
        detection_plan = create_accident_detection_plan()
        
        # Run the plan
        result = agent.run_plan(detection_plan)
        
        if result and result.outputs and result.outputs.final_output:
            detected_accidents = result.outputs.final_output.value
            
            if hasattr(detected_accidents, 'accidents') and detected_accidents.accidents:
                st.session_state.detected_accidents = detected_accidents.accidents
                st.session_state.agent_active = True
                return detected_accidents.accidents
            else:
                st.error("No accident data found in agent response")
                return []
        else:
            st.error("No result returned from Portia agent")
            return []
    except Exception as e:
        st.error(f"Error fetching accident data: {str(e)}")
        return []

# Generate mock accidents for testing
def generate_mock_accidents():
    """Generate varied mock accidents for testing with unique IDs and locations"""
    import random
    from datetime import timedelta
    
    base_time = datetime.now()
    accidents = []
    
    # Create diverse accident scenarios across different US cities
    accident_templates = [
        {
            "id": f"ACC_{base_time.strftime('%Y%m%d%H%M%S')}01",
            "description": "Multi-vehicle collision on I-95 near Miami, multiple injuries reported with fire hazard",
            "location": "I-95 Highway, Miami, FL",
            "gps_lat": 25.7617,
            "gps_lon": -80.1918,
            "severity_indicators": ["multi-vehicle", "multiple injuries", "fire hazard", "highway"],
            "news_sources": ["Miami Herald", "Local News"],
            "confidence_score": 0.92
        },
        {
            "id": f"ACC_{base_time.strftime('%Y%m%d%H%M%S')}02", 
            "description": "Pedestrian struck by vehicle at busy intersection during rush hour",
            "location": "Times Square, New York, NY",
            "gps_lat": 40.7580,
            "gps_lon": -73.9855,
            "severity_indicators": ["pedestrian", "busy intersection", "rush hour"],
            "news_sources": ["NY1", "ABC News"],
            "confidence_score": 0.88
        },
        {
            "id": f"ACC_{base_time.strftime('%Y%m%d%H%M%S')}03",
            "description": "Head-on collision between two vehicles on mountain highway, entrapment reported", 
            "location": "Highway 1, Big Sur, CA",
            "gps_lat": 36.2679,
            "gps_lon": -121.8073,
            "severity_indicators": ["head-on collision", "entrapment", "mountain highway"],
            "news_sources": ["San Francisco Chronicle"],
            "confidence_score": 0.95
        },
        {
            "id": f"ACC_{base_time.strftime('%Y%m%d%H%M%S')}04",
            "description": "School bus accident with children injured on city road",
            "location": "Main Street, Austin, TX", 
            "gps_lat": 30.2672,
            "gps_lon": -97.7431,
            "severity_indicators": ["school bus", "children", "multiple injuries"],
            "news_sources": ["Austin American-Statesman"],
            "confidence_score": 0.94
        },
        {
            "id": f"ACC_{base_time.strftime('%Y%m%d%H%M%S')}05",
            "description": "Motorcycle accident on bridge with potential spinal injury",
            "location": "Golden Gate Bridge, San Francisco, CA",
            "gps_lat": 37.8199,
            "gps_lon": -122.4783,
            "severity_indicators": ["motorcycle", "bridge", "spinal injury"],
            "news_sources": ["SF Chronicle"],
            "confidence_score": 0.89
        }
    ]
    
    # Create 3-5 random accidents from templates
    num_accidents = random.randint(3, 5)
    selected_accidents = random.sample(accident_templates, num_accidents)
    
    for i, acc_data in enumerate(selected_accidents):
        # Add slight time variations
        timestamp = base_time - timedelta(minutes=random.randint(1, 30))
        
        accidents.append(Accident(
            id=acc_data["id"],
            description=acc_data["description"],
            location=acc_data["location"],
            gps_lat=acc_data["gps_lat"],
            gps_lon=acc_data["gps_lon"],
            timestamp=timestamp,
            severity_indicators=acc_data["severity_indicators"],
            news_sources=acc_data["news_sources"],
            confidence_score=acc_data["confidence_score"]
        ))
    
    return accidents

# Get marker color based on PCS score
def get_pcs_marker_color(pcs_score):
    """Get marker color based on Patient Critical Score"""
    if pcs_score >= 8:
        return "darkred"
    elif pcs_score >= 6:
        return "red"
    elif pcs_score >= 4:
        return "orange"
    elif pcs_score >= 2:
        return "lightred"
    else:
        return "green"

def get_accident_icon():
    """Get icon for accidents"""
    return "ambulance", "fa"

# Create comprehensive map showing all stages
def create_ambulance_map():
    """Create a Folium map with all accident markers and routes"""
    
    # Collect all accident coordinates to calculate center and zoom
    all_coordinates = []
    
    # Add detected accidents coordinates
    for accident in st.session_state.detected_accidents:
        all_coordinates.append([accident.gps_lat, accident.gps_lon])
    
    # Add approved accidents coordinates
    for accident in st.session_state.approved_accidents:
        all_coordinates.append([accident.gps_lat, accident.gps_lon])
        
        # Also add hospital coordinates for approved accidents to show complete route area
        for route in st.session_state.route_results:
            if route.accident_id == accident.id:
                all_coordinates.append([route.target_hospital.gps_lat, route.target_hospital.gps_lon])
                break
        
    # Add rejected accidents coordinates
    for accident, reason in st.session_state.rejected_accidents:
        all_coordinates.append([accident.gps_lat, accident.gps_lon])
    
    # Calculate optimal map center and zoom
    if all_coordinates:
        # Calculate center point of all incidents
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
        if max_diff < 0.01:  # Very close incidents
            zoom_level = 13
        elif max_diff < 0.05:  # City-level spread
            zoom_level = 11
        elif max_diff < 0.2:  # Regional spread
            zoom_level = 9
        elif max_diff < 1.0:  # State-level spread
            zoom_level = 7
        else:  # Multi-state spread
            zoom_level = 5
        
        # Create map centered on incidents
        m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)
        
        # For better viewing, fit bounds to show all incidents with some padding
        if len(all_coordinates) > 1:
            # Add some padding around the incidents
            padding = max(0.01, max_diff * 0.1)  # 10% padding, minimum 0.01 degrees
            southwest = [min_lat - padding, min_lon - padding]
            northeast = [max_lat + padding, max_lon + padding]
            m.fit_bounds([southwest, northeast])
    else:
        # Fallback: Center map on US if no incidents
        m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)
    
    # Add detected accidents (pending approval) with enhanced visibility
    for accident in st.session_state.detected_accidents:
        # Find PCS data for this accident
        pcs_data = None
        for pcs in st.session_state.pcs_results:
            if pcs.accident_id == accident.id:
                pcs_data = pcs
                break
        
        color = get_pcs_marker_color(pcs_data.patient_critical_score if pcs_data else 5)
        icon_name, icon_prefix = get_accident_icon()
        
        popup_html = f"""
        <div style="min-width:300px;">
            <h4 style="color:blue;">🚨 {accident.id} - PENDING APPROVAL</h4>
            <b>📍 Location:</b> {accident.location}<br>
            <b>🗺️ GPS:</b> {accident.gps_lat}, {accident.gps_lon}<br>
            <b>⏰ Time:</b> {accident.timestamp.strftime('%H:%M:%S')}<br>
            <b>🎯 Confidence:</b> <span style="color:{'green' if accident.confidence_score >= 0.9 else 'orange' if accident.confidence_score >= 0.7 else 'red'};font-weight:bold;">{accident.confidence_score:.2f}</span><br>
            <b>⚠️ Severity:</b> {', '.join(accident.severity_indicators)}<br>
            <b>🧠 PCS Score:</b> {pcs_data.patient_critical_score if pcs_data else 'Calculating...'}/10<br>
            <b>📰 Sources:</b> {', '.join(accident.news_sources)}<br>
            <b>📝 Description:</b> {accident.description}<br>
            <hr>
            <a href="https://maps.google.com/?q={accident.gps_lat},{accident.gps_lon}" target="_blank" style="color:blue;">🎯 View on Google Maps</a>
        </div>
        """
        
        # Enhanced accident marker with pulsing effect
        folium.Marker(
            [accident.gps_lat, accident.gps_lon],
            popup=folium.Popup(popup_html, max_width=400),
            tooltip=f"🚨 {accident.id} - PENDING APPROVAL (Confidence: {accident.confidence_score:.2f})",
            icon=folium.Icon(color=color, icon=icon_name, prefix=icon_prefix)
        ).add_to(m)
        
        # Add a pulsing circle around pending accidents for visibility
        folium.Circle(
            [accident.gps_lat, accident.gps_lon],
            radius=150,
            color='blue',
            fillColor='lightblue',
            fillOpacity=0.2,
            opacity=0.5,
            popup=f"🚨 Emergency Zone: {accident.id}",
            tooltip="Pending Accident - Awaiting Approval"
        ).add_to(m)
    
    # Add approved accidents with routes
    for accident in st.session_state.approved_accidents:
        # Find associated data
        pcs_data = None
        route_data = None
        gc_data = None
        
        for pcs in st.session_state.pcs_results:
            if pcs.accident_id == accident.id:
                pcs_data = pcs
                break
        
        for route in st.session_state.route_results:
            if route.accident_id == accident.id:
                route_data = route
                break
        
        for gc in st.session_state.green_corridor_results:
            if gc.accident_id == accident.id:
                gc_data = gc
                break
        
        popup_html = f"""
        <div style="min-width:350px;">
            <h4 style="color:green;">✅ {accident.id} - APPROVED & DISPATCHED</h4>
            <b>📍 Location:</b> {accident.location}<br>
            <b>⏰ Time:</b> {accident.timestamp.strftime('%H:%M:%S')}<br>
            <b>🧠 PCS Score:</b> <span style="color:{'darkred' if pcs_data and pcs_data.patient_critical_score >= 8 else 'red' if pcs_data and pcs_data.patient_critical_score >= 6 else 'orange' if pcs_data and pcs_data.patient_critical_score >= 4 else 'green'};font-weight:bold;">{pcs_data.patient_critical_score if pcs_data else 'N/A'}/10</span><br>
            <b>🚑 Ambulance:</b> {route_data.ambulance_id if route_data else 'N/A'}<br>
            <b>🏥 Hospital:</b> {route_data.target_hospital.name if route_data else 'N/A'}<br>
            <b>📏 Distance:</b> {route_data.distance_km if route_data else 'N/A'} km<br>
            <b>🕐 ETA Normal:</b> {route_data.estimated_time_normal if route_data else 'N/A'} min<br>
            <b>🚦 ETA Green Corridor:</b> {route_data.estimated_time_green_corridor if route_data else 'N/A'} min<br>
            <b>⏱️ Time Saved:</b> <span style="color:green;font-weight:bold;">{route_data.time_saved_minutes if route_data else 0} min</span><br>
            <b>🚦 Green Corridor:</b> <span style="color:{'green' if gc_data else 'red'};font-weight:bold;">{'✅ ACTIVE' if gc_data else '❌ INACTIVE'}</span><br>
            <b>🚨 Traffic Signals:</b> {route_data.traffic_intersections if route_data else 'N/A'}<br>
            <hr>
            <a href="https://maps.google.com/?q={accident.gps_lat},{accident.gps_lon}" target="_blank" style="color:green;">🎯 View on Google Maps</a>
        </div>
        """
        
        # Enhanced accident marker for approved accidents
        folium.Marker(
            [accident.gps_lat, accident.gps_lon],
            popup=folium.Popup(popup_html, max_width=400),
            tooltip=f"✅ {accident.id} - DISPATCHED | 🚑 {route_data.ambulance_id if route_data else 'N/A'} | ⏱️ {route_data.time_saved_minutes if route_data else 0} min saved",
            icon=folium.Icon(color="green", icon="check", prefix="fa")
        ).add_to(m)
        
        # Add a larger, more visible circle around approved accidents
        folium.Circle(
            [accident.gps_lat, accident.gps_lon],
            radius=300,  # Larger radius for approved accidents
            color='green',
            fillColor='lightgreen',
            fillOpacity=0.15,
            opacity=0.6,
            weight=2,
            popup=f"🚑 Active Emergency Response Zone: {accident.id}",
            tooltip="APPROVED - Emergency Response Active"
        ).add_to(m)
        
        # Add route line if available with enhanced visualization
        if route_data and hasattr(route_data, 'route_coordinates') and route_data.route_coordinates:
            # Handle different coordinate formats
            route_coords = []
            for coord in route_data.route_coordinates:
                if isinstance(coord, dict):
                    # Dictionary format: {"lat": x, "lon": y}
                    route_coords.append((coord.get("lat", coord.get("latitude")), coord.get("lon", coord.get("longitude"))))
                elif isinstance(coord, (list, tuple)) and len(coord) >= 2:
                    # List/tuple format: [lat, lon] or (lat, lon)
                    route_coords.append((coord[0], coord[1]))
                else:
                    # Skip invalid coordinates
                    continue
            
            # Ensure we have the accident and hospital as start/end points
            if route_coords:
                # Make sure accident location is the first point
                accident_coord = (accident.gps_lat, accident.gps_lon)
                if route_coords[0] != accident_coord:
                    route_coords.insert(0, accident_coord)
                
                # Make sure hospital location is the last point
                hospital_coord = (route_data.target_hospital.gps_lat, route_data.target_hospital.gps_lon)
                if route_coords[-1] != hospital_coord:
                    route_coords.append(hospital_coord)
            else:
                # If no route coordinates, create direct path from accident to hospital
                route_coords = [
                    (accident.gps_lat, accident.gps_lon),
                    (route_data.target_hospital.gps_lat, route_data.target_hospital.gps_lon)
                ]
            
            # Generate unique colors for each route to avoid overlap confusion
            route_colors = ["#FF4444", "#4444FF", "#44FF44", "#FF44FF", "#44FFFF", "#FFFF44", "#FF8844", "#8844FF", "#44FF88"]
            approved_accident_ids = [acc.id for acc in st.session_state.approved_accidents]
            try:
                color_index = approved_accident_ids.index(accident.id) % len(route_colors)
                route_color = route_colors[color_index]
            except ValueError:
                route_color = "#FF4444"  # Default red
            
            # Determine line style based on green corridor status
            if gc_data:
                line_weight = 7
                line_opacity = 1.0
                line_style = "solid"
                route_label = f"🟢 GREEN CORRIDOR: {route_data.ambulance_id} → {route_data.target_hospital.name}"
            else:
                line_weight = 5
                line_opacity = 0.8
                line_style = "dashed"
                route_label = f"🔵 NORMAL ROUTE: {route_data.ambulance_id} → {route_data.target_hospital.name}"
            
            # Add a thick white border for better visibility
            folium.PolyLine(
                route_coords,
                color='white',
                weight=line_weight + 4,
                opacity=0.8
            ).add_to(m)
            
            # Add a thinner black border for definition
            folium.PolyLine(
                route_coords,
                color='black',
                weight=line_weight + 2,
                opacity=0.6
            ).add_to(m)
            
            # Create the main route line with enhanced visibility
            main_route = folium.PolyLine(
                route_coords,
                color=route_color,
                weight=line_weight,
                opacity=line_opacity,
                popup=folium.Popup(f"""
                <div style="min-width:250px;">
                    <h4>{route_label}</h4>
                    <b>Accident:</b> {accident.id}<br>
                    <b>Distance:</b> {route_data.distance_km} km<br>
                    <b>Normal ETA:</b> {route_data.estimated_time_normal} min<br>
                    <b>Green Corridor ETA:</b> {route_data.estimated_time_green_corridor} min<br>
                    <b>Time Saved:</b> {route_data.time_saved_minutes} min<br>
                    <b>Intersections:</b> {route_data.traffic_intersections}<br>
                    <b>Status:</b> {'GREEN CORRIDOR ACTIVE' if gc_data else 'NORMAL ROUTING'}<br>
                    <b>Path Points:</b> {len(route_coords)} coordinates
                </div>
                """, max_width=300),
                tooltip=f"🚑 {route_data.ambulance_id} → 🏥 {route_data.target_hospital.name} ({route_data.time_saved_minutes} min saved)"
            ).add_to(m)
            
            # Add enhanced directional arrows and waypoints along the complete route
            if len(route_coords) >= 2:
                # Add start marker (🚑 Ambulance at accident site)
                folium.Marker(
                    route_coords[0],
                    icon=folium.DivIcon(
                        html=f'<div style="background-color:white;border:2px solid {route_color};border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:12px;">🚑</div>',
                        icon_size=(24, 24),
                        icon_anchor=(12, 12)
                    ),
                    tooltip=f"🚑 Start: {route_data.ambulance_id} at {accident.id}",
                    popup=f"Ambulance {route_data.ambulance_id} departure point"
                ).add_to(m)
                
                # Add end marker (🏥 Hospital destination)
                folium.Marker(
                    route_coords[-1],
                    icon=folium.DivIcon(
                        html=f'<div style="background-color:white;border:2px solid {route_color};border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:12px;">🏥</div>',
                        icon_size=(24, 24),
                        icon_anchor=(12, 12)
                    ),
                    tooltip=f"🏥 Destination: {route_data.target_hospital.name}",
                    popup=f"Hospital destination for {route_data.ambulance_id}"
                ).add_to(m)
                
                # Add directional arrows at regular intervals along the route
                if len(route_coords) > 2:
                    arrow_count = min(8, len(route_coords) - 1)  # Up to 8 arrows
                    step = max(1, (len(route_coords) - 1) // arrow_count)
                    
                    for i in range(1, len(route_coords) - 1, step):
                        arrow_location = route_coords[i]
                        
                        # Calculate direction for arrow
                        prev_coord = route_coords[i-1]
                        next_coord = route_coords[min(i+1, len(route_coords)-1)]
                        
                        # Direction arrow with better styling
                        folium.Marker(
                            arrow_location,
                            icon=folium.DivIcon(
                                html=f'<div style="color:{route_color};font-size:20px;font-weight:bold;text-shadow:1px 1px 2px white;background-color:rgba(255,255,255,0.8);border-radius:50%;width:20px;height:20px;display:flex;align-items:center;justify-content:center;">➤</div>',
                                icon_size=(20, 20),
                                icon_anchor=(10, 10)
                            ),
                            tooltip=f"🚑 Route direction: {route_data.ambulance_id}"
                        ).add_to(m)
                
                # Add waypoint markers every few points for complete path visibility
                waypoint_step = max(1, len(route_coords) // 10)  # Show up to 10 waypoints
                for i in range(1, len(route_coords) - 1, waypoint_step):
                    coord = route_coords[i]
                    folium.CircleMarker(
                        [coord[0], coord[1]],
                        radius=4,
                        color=route_color,
                        fillColor='white',
                        fillOpacity=0.8,
                        weight=2,
                        popup=f"Waypoint {i+1}/{len(route_coords)} - {route_data.ambulance_id}",
                        tooltip=f"Route point {i+1}"
                    ).add_to(m)
            
            # Add hospital marker with enhanced details
            hospital = route_data.target_hospital
            hospital_popup = f"""
            <div style="min-width:250px;">
                <h4>🏥 {hospital.name}</h4>
                <b>Location:</b> {hospital.location}<br>
                <b>Trauma Level:</b> Level {hospital.trauma_level}<br>
                <b>Available Beds:</b> {hospital.available_beds}<br>
                <b>Specialties:</b> {', '.join(hospital.specialties) if hasattr(hospital, 'specialties') else 'General Emergency'}<br>
                <b>Distance from Accident:</b> {hospital.distance_km} km<br>
                <b>Incoming Ambulance:</b> {route_data.ambulance_id}<br>
                <b>Expected Arrival:</b> {route_data.estimated_time_green_corridor if gc_data else route_data.estimated_time_normal} min
            </div>
            """
            
            # Enhanced hospital marker with size based on trauma level
            hospital_marker = folium.Marker(
                [hospital.gps_lat, hospital.gps_lon],
                popup=folium.Popup(hospital_popup, max_width=300),
                tooltip=f"🏥 {hospital.name} - Level {hospital.trauma_level} Trauma Center",
                icon=folium.Icon(
                    color="red" if hospital.trauma_level == 1 else "orange",
                    icon="plus", 
                    prefix="fa"
                )
            ).add_to(m)
            
            # Add hospital coverage circle to show service area
            coverage_radius = 500 if hospital.trauma_level == 1 else 300
            folium.Circle(
                [hospital.gps_lat, hospital.gps_lon],
                radius=coverage_radius,
                color='red' if hospital.trauma_level == 1 else 'orange',
                fillColor='lightcoral' if hospital.trauma_level == 1 else 'lightyellow',
                fillOpacity=0.1,
                opacity=0.2,
                popup=f"🏥 {hospital.name} Service Area",
                tooltip=f"Hospital Coverage: {coverage_radius}m radius"
            ).add_to(m)
            
            # Add connecting line from accident to hospital for clarity
            folium.PolyLine(
                [[accident.gps_lat, accident.gps_lon], [hospital.gps_lat, hospital.gps_lon]],
                color='gray',
                weight=2,
                opacity=0.4,
                dash_array='5, 10',
                popup=f"Direct line: {accident.id} → {hospital.name}"
            ).add_to(m)
    
    # Add rejected accidents
    for accident, reason in st.session_state.rejected_accidents:
        popup_html = f"""
        <div style="min-width:250px;">
            <h4>{accident.id} - REJECTED ❌</h4>
            <b>Location:</b> {accident.location}<br>
            <b>Reason:</b> {reason}<br>
            <b>Description:</b> {accident.description}<br>
            <a href="https://maps.google.com/?q={accident.gps_lat},{accident.gps_lon}" target="_blank">Open in Google Maps</a>
        </div>
        """
        
        folium.Marker(
            [accident.gps_lat, accident.gps_lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{accident.id} - REJECTED",
            icon=folium.Icon(color="gray", icon="times", prefix="fa")
        ).add_to(m)
    
    return m

# Approve accident
def approve_accident(accident):
    """Approve an accident and move it to approved list"""
    if accident not in st.session_state.approved_accidents:
        st.session_state.approved_accidents.append(accident)
        if accident in st.session_state.detected_accidents:
            st.session_state.detected_accidents.remove(accident)
        st.success(f"🚑 Accident {accident.id} approved for ambulance dispatch!")

# Reject accident
def reject_accident(accident, reason):
    """Reject an accident and move it to rejected list"""
    if not reason:
        st.error("Please provide a reason for rejection.")
        return
    
    st.session_state.rejected_accidents.append((accident, reason))
    if accident in st.session_state.detected_accidents:
        st.session_state.detected_accidents.remove(accident)
    st.error(f"❌ Accident {accident.id} rejected: {reason}")

# Calculate PCS for approved accidents
def calculate_pcs_for_approved():
    """Calculate Patient Critical Score for approved accidents"""
    if not st.session_state.approved_accidents:
        st.warning("No approved accidents to assess.")
        return
    
    with st.spinner("🧠 Calculating Patient Critical Scores using Cerebras AI..."):
        try:
            # Convert accidents to JSON for Cerebras
            accidents_json = json.dumps([acc.model_dump() for acc in st.session_state.approved_accidents], default=str)
            
            # Get PCS assessment from Cerebras
            pcs_response = calculate_pcs_with_cerebras(accidents_json)
            pcs_results = parse_cerebras_pcs(pcs_response)
            
            st.session_state.pcs_results = pcs_results.assessments
            st.success(f"✅ PCS calculated for {len(pcs_results.assessments)} accidents")
            
        except Exception as e:
            st.error(f"Error calculating PCS: {str(e)}")

# Calculate routes for assessed accidents
def calculate_routes():
    """Calculate optimal routes for accidents with PCS"""
    if not st.session_state.pcs_results:
        st.warning("No PCS assessments available for route calculation.")
        return
    
    with st.spinner("🛣️ Calculating optimal routes with Cerebras AI ETA prediction..."):
        try:
            pcs_results_obj = PCSResults(assessments=st.session_state.pcs_results)
            route_results = calculate_route_with_cerebras(pcs_results_obj)
            
            st.session_state.route_results = route_results.routes
            st.success(f"✅ Routes calculated for {len(route_results.routes)} ambulances")
            
        except Exception as e:
            st.error(f"Error calculating routes: {str(e)}")

# Activate green corridors
def activate_green_corridors():
    """Activate green corridors for qualifying routes"""
    if not st.session_state.route_results:
        st.warning("No routes available for green corridor activation.")
        return
    
    with st.spinner("🚦 Activating green corridors and coordinating traffic signals..."):
        try:
            route_results_obj = RouteResults(routes=st.session_state.route_results)
            gc_results = activate_green_corridor_sumo(route_results_obj)
            
            st.session_state.green_corridor_results = gc_results.activations
            st.success(f"✅ {len(gc_results.activations)} green corridors activated")
            
        except Exception as e:
            st.error(f"Error activating green corridors: {str(e)}")

# Send hospital notifications
def send_hospital_notifications():
    """Send notifications to hospitals"""
    if not st.session_state.route_results or not st.session_state.pcs_results:
        st.warning("Missing route or PCS data for hospital notifications.")
        return
    
    with st.spinner("🏥 Sending hospital notifications via FHIR..."):
        try:
            route_results_obj = RouteResults(routes=st.session_state.route_results)
            pcs_results_obj = PCSResults(assessments=st.session_state.pcs_results)
            
            notifications = notify_hospitals_fhir(route_results_obj, pcs_results_obj)
            
            st.session_state.hospital_notifications = notifications.notifications
            st.success(f"✅ {len(notifications.notifications)} hospitals notified")
            
        except Exception as e:
            st.error(f"Error sending hospital notifications: {str(e)}")

# Send three-email notifications
def send_three_email_notifications():
    """Send three separate email notifications: Traffic Police, Hospital, and Dispatch Summary"""
    if not st.session_state.approved_accidents or not st.session_state.route_results:
        st.warning("Complete route calculations required for email notifications.")
        return None
    
    with st.spinner("📧 Sending three-email notification system..."):
        try:
            # Get the first approved accident and its route for email content
            accident = st.session_state.approved_accidents[0]
            route = st.session_state.route_results[0] if st.session_state.route_results else None
            pcs = st.session_state.pcs_results[0] if st.session_state.pcs_results else None
            gc = st.session_state.green_corridor_results[0] if st.session_state.green_corridor_results else None
            
            if not all([accident, route, pcs]):
                st.error("Missing required data for email notifications")
                return None
            
            # Create three email notifications
            traffic_police_notification = create_traffic_police_email(route, pcs, gc) if gc else "Green corridor not activated"
            hospital_notification = create_hospital_bed_notification(route, pcs, accident)
            dispatch_notification = create_ambulance_dispatch_notification(route, pcs, accident, gc)
            
            # Create three separate email plans
            # 1. Traffic Police Email (only if green corridor active)
            traffic_police_plan = None
            if gc:
                traffic_police_plan = (
                    PlanBuilderV2("Traffic Police Green Corridor Notification")
                    .invoke_tool_step(
                        step_name="traffic_police_email",
                        tool="portia:google:gmail:send_email",
                        args={
                            "recipients": [st.session_state.get("email_address", "anuju760@gmail.com")],
                            "email_title": "🚦 URGENT: GREEN CORRIDOR ACTIVATION - AMBULANCE PRIORITY REQUIRED",
                            "email_body": traffic_police_notification
                        }
                    )
                    .final_output(output_schema=FinalDispatchResult)
                    .build()
                )
            
            # 2. Hospital Bed Preparation Email
            hospital_plan = (
                PlanBuilderV2("Hospital Bed Preparation Notification")
                .invoke_tool_step(
                    step_name="hospital_email",
                    tool="portia:google:gmail:send_email",
                    args={
                        "recipients": [st.session_state.get("email_address", "anuju760@gmail.com")],
                        "email_title": "🏥 URGENT: INCOMING CRITICAL PATIENT - BED PREPARATION REQUIRED 🏥",
                        "email_body": hospital_notification
                    }
                )
                .final_output(output_schema=FinalDispatchResult)
                .build()
            )
            
            # 3. Comprehensive Dispatch Summary Email
            dispatch_plan = (
                PlanBuilderV2("Emergency Dispatch Summary")
                .invoke_tool_step(
                    step_name="dispatch_email",
                    tool="portia:google:gmail:send_email",
                    args={
                        "recipients": [st.session_state.get("email_address", "anuju760@gmail.com")],
                        "email_title": "🚑 AMBULANCE EMERGENCY DISPATCH - CRITICAL INCIDENT RESPONSE 🚑",
                        "email_body": dispatch_notification
                    }
                )
                .final_output(output_schema=FinalDispatchResult)
                .build()
            )
            
            # Configure agent with Cerebras
            cerebras_model = CerebrasModel()
            config = Config.from_default(
                default_model=cerebras_model,
                api_keys={
                    "portia": os.getenv("PORTIA_API_KEY"),
                    "cerebras": os.getenv("CEREBRAS_API_KEY")
                }
            )
            
            agent = Portia(config=config)
            
            # Send emails sequentially
            success_count = 0
            total_emails = 2 + (1 if traffic_police_plan else 0)
            
            # Send hospital notification first (most critical)
            st.info("📧 Sending hospital bed preparation notification...")
            hospital_result = agent.run_plan(hospital_plan)
            if hospital_result and hospital_result.outputs:
                st.success("✅ Hospital notification sent successfully!")
                success_count += 1
            else:
                st.error("❌ Hospital notification failed")
            
            # Send traffic police notification (if green corridor active)
            if traffic_police_plan:
                st.info("🚦 Sending traffic police green corridor notification...")
                traffic_result = agent.run_plan(traffic_police_plan)
                if traffic_result and traffic_result.outputs:
                    st.success("✅ Traffic police notification sent successfully!")
                    success_count += 1
                else:
                    st.error("❌ Traffic police notification failed")
            
            # Send dispatch summary
            st.info("📧 Sending comprehensive dispatch summary...")
            dispatch_result = agent.run_plan(dispatch_plan)
            if dispatch_result and dispatch_result.outputs:
                st.success("✅ Dispatch summary sent successfully!")
                success_count += 1
            else:
                st.error("❌ Dispatch summary failed")
            
            if success_count > 0:
                st.session_state.email_sent = True
                st.success(f"✅ {success_count}/{total_emails} Email notifications sent successfully!")
                
                # Display notification previews
                with st.expander("🏥 Hospital Notification Preview", expanded=False):
                    st.text(hospital_notification)
                    
                if gc and traffic_police_notification:
                    with st.expander("🚦 Traffic Police Green Corridor Preview", expanded=False):
                        st.text(traffic_police_notification)
                        
                with st.expander("🚑 Dispatch Summary Preview", expanded=False):
                    st.text(dispatch_notification)
                    
                return True
            else:
                st.error("❌ All email notifications failed")
                return False
                
        except Exception as e:
            st.error(f"Error sending three-email notifications: {str(e)}")
            return False

# Create and send dispatch summary
def create_and_send_dispatch():
    """Create comprehensive dispatch summary and send email"""
    if not st.session_state.approved_accidents:
        st.warning("No approved accidents to dispatch.")
        return
    
    with st.spinner("📧 Creating dispatch summary and sending alerts..."):
        try:
            # Create data objects
            detected_obj = DetectedAccidents(accidents=st.session_state.approved_accidents)
            pcs_obj = PCSResults(assessments=st.session_state.pcs_results)
            route_obj = RouteResults(routes=st.session_state.route_results)
            gc_obj = GreenCorridorResults(activations=st.session_state.green_corridor_results)
            notif_obj = NotificationResults(notifications=st.session_state.hospital_notifications)
            
            # Create dispatch summary
            dispatch_summary = create_dispatch_summary(
                detected_obj, pcs_obj, route_obj, gc_obj, notif_obj
            )
            
            st.session_state.dispatch_summary = dispatch_summary
            
            # Send three-email notifications if requested
            if st.session_state.get("send_dispatch_email", False):
                st.info("📧 Sending three-email notification system...")
                
                # Get the first approved accident and its route for email content
                accident = st.session_state.approved_accidents[0]
                route = st.session_state.route_results[0] if st.session_state.route_results else None
                pcs = st.session_state.pcs_results[0] if st.session_state.pcs_results else None
                gc = st.session_state.green_corridor_results[0] if st.session_state.green_corridor_results else None
                
                if not all([accident, route, pcs]):
                    st.error("Missing required data for email notifications")
                    return
                
                # Create three email notifications
                traffic_police_notification = create_traffic_police_email(route, pcs, gc) if gc else "Green corridor not activated"
                hospital_notification = create_hospital_bed_notification(route, pcs, accident)
                dispatch_notification = create_ambulance_dispatch_notification(route, pcs, accident, gc)
                
                # Configure agent with Cerebras
                cerebras_model = CerebrasModel()
                config = Config.from_default(
                    default_model=cerebras_model,
                    api_keys={
                        "portia": os.getenv("PORTIA_API_KEY"),
                        "cerebras": os.getenv("CEREBRAS_API_KEY")
                    }
                )
                
                agent = Portia(config=config)
                
                # Send emails sequentially
                success_count = 0
                total_emails = 2 + (1 if gc else 0)
                
                # 1. Send hospital notification first (most critical)
                st.info("🏥 Sending hospital bed preparation notification...")
                hospital_plan = (
                    PlanBuilderV2("Hospital Bed Preparation")
                    .invoke_tool_step(
                        step_name="hospital_email",
                        tool="portia:google:gmail:send_email",
                        args={
                            "recipients": [st.session_state.get("email_address", "anuju760@gmail.com")],
                            "email_title": "🏥 URGENT: INCOMING CRITICAL PATIENT - BED PREPARATION REQUIRED 🏥",
                            "email_body": hospital_notification
                        }
                    )
                    .final_output(output_schema=FinalDispatchResult)
                    .build()
                )
                
                hospital_result = agent.run_plan(hospital_plan)
                if hospital_result and hospital_result.outputs:
                    st.success("✅ Hospital notification sent successfully!")
                    success_count += 1
                else:
                    st.error("❌ Hospital notification failed")
                
                # 2. Send traffic police notification (if green corridor active)
                if gc:
                    st.info("🚦 Sending traffic police green corridor notification...")
                    traffic_plan = (
                        PlanBuilderV2("Traffic Police Green Corridor")
                        .invoke_tool_step(
                            step_name="traffic_email",
                            tool="portia:google:gmail:send_email",
                            args={
                                "recipients": [st.session_state.get("email_address", "anuju760@gmail.com")],
                                "email_title": "🚦 URGENT: GREEN CORRIDOR ACTIVATION - AMBULANCE PRIORITY REQUIRED",
                                "email_body": traffic_police_notification
                            }
                        )
                        .final_output(output_schema=FinalDispatchResult)
                        .build()
                    )
                    
                    traffic_result = agent.run_plan(traffic_plan)
                    if traffic_result and traffic_result.outputs:
                        st.success("✅ Traffic police notification sent successfully!")
                        success_count += 1
                    else:
                        st.error("❌ Traffic police notification failed")
                
                # 3. Send comprehensive dispatch summary
                st.info("🚑 Sending emergency dispatch summary...")
                dispatch_plan = (
                    PlanBuilderV2("Emergency Dispatch Summary")
                    .invoke_tool_step(
                        step_name="dispatch_email",
                        tool="portia:google:gmail:send_email",
                        args={
                            "recipients": [st.session_state.get("email_address", "anuju760@gmail.com")],
                            "email_title": "🚑 AMBULANCE EMERGENCY DISPATCH - CRITICAL INCIDENT RESPONSE 🚑",
                            "email_body": dispatch_notification
                        }
                    )
                    .final_output(output_schema=FinalDispatchResult)
                    .build()
                )
                
                dispatch_result = agent.run_plan(dispatch_plan)
                if dispatch_result and dispatch_result.outputs:
                    st.success("✅ Emergency dispatch summary sent successfully!")
                    success_count += 1
                else:
                    st.error("❌ Emergency dispatch summary failed")
                
                # Final status
                if success_count > 0:
                    st.session_state.email_sent = True
                    st.success(f"✅ {success_count}/{total_emails} Email notifications sent successfully!")
                    
                    # Display notification previews
                    with st.expander("🏥 Hospital Notification Preview", expanded=False):
                        st.text(hospital_notification)
                        
                    if gc and traffic_police_notification:
                        with st.expander("🚦 Traffic Police Green Corridor Preview", expanded=False):
                            st.text(traffic_police_notification)
                            
                    with st.expander("🚑 Emergency Dispatch Summary Preview", expanded=False):
                        st.text(dispatch_notification)
                else:
                    st.error("❌ All email notifications failed")
            
            st.success("✅ Dispatch summary created successfully!")
            
        except Exception as e:
            st.error(f"Error creating dispatch summary: {str(e)}")

# Header
st.title("🚑 LifeLine Green Corridor AI - Emergency Response Dashboard")
st.markdown("### Cerebras-Powered LLGCA Response System ")

# Sidebar for controls
with st.sidebar:
    st.header("🚑 Control Panel")
    
    st.subheader("Data Controls")
    email_input = st.text_input("Email for notifications:", value="anuju760@gmail.com")
    st.session_state.email_address = email_input
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔍 Fetch Real Data", type="primary"):
            accidents = fetch_accident_data()
            if accidents:
                st.success(f"✅ Found {len(accidents)} accidents!")
    
    # with col2:
    #     if st.button("🧪 Load Test Data"):
    #         st.session_state.detected_accidents = generate_mock_accidents()
    #         st.success("✅ Test data loaded!")
    
    # Reset Dashboard
    if st.button("🔄 Reset Dashboard"):
        for key in ["detected_accidents", "approved_accidents", "rejected_accidents", 
                   "pcs_results", "route_results", "green_corridor_results", 
                   "hospital_notifications", "dispatch_summary", "email_sent"]:
            st.session_state[key] = []
        st.session_state.dispatch_summary = ""
        st.session_state.email_sent = False
        st.success("🔄 All data cleared!")
    
    st.markdown("---")
    
    st.subheader("🚀 Quick Actions")
    
    if st.button("🧠 Calculate PCS", disabled=not st.session_state.approved_accidents):
        calculate_pcs_for_approved()
    
    if st.button("🛣️ Calculate Routes", disabled=not st.session_state.pcs_results):
        calculate_routes()
    
    if st.button("🚦 Activate Green Corridors", disabled=not st.session_state.route_results):
        activate_green_corridors()
    
    if st.button("🏥 Notify Hospitals", disabled=not st.session_state.route_results):
        send_hospital_notifications()
    
    st.markdown("---")
    
    st.subheader("📧 Dispatch Settings")
    st.session_state.send_dispatch_email = st.checkbox("Send 3-Email Notifications", value=True)
    
    if st.button("📤 Create & Send Dispatch", type="primary", disabled=not st.session_state.approved_accidents):
        create_and_send_dispatch()
    
    st.markdown("---")
    
    st.subheader("📊 System Stats")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("🚨 Pending", len(st.session_state.detected_accidents))
        st.metric("✅ Approved", len(st.session_state.approved_accidents))
        st.metric("📧 Emails Sent", "Yes" if st.session_state.email_sent else "No")
    with col2:
        st.metric("❌ Rejected", len(st.session_state.rejected_accidents))
        st.metric("🚦 Green Corridors", len(st.session_state.green_corridor_results))
        st.metric("🏥 Hospitals", len(st.session_state.hospital_notifications))

# Create tabs for different views
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🗺️ Map View", 
    "🚨 Accident Detection", 
    "🧠 PCS Assessment", 
    "🛣️ Route Optimization", 
    "🚦 Green Corridors",
    "📧 Dispatch Summary"
])

# Tab 1: Map View
with tab1:
    st.subheader("🗺️ Ambulance Green Corridor Map")
    
    if not (st.session_state.detected_accidents or st.session_state.approved_accidents or st.session_state.rejected_accidents):
        st.info("🔍 No accidents loaded. Use the sidebar to fetch real data or load test data to get started.")
    else:
        # Show current incident focus information
        total_incidents = len(st.session_state.detected_accidents) + len(st.session_state.approved_accidents) + len(st.session_state.rejected_accidents)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🎯 Map Focus", f"{total_incidents} Incidents")
        with col2:
            if st.session_state.approved_accidents:
                active_routes = len([r for r in st.session_state.route_results])
                st.metric("🛣️ Active Routes", active_routes)
        with col3:
            if st.session_state.green_corridor_results:
                st.metric("🚦 Green Corridors", len(st.session_state.green_corridor_results))
        
        # Create and display map
        ambulance_map = create_ambulance_map()
        folium_static(ambulance_map, width=1200, height=600)
        
        st.info("🎯 Map automatically focuses on incident locations with optimal zoom level for best visibility.")
        
        # Add comprehensive legend
        st.markdown("""
        ### 🎯 Enhanced Map Legend:
        
        **🚨 Accident Markers:**
        - **🚑 Dark Red**: Critical PCS (8-10) - Immediate Green Corridor Priority
        - **🚑 Red**: High PCS (6-7) - Green Corridor Recommended  
        - **🚑 Orange**: Moderate PCS (4-5) - Expedited Route
        - **🚑 Light Red/Green**: Low PCS (0-3) - Normal Route Priority
        - **✅ Green Check**: Approved & Dispatched
        - **❌ Gray X**: Rejected Accident
        
        **🛣️ Route Visualization:**
        - **Thick Colored Lines**: Complete ambulance route (accident → hospital)
        - **White/Black Borders**: Enhanced route visibility
        - **🚑 Start Marker**: Ambulance departure point
        - **🏥 End Marker**: Hospital destination
        - **➤ Direction Arrows**: Route direction indicators
        - **Small Circles**: Route waypoints for complete path visibility
        
        **🏥 Hospital & Coverage:**
        - **🏥 Red Plus**: Level 1 Trauma Center
        - **🏥 Orange Plus**: Level 2+ Trauma Center  
        - **Large Circles**: Hospital service coverage areas
        - **Dashed Lines**: Direct accident-to-hospital connection
        
        **🚦 Green Corridor Status:**
        - **Solid Thick Lines**: Green Corridor Active Routes
        - **Normal Lines**: Standard Priority Routes
        - **Green Circles**: Active emergency response zones
        - **Blue Circles**: Pending approval zones
        """)

# Tab 2: Accident Detection & Approval
with tab2:
    st.subheader("🚨 Accident Detection & Human Approval")
    
    if not st.session_state.detected_accidents:
        st.info("🔍 No pending accidents. Fetch accident data from the sidebar.")
    else:
        st.success(f"🔍 Found {len(st.session_state.detected_accidents)} potential accidents requiring review")
        
        # Sort by confidence score (highest first)
        sorted_accidents = sorted(
            st.session_state.detected_accidents,
            key=lambda a: a.confidence_score,
            reverse=True
        )
        
        for i, accident in enumerate(sorted_accidents):
            with st.container():
                col1, col2 = st.columns([3, 1])
                
                # Accident details
                with col1:
                    confidence_color = "green" if accident.confidence_score >= 0.9 else "orange" if accident.confidence_score >= 0.7 else "red"
                    st.markdown(f"### 🚨 {accident.id}")
                    st.markdown(f"**Confidence:** <span style='color:{confidence_color};font-weight:bold;'>{accident.confidence_score:.2f}</span>", unsafe_allow_html=True)
                    st.markdown(f"**📍 Location:** {accident.location}")
                    st.markdown(f"**🗺️ GPS:** {accident.gps_lat}, {accident.gps_lon}")
                    st.markdown(f"**⏰ Time:** {accident.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    st.markdown(f"**⚠️ Severity Indicators:** {', '.join(accident.severity_indicators)}")
                    st.markdown(f"**📰 Sources:** {', '.join(accident.news_sources)}")
                    st.markdown(f"**📝 Description:** {accident.description}")
                    st.markdown(f"[🎯 View on Google Maps](https://maps.google.com/?q={accident.gps_lat},{accident.gps_lon})")
                
                # Approval/Rejection controls
                with col2:
                    st.markdown("#### 🚑 Deploy Ambulance?")
                    
                    if st.button(f"✅ APPROVE", key=f"approve_{i}", use_container_width=True, type="primary"):
                        approve_accident(accident)
                        st.rerun()
                    
                    rejection_reason = st.text_input(
                        "Rejection reason:", 
                        key=f"reason_{i}", 
                        placeholder="Required for rejection"
                    )
                    
                    if st.button(f"❌ REJECT", key=f"reject_{i}", disabled=not rejection_reason, use_container_width=True):
                        reject_accident(accident, rejection_reason)
                        st.rerun()
                
                st.markdown("---")

# Tab 3: PCS Assessment
with tab3:
    st.subheader("🧠 Patient Critical Score (PCS) Assessment")
    
    if not st.session_state.approved_accidents:
        st.info("🚑 No approved accidents for PCS assessment.")
    elif not st.session_state.pcs_results:
        st.info("📊 Click 'Calculate PCS' in the sidebar to assess accident severity.")
    else:
        st.success(f"🧠 PCS Assessment completed for {len(st.session_state.pcs_results)} accidents")
        
        # Display PCS results in a table
        pcs_data = []
        for pcs in st.session_state.pcs_results:
            # Find corresponding accident
            accident = None
            for acc in st.session_state.approved_accidents:
                if acc.id == pcs.accident_id:
                    accident = acc
                    break
            
            pcs_data.append({
                "Accident ID": pcs.accident_id,
                "Location": accident.location if accident else "Unknown",
                "PCS Score": f"{pcs.patient_critical_score}/10",
                "Severity": pcs.severity_level.value.upper(),
                "Recommendation": pcs.recommendation,
                "Est. Patients": pcs.estimated_patients,
                "Priority": pcs.priority_level
            })
        
        if pcs_data:
            pcs_df = pd.DataFrame(pcs_data)
            st.dataframe(pcs_df, use_container_width=True)
            
        # Show detailed breakdown
        with st.expander("📋 Detailed PCS Breakdown"):
            for pcs in st.session_state.pcs_results:
                st.markdown(f"### {pcs.accident_id}")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("PCS Score", f"{pcs.patient_critical_score}/10")
                with col2:
                    st.metric("Severity", pcs.severity_level.value.upper())
                with col3:
                    st.metric("Estimated Patients", pcs.estimated_patients)
                
                st.markdown("**Score Breakdown:**")
                for factor, score in pcs.score_breakdown.items():
                    st.markdown(f"- {factor.replace('_', ' ').title()}: +{score} points")
                
                st.markdown(f"**Recommendation:** {pcs.recommendation}")
                st.markdown("---")

# Tab 4: Route Optimization
with tab4:
    st.subheader("🛣️ Route Optimization & ETA Prediction")
    
    if not st.session_state.route_results:
        st.info("🛣️ No route calculations available. Complete PCS assessment first.")
    else:
        st.success(f"🛣️ Route optimization completed for {len(st.session_state.route_results)} ambulances")
        
        # Summary metrics
        total_time_saved = sum(route.time_saved_minutes for route in st.session_state.route_results)
        avg_distance = sum(route.distance_km for route in st.session_state.route_results) / len(st.session_state.route_results)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🕒 Total Time Saved", f"{total_time_saved} minutes")
        with col2:
            st.metric("📏 Avg Distance", f"{avg_distance:.1f} km")
        with col3:
            st.metric("🚑 Ambulances", len(st.session_state.route_results))
        
        # Route details table
        route_data = []
        for route in st.session_state.route_results:
            route_data.append({
                "Ambulance ID": route.ambulance_id,
                "Accident ID": route.accident_id,
                "Target Hospital": route.target_hospital.name,
                "Distance (km)": route.distance_km,
                "Normal ETA (min)": route.estimated_time_normal,
                "Green Corridor ETA (min)": route.estimated_time_green_corridor,
                "Time Saved (min)": route.time_saved_minutes,
                "Traffic Signals": route.traffic_intersections
            })
        
        if route_data:
            route_df = pd.DataFrame(route_data)
            st.dataframe(route_df, use_container_width=True)
        
        # Hospital details
        with st.expander("🏥 Hospital Information"):
            for route in st.session_state.route_results:
                hospital = route.target_hospital
                st.markdown(f"### {hospital.name}")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Trauma Level", hospital.trauma_level)
                with col2:
                    st.metric("Available Beds", hospital.available_beds)
                with col3:
                    st.metric("Distance", f"{hospital.distance_km:.1f} km")
                
                st.markdown(f"**Specialties:** {', '.join(hospital.specialties)}")
                st.markdown(f"**Location:** {hospital.location}")
                st.markdown("---")

# Tab 5: Green Corridors
with tab5:
    st.subheader("🚦 Green Corridor Management")
    
    if not st.session_state.green_corridor_results:
        st.info("🚦 No green corridors activated. Complete route optimization first.")
    else:
        st.success(f"🚦 {len(st.session_state.green_corridor_results)} Green Corridors activated")
        
        # Summary metrics
        total_intersections = sum(gc.total_intersections for gc in st.session_state.green_corridor_results)
        total_time_saved_gc = sum(gc.estimated_time_saved for gc in st.session_state.green_corridor_results)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🚦 Traffic Signals Controlled", total_intersections)
        with col2:
            st.metric("⏱️ Total Time Saved", f"{total_time_saved_gc} minutes")
        with col3:
            st.metric("🟢 Active Corridors", len(st.session_state.green_corridor_results))
        
        # Green corridor details
        for gc in st.session_state.green_corridor_results:
            with st.expander(f"🚦 Green Corridor: {gc.green_corridor_id}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**Ambulance ID:** {gc.ambulance_id}")
                    st.markdown(f"**Accident ID:** {gc.accident_id}")
                    st.markdown(f"**Status:** {gc.status.value.upper()}")
                    st.markdown(f"**Activation Time:** {gc.activation_time.strftime('%H:%M:%S')}")
                
                with col2:
                    st.markdown(f"**Total Intersections:** {gc.total_intersections}")
                    st.markdown(f"**Time Saved:** {gc.estimated_time_saved} minutes")
                
                # Traffic intersections
                if gc.affected_intersections:
                    st.markdown("**Traffic Intersections:**")
                    intersection_data = []
                    for intersection in gc.affected_intersections[:5]:  # Show first 5
                        intersection_data.append({
                            "Intersection ID": intersection.intersection_id,
                            "Status": intersection.signal_status,
                            "Activation": intersection.activation_time.strftime('%H:%M:%S'),
                            "Passage": intersection.estimated_passage_time.strftime('%H:%M:%S')
                        })
                    
                    if intersection_data:
                        int_df = pd.DataFrame(intersection_data)
                        st.dataframe(int_df, use_container_width=True)

# Tab 6: Dispatch Summary
with tab6:
    st.subheader("📧 Emergency Dispatch Summary")
    
    if not st.session_state.dispatch_summary:
        st.info("📧 No dispatch summary available. Complete the full workflow and click 'Create & Send Dispatch'.")
    else:
        # Show dispatch status
        col1, col2 = st.columns(2)
        with col1:
            st.success("✅ Dispatch Summary Created")
        with col2:
            if st.session_state.email_sent:
                st.success("📧 Email Sent Successfully")
            else:
                st.info("📧 Email Not Sent")
        
        # Show summary content
        st.markdown("### 📋 Dispatch Summary Content")
        st.text_area(
            "Dispatch Summary",
            st.session_state.dispatch_summary,
            height=500,
            help="This summary will be sent to emergency coordinators and hospital staff."
        )
        
        # Approved accidents summary
        if st.session_state.approved_accidents:
            st.markdown("### ✅ Approved Accidents Summary")
            summary_data = []
            for accident in st.session_state.approved_accidents:
                # Find PCS and route data
                pcs = next((p for p in st.session_state.pcs_results if p.accident_id == accident.id), None)
                route = next((r for r in st.session_state.route_results if r.accident_id == accident.id), None)
                
                summary_data.append({
                    "Accident ID": accident.id,
                    "Location": accident.location,
                    "PCS Score": f"{pcs.patient_critical_score}/10" if pcs else "N/A",
                    "Ambulance": route.ambulance_id if route else "N/A",
                    "Hospital": route.target_hospital.name if route else "N/A",
                    "ETA (Green Corridor)": f"{route.estimated_time_green_corridor} min" if route else "N/A",
                    "Time Saved": f"{route.time_saved_minutes} min" if route else "N/A"
                })
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("### 🚑 System Status")

# System status indicators
col1, col2, col3, col4 = st.columns(4)

with col1:
    status = "🟢 OPERATIONAL" if st.session_state.detected_accidents else "🟡 STANDBY"
    st.markdown(f"**Detection:** {status}")

with col2:
    status = "🟢 ACTIVE" if st.session_state.pcs_results else "🟡 WAITING"
    st.markdown(f"**PCS Analysis:** {status}")

with col3:
    status = "🟢 ACTIVE" if st.session_state.green_corridor_results else "🟡 INACTIVE"
    st.markdown(f"**Green Corridors:** {status}")

with col4:
    status = "🟢 SENT" if st.session_state.email_sent else "🟡 PENDING"
    st.markdown(f"**Dispatch:** {status}")

st.caption(f"🚑 LifeLine Green Corridor Dashboard v1.0 | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("Powered by 🧠 Cerebras Inference LLaMA + Portia AI for Orchestration")

