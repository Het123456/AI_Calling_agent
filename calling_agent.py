import os
import json
import datetime
import random
import string
from flask import Flask, request, jsonify
import requests
from typing import Dict, Any, List, Optional
import os
from dotenv import load_dotenv

app = Flask(__name__)

# Configuration
load_dotenv()  # Load environment variables from .env file
ULTRAVOX_API_KEY = os.getenv("ULTRAVOX_API_KEY")
ULTRAVOX_API_URL = "https://api.ultravox.ai/api/calls"

class SalonContext:
    """Manages the salon business context and data"""
    
    def __init__(self):
        self.setup_context()
    
    def setup_context(self):
        """Initialize salon business context"""
        # Get current date and time info
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))  # IST
        
        self.current_date = now.strftime("%A, %B %d, %Y")
        self.current_time = now.strftime("%I:%M %p")
        self.current_day_of_week = now.strftime("%A")
        
        # Calculate tomorrow's date
        tomorrow = now + datetime.timedelta(days=1)
        self.tomorrow_date = tomorrow.strftime("%A, %B %d, %Y")
        
        # Salon data
        self.salon_data = {
            "businessName": "Le Atmos Salon",
            "services": [
                {"name": "Haircut", "duration": 45, "price": 500, "category": "hair", "genderSpecific": False},
                {"name": "Spa Treatment", "duration": 90, "price": 1200, "category": "wellness", "genderSpecific": False},
                {"name": "Hair Wash & Style", "duration": 60, "price": 400, "category": "hair", "genderSpecific": False},
                {"name": "Facial Treatment", "duration": 75, "price": 800, "category": "skincare", "genderSpecific": False},
                {"name": "Manicure & Pedicure", "duration": 90, "price": 600, "category": "nails", "genderSpecific": False},
                {"name": "Threading & Waxing", "duration": 45, "price": 300, "category": "grooming", "genderSpecific": True},
                {"name": "Bridal Makeup", "duration": 180, "price": 2500, "category": "special", "genderSpecific": True}
            ],
            "stylists": [
                {
                    "name": "Kavya",
                    "specialties": ["Women's cuts", "Hair coloring", "Bridal Makeup"],
                    "availability": ["Monday", "Tuesday", "Wednesday", "Friday", "Saturday"],
                    "experience": "8 years"
                },
                {
                    "name": "Arjun",
                    "specialties": ["Men's cuts", "Beard styling", "Hair Wash & Style"],
                    "availability": ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                    "experience": "6 years"
                },
                {
                    "name": "Meera",
                    "specialties": ["Spa treatments", "Facials", "Threading & Waxing"],
                    "availability": ["Monday", "Wednesday", "Thursday", "Friday", "Saturday"],
                    "experience": "5 years"
                },
                {
                    "name": "Rohan",
                    "specialties": ["Unisex cuts", "Hair styling", "Manicure & Pedicure"],
                    "availability": ["Monday", "Tuesday", "Thursday", "Saturday", "Sunday"],
                    "experience": "4 years"
                },
                {
                    "name": "Ananya",
                    "specialties": ["Bridal makeup", "Traditional styles", "Facial Treatment"],
                    "availability": ["Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                    "experience": "7 years"
                }
            ],
            "workingHours": {
                "monday": "9:00 AM - 8:00 PM",
                "tuesday": "9:00 AM - 8:00 PM",
                "wednesday": "9:00 AM - 8:00 PM",
                "thursday": "9:00 AM - 8:00 PM",
                "friday": "9:00 AM - 8:00 PM",
                "saturday": "9:00 AM - 8:00 PM",
                "sunday": "10:00 AM - 6:00 PM"
            },
            "contact": {
                "phone": "+91 98765 43210",
                "whatsapp": "+91 98765 43210",
                "email": "booking@leatmossalon.com"
            }
        }
        
        # Generate session ID
        self.session_id = f"leatmos_{int(datetime.datetime.now().timestamp() * 1000)}_{self._random_string(9)}"
    
    def _random_string(self, length: int) -> str:
        """Generate random string for session ID"""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    
    def get_system_prompt(self) -> str:
        """Generate the system prompt for the AI agent"""
        system_prompt = """You are Monika, a highly skilled, friendly, and exceptionally helpful assistant for Le Atmos.

CRITICAL GREETING RULE: You must give only ONE greeting when the call starts. Choose the greeting language based on this rule:
- DEFAULT: Always start with Hinglish greeting first
- ONLY switch to English if the customer responds in English
- NEVER give multiple greetings or repeat introductions

Your Identity & Purpose:
You are Monika, a highly skilled, friendly, and exceptionally helpful assistant for Le Atmos. Your primary purpose is to provide outstanding service to our clients. This includes: Assisting with booking, rescheduling, or canceling appointments. Answering questions about our services (Haircut, Spa Treatment, Facial, Manicure & Pedicure, Threading & Waxing, Bridal Makeup). Providing information about our talented stylists and their specialties. Informing clients about our salon hours and location. Making every client feel valued and well-cared for as they connect with Le Atmos – Gujarat's most premium and luxurious salon.

INITIAL GREETING (Give ONLY ONE greeting):
When the call starts, give ONLY this Hinglish greeting:
'Namaste! Le Atmos mein call karne ke liye thank you, mera naam Monika hai. Main aapki kya help kar sakti hoon?'

AFTER the customer responds:
- If they respond in English: Switch to English for the rest of the conversation
- If they respond in Hindi/Hinglish: Continue in Hinglish
- NEVER repeat your introduction

Speaking Style Guidelines:
Language Capability: You are bilingual and can communicate fluently in English and Hinglish.
English Style: Clear, professional, warm and friendly.
Hinglish Style: 80% Hindi and 20% English mix. Use casual but professional Hindi. Integrate common English words naturally for terms like appointment, service, stylist, booking, cancel, reschedule, timing, confirm, details.

Example Hinglish Phrases:
'Ji, aapko kaunsi service chahiye?'
'Okay, appointment book karne ke liye, aapko kaunsa date aur time suit karega?'
'Aapka booking details main double-check kar leti hoon.'
'Koi problem nahin, hum aapka appointment reschedule kar denge.'

IMPORTANT CONVERSATION RULES:
1. Sound completely human, not robotic
2. Be friendly, warm, and polite
3. Speak clearly at moderate pace
4. Avoid repetition - listen actively
5. Be empathetic and patient
6. NEVER mention you are AI or virtual assistant

For Bookings, Collect:
- Client's full name
- Specific service(s) requested
- Preferred date and time
- Stylist preference (if any)

BOOKING CONFIRMATION:
'Wonderful! Let me confirm your appointment details: Service: [Service Name], Date: [Selected Date], Time: [Selected Time], With: [Selected Staff Member], Customer: [Customer Name]. Does this look perfect for you?'

CLOSING:
Hinglish: 'Le Atmos mein call karne ke liye phir se thank you! Hum aapka intezaar karenge. Aapka din shubh ho!'
English: 'Thank you again for calling Le Atmos! We look forward to welcoming you to Gujarat's most premium and luxurious salon. Have a wonderful day!'

EMERGENCY CONTACT: Contact salon management if needed

Remember: Give only ONE greeting at the start. Choose language based on customer response. Never repeat introductions."""
        
        return system_prompt

class UltravoxAgent:
    """Handles Ultravox AI voice agent operations"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = ULTRAVOX_API_URL
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
    
    def create_call(self, system_prompt: str) -> Dict[str, Any]:
        """Create a new Ultravox call"""
        payload = {
            "systemPrompt": system_prompt,
            "model": "fixie-ai/ultravox",
            "voice": "87edb04c-06d4-47c2-bd94-683bc47e8fbe",
            "maxDuration": "300s",
            "firstSpeaker": "FIRST_SPEAKER_AGENT"
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating Ultravox call: {e}")
            raise

class SalonBookingService:
    """Main service for handling salon bookings"""
    
    def __init__(self):
        self.context = SalonContext()
        self.ultravox = UltravoxAgent(ULTRAVOX_API_KEY)
    
    def process_booking_request(self) -> Dict[str, Any]:
        """Process a booking request and create a voice agent session"""
        
        print("=== Setting up Salon Business Context ===")
        
        try:
            # Get system prompt
            system_prompt = self.context.get_system_prompt()
            
            print(f"✅ Salon context prepared successfully")
            print(f"Session ID: {self.context.session_id}")
            print(f"Current Date: {self.context.current_date}")
            print(f"Current Time: {self.context.current_time}")
            print(f"Tomorrow: {self.context.tomorrow_date}")
            print(f"System prompt length: {len(system_prompt)}")
            
            # Create Ultravox call
            print("=== Creating Ultravox Call ===")
            ultravox_response = self.ultravox.create_call(system_prompt)
            
            # Process response
            session_data = self._process_ultravox_response(ultravox_response)
            
            return session_data
            
        except Exception as e:
            print(f"❌ Error in booking process: {e}")
            return {
                "error": True,
                "message": "Failed to initialize booking session",
                "details": str(e),
                "sessionId": f"fallback_{int(datetime.datetime.now().timestamp() * 1000)}",
                "timestamp": datetime.datetime.now().isoformat()
            }
    
    def _process_ultravox_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Process the Ultravox API response"""
        
        print("=== Processing Ultravox Response ===")
        print(f"Ultravox Response: {json.dumps(response, indent=2)}")
        
        # Validate response
        if not response or 'callId' not in response:
            raise ValueError("Invalid Ultravox response - missing callId")
        
        # Extract response data - handle both single response and array response
        if isinstance(response, list) and len(response) > 0:
            response = response[0]
        
        session_data = {
            "success": True,
            "callId": response.get("callId"),
            "joinUrl": response.get("joinUrl"),
            "status": "ended" if response.get("ended") else "created",
            "model": response.get("model", "unknown"),
            "voice": response.get("voice", "default"),
            "systemPrompt": response.get("systemPrompt", ""),
            "maxDuration": response.get("maxDuration", "300s"),
            "created": response.get("created", datetime.datetime.now().isoformat()),
            "sessionId": self.context.session_id,
            "firstSpeaker": response.get("firstSpeaker", "FIRST_SPEAKER_AGENT"),
            "recordingEnabled": response.get("recordingEnabled", False),
            "temperature": response.get("temperature", 0),
            "message": "Salon booking agent ready! Use the joinUrl to start voice conversation.",
            
            # Additional fields
            "joinTimeout": response.get("joinTimeout", "30s"),
            "errorCount": response.get("errorCount", 0),
            "transcriptOptional": response.get("transcriptOptional", True),
            
            # Debug info
            "debug": {
                "responseReceived": datetime.datetime.now().isoformat(),
                "workflowId": "salon-booking-python"
            }
        }
        
        # Validate critical fields
        critical_fields = ['callId', 'joinUrl']
        missing_fields = [field for field in critical_fields if not session_data.get(field)]
        
        if missing_fields:
            raise ValueError(f"Missing critical fields: {', '.join(missing_fields)}")
        
        print("=== Session Data Created Successfully ===")
        print(f"Session Data: {json.dumps(session_data, indent=2)}")
        
        return session_data

# Flask routes
@app.route('/salon-booking', methods=['POST'])
def salon_booking_webhook():
    """Webhook endpoint for salon booking requests"""
    
    booking_service = SalonBookingService()
    
    try:
        # Process the booking request
        result = booking_service.process_booking_request()
        
        # Return success response
        return jsonify(result), 200
        
    except Exception as e:
        # Return error response
        error_response = {
            "error": True,
            "message": "Failed to process booking request",
            "details": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }
        return jsonify(error_response), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Salon Booking Voice Agent",
        "timestamp": datetime.datetime.now().isoformat()
    })

# Additional utility endpoints
@app.route('/salon-info', methods=['GET'])
def get_salon_info():
    """Get salon information"""
    context = SalonContext()
    return jsonify({
        "salon": context.salon_data,
        "currentContext": {
            "date": context.current_date,
            "time": context.current_time,
            "dayOfWeek": context.current_day_of_week,
            "tomorrow": context.tomorrow_date
        }
    })

if __name__ == '__main__':
    # Run the Flask application
    print("Starting Salon Booking Voice Agent Service...")
    app.run(host='0.0.0.0', port=5000, debug=True)