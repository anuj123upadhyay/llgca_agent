# Ambulance Green Corridor AI

An intelligent emergency response system that creates priority traffic routes for ambulances using AI-powered accident detection and patient assessment.

## System Overview

This system implements a 5-step workflow:
1. **Accident Detection** - Tavily News Search + AI Analysis
2. **Patient Critical Score Assessment** - AI-powered severity scoring
3. **Route Optimization** - Real-time traffic analysis with Cerebras AI
4. **Green Corridor Coordination** - Traffic signal control via SUMO
5. **Hospital Readiness Notification** - FHIR API integration

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Setup**:
   ```bash
   cp .env.example .env
   # Add your API keys to .env file
   ```

3. **Run the System**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

4. **Access API Documentation**:
   - OpenAPI Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Endpoints

- `POST /api/v1/emergency/detect` - Manual accident reporting
- `GET /api/v1/emergency/status/{accident_id}` - Get emergency status
- `POST /api/v1/emergency/start-monitoring` - Start news monitoring
- `GET /api/v1/emergency/active` - List active emergencies

## Configuration

All configuration is handled through environment variables in `.env`:
- API keys for Tavily, OpenAI, Google Maps
- Database connections
- Redis configuration
- Hospital and traffic system endpoints

## Architecture

The system uses:
- **FastAPI** for REST API
- **SQLAlchemy** for database ORM
- **Redis** for caching and real-time data
- **Celery** for background tasks
- **WebSocket** for real-time updates