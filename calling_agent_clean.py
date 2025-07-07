import os
import json
import sqlite3
import datetime
import pytz
import random
import string
import requests
from typing import Dict, Any, List, Optional, Tuple
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()
ULTRAVOX_API_KEY = os.getenv("ULTRAVOX_API_KEY")
ULTRAVOX_API_URL = "https://api.ultravox.ai/api/calls"

# Google Calendar configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']
GOOGLE_CREDENTIALS_FILE = 'credentials.json'
GOOGLE_TOKEN_FILE = 'token.json'

# Stylist Calendar IDs - UPDATE THESE WITH YOUR ACTUAL CALENDAR IDs
STYLIST_CALENDAR_IDS = {
    'Kavya': 'dc9d357c0ea27a4f13aa8b25029cd7d15c57a189120abc0fa835fad1647f7dd1@group.calendar.google.com',
    'Arjun': '920e6d90a85697b00d8ed6108a4eadc1d325458eb24af758d7adcea4f45570b1@group.calendar.google.com',
    'Meera': '9132a369232f0cbd2e4b851f434d8c57bf61434ade61d35b75532a64abb33f36@group.calendar.google.com',
    'Rohan': 'bf286a774c895afd9a2d1060078cbc13a1fe3105896415a7b8d13033f71dfb29@group.calendar.google.com',
    'Ananya': '2d8eaeaed01a4ff27079d9aa33cd637dbf824e40d1e123b46094c766c3d7b545@group.calendar.google.com'
}

# India Standard Time
IST = pytz.timezone('Asia/Kolkata')


class DatabaseManager:
    """Enhanced database manager with full CRUD operations"""
    
    def __init__(self, db_path: str = "salon_appointments.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with comprehensive schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create appointments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                customer_phone TEXT,
                customer_email TEXT,
                stylist_name TEXT NOT NULL,
                service_name TEXT NOT NULL,
                service_duration INTEGER NOT NULL,
                service_price REAL NOT NULL,
                appointment_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                status TEXT DEFAULT 'confirmed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                google_calendar_event_id TEXT,
                session_id TEXT,
                notes TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create services table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                duration INTEGER NOT NULL,
                price REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                gender_specific INTEGER DEFAULT 0
            )
        ''')
        
        # Create stylists table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stylists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                specialties TEXT NOT NULL,
                availability TEXT NOT NULL,
                experience TEXT,
                rating REAL DEFAULT 5.0,
                google_calendar_id TEXT
            )
        ''')
        
        # Create analytics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
    
    def add_appointment(self, appointment_data: Dict[str, Any]) -> int:
        """Add new appointment and return appointment ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO appointments (
                customer_name, customer_phone, customer_email, stylist_name,
                service_name, service_duration, service_price, appointment_date,
                start_time, end_time, google_calendar_event_id, session_id, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            appointment_data['customer_name'],
            appointment_data.get('customer_phone'),
            appointment_data.get('customer_email'),
            appointment_data['stylist_name'],
            appointment_data['service_name'],
            appointment_data['service_duration'],
            appointment_data['service_price'],
            appointment_data['appointment_date'],
            appointment_data['start_time'],
            appointment_data['end_time'],
            appointment_data.get('google_calendar_event_id'),
            appointment_data.get('session_id'),
            appointment_data.get('notes')
        ))
        
        appointment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return appointment_id
    
    def check_availability(self, stylist_name: str, date: str, time: str, duration: int) -> bool:
        """Check if stylist is available at given time"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Convert time to check for overlaps
        start_time = datetime.datetime.strptime(time, '%H:%M').time()
        end_time = (datetime.datetime.combine(datetime.date.today(), start_time) + 
                   datetime.timedelta(minutes=duration)).time()
        
        cursor.execute('''
            SELECT COUNT(*) FROM appointments 
            WHERE stylist_name = ? AND appointment_date = ? 
            AND status = 'confirmed'
            AND (
                (start_time <= ? AND end_time > ?) OR
                (start_time < ? AND end_time >= ?) OR
                (start_time >= ? AND start_time < ?)
            )
        ''', (stylist_name, date, time, time, end_time.strftime('%H:%M'), 
              end_time.strftime('%H:%M'), time, end_time.strftime('%H:%M')))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count == 0
    
    def get_appointments(self, date: str = None, stylist_name: str = None) -> List[Dict[str, Any]]:
        """Get appointments with optional filters"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM appointments WHERE status = 'confirmed'"
        params = []
        
        if date:
            query += " AND appointment_date = ?"
            params.append(date)
        
        if stylist_name:
            query += " AND stylist_name = ?"
            params.append(stylist_name)
        
        query += " ORDER BY appointment_date, start_time"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        columns = [description[0] for description in cursor.description]
        appointments = [dict(zip(columns, row)) for row in rows]
        
        conn.close()
        return appointments
    
    def get_service_details(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service details by name"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM services WHERE name = ?", (service_name,))
        row = cursor.fetchone()
        
        if row:
            columns = [description[0] for description in cursor.description]
            service = dict(zip(columns, row))
            conn.close()
            return service
        
        conn.close()
        return None
    
    def get_all_services(self) -> List[Dict[str, Any]]:
        """Get all available services"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM services ORDER BY category, name")
        rows = cursor.fetchall()
        
        columns = [description[0] for description in cursor.description]
        services = [dict(zip(columns, row)) for row in rows]
        
        conn.close()
        return services
    
    def get_all_stylists(self) -> List[Dict[str, Any]]:
        """Get all stylists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM stylists ORDER BY name")
        rows = cursor.fetchall()
        
        columns = [description[0] for description in cursor.description]
        stylists = [dict(zip(columns, row)) for row in rows]
        
        conn.close()
        return stylists


class GoogleCalendarManager:
    """Enhanced Google Calendar integration"""
    
    def __init__(self):
        self.service = None
        self.setup_calendar_service()
    
    def setup_calendar_service(self):
        """Setup Google Calendar API service"""
        try:
            creds = None
            
            # Load existing token
            if os.path.exists(GOOGLE_TOKEN_FILE):
                creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, SCOPES)
            
            # If no valid credentials, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if os.path.exists(GOOGLE_CREDENTIALS_FILE):
                        flow = InstalledAppFlow.from_client_secrets_file(
                            GOOGLE_CREDENTIALS_FILE, SCOPES)
                        creds = flow.run_local_server(port=0)
                    else:
                        print("⚠️  Google credentials file not found. Calendar integration disabled.")
                        return
                
                # Save credentials for next run
                with open(GOOGLE_TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
            
            self.service = build('calendar', 'v3', credentials=creds)
            print("✅ Google Calendar service initialized")
            
        except Exception as e:
            print(f"⚠️  Could not initialize Google Calendar service: {e}")
            self.service = None
    
    def check_availability(self, calendar_id: str, start_time: str, end_time: str) -> bool:
        """Check if calendar is free at given time"""
        if not self.service:
            return True  # If no calendar service, assume available
        
        try:
            # Query for events in the time range
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return len(events) == 0  # Available if no events found
            
        except HttpError as e:
            print(f"Calendar check error: {e}")
            return True  # Assume available on error
    
    def create_event(self, calendar_id: str, event_details: Dict[str, Any]) -> Optional[str]:
        """Create calendar event and return event ID"""
        if not self.service:
            return None
        
        try:
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_details
            ).execute()
            
            return event.get('id')
            
        except HttpError as e:
            print(f"Calendar event creation error: {e}")
            return None
    
    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """Delete calendar event"""
        if not self.service or not event_id:
            return False
        
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return True
            
        except HttpError as e:
            print(f"Calendar event deletion error: {e}")
            return False


class DateTimeValidator:
    """Enhanced date/time validation with intelligent suggestions"""
    
    def __init__(self):
        self.ist = pytz.timezone('Asia/Kolkata')
        self.business_hours = {
            'start': 9,   # 9 AM
            'end': 20     # 8 PM
        }
        self.working_days = [0, 1, 2, 3, 4, 5]  # Monday to Saturday
    
    def get_current_ist_time(self) -> datetime.datetime:
        """Get current IST time"""
        return datetime.datetime.now(self.ist)
    
    def validate_appointment_time(self, date_str: str, time_str: str) -> Dict[str, Any]:
        """Comprehensive date/time validation"""
        errors = []
        
        try:
            # Parse date
            appointment_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            current_date = self.get_current_ist_time().date()
            
            # Check if date is in the past
            if appointment_date < current_date:
                errors.append("Cannot book appointments in the past")
            
            # Check if date is too far in future (3 months)
            max_date = current_date + datetime.timedelta(days=90)
            if appointment_date > max_date:
                errors.append("Cannot book appointments more than 3 months in advance")
            
            # Check if it's a working day
            if appointment_date.weekday() not in self.working_days:
                errors.append("We are closed on Sundays")
            
            # Parse time
            appointment_time = datetime.datetime.strptime(time_str, '%H:%M').time()
            
            # Check business hours
            if (appointment_time.hour < self.business_hours['start'] or 
                appointment_time.hour >= self.business_hours['end']):
                errors.append(f"Business hours are {self.business_hours['start']}:00 AM to {self.business_hours['end']}:00 PM")
            
            # For today, check if time has passed
            if appointment_date == current_date:
                current_time = self.get_current_ist_time().time()
                if appointment_time <= current_time:
                    errors.append("Cannot book appointments in the past")
            
            # Create appointment datetime
            appointment_datetime = datetime.datetime.combine(appointment_date, appointment_time)
            appointment_datetime = self.ist.localize(appointment_datetime)
            
            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'appointment_datetime': appointment_datetime,
                'formatted_date': appointment_date.strftime('%A, %B %d, %Y'),
                'formatted_time': appointment_time.strftime('%I:%M %p')
            }
            
        except ValueError as e:
            errors.append(f"Invalid date/time format: {str(e)}")
            return {
                'valid': False,
                'errors': errors,
                'appointment_datetime': None,
                'formatted_date': None,
                'formatted_time': None
            }
    
    def suggest_next_available_slots(self, date_str: str, duration: int = 60) -> List[Dict[str, str]]:
        """Suggest next available time slots"""
        suggestions = []
        
        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            current_time = self.get_current_ist_time()
            
            # Start from today or the requested date, whichever is later
            start_date = max(target_date, current_time.date())
            
            # Generate suggestions for the next 7 days
            for day_offset in range(7):
                check_date = start_date + datetime.timedelta(days=day_offset)
                
                # Skip Sundays
                if check_date.weekday() == 6:
                    continue
                
                # Generate time slots
                start_hour = self.business_hours['start']
                end_hour = self.business_hours['end']
                
                # If it's today, start from current hour + 1
                if check_date == current_time.date():
                    start_hour = max(start_hour, current_time.hour + 1)
                
                for hour in range(start_hour, end_hour):
                    for minute in [0, 30]:  # 30-minute intervals
                        time_slot = datetime.time(hour, minute)
                        
                        suggestions.append({
                            'date': check_date.strftime('%Y-%m-%d'),
                            'time': time_slot.strftime('%H:%M'),
                            'display': f"{check_date.strftime('%A, %b %d')} at {time_slot.strftime('%I:%M %p')}"
                        })
                        
                        if len(suggestions) >= 10:
                            return suggestions
            
            return suggestions
            
        except Exception as e:
            print(f"Error generating suggestions: {e}")
            return []


class SalonBookingService:
    """Main salon booking service with comprehensive functionality"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.calendar_manager = GoogleCalendarManager()
        self.datetime_validator = DateTimeValidator()
        self.setup_context()
        self.populate_initial_data()
    
    def setup_context(self):
        """Initialize salon business context"""
        now = self.datetime_validator.get_current_ist_time()
        
        self.current_date = now.strftime("%A, %B %d, %Y")
        self.current_time = now.strftime("%I:%M %p")
        self.current_day_of_week = now.strftime("%A")
        self.current_date_iso = now.strftime("%Y-%m-%d")
        self.current_time_24 = now.strftime("%H:%M")
        
        # Calculate tomorrow's date
        tomorrow = now + datetime.timedelta(days=1)
        self.tomorrow_date = tomorrow.strftime("%A, %B %d, %Y")
        self.tomorrow_date_iso = tomorrow.strftime("%Y-%m-%d")
        
        # Generate session ID
        self.session_id = f"leatmos_{int(now.timestamp() * 1000)}_{self._random_string(9)}"
    
    def populate_initial_data(self):
        """Populate database with initial salon data"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            
            # Add services
            services = [
                ("Haircut", 45, 500, "hair", 0),
                ("Spa Treatment", 90, 1200, "wellness", 0),
                ("Hair Wash & Style", 60, 400, "hair", 0),
                ("Facial Treatment", 75, 800, "skincare", 0),
                ("Manicure & Pedicure", 90, 600, "nails", 0),
                ("Threading & Waxing", 45, 300, "grooming", 1),
                ("Bridal Makeup", 180, 2500, "special", 1)
            ]
            
            cursor.executemany('''
                INSERT OR IGNORE INTO services (name, duration, price, category, gender_specific)
                VALUES (?, ?, ?, ?, ?)
            ''', services)
            
            # Add stylists with calendar IDs
            stylists = [
                ("Kavya", "Women's cuts,Hair coloring,Bridal Makeup", "Monday,Tuesday,Wednesday,Friday,Saturday", "8 years", STYLIST_CALENDAR_IDS.get('Kavya', 'primary')),
                ("Arjun", "Men's cuts,Beard styling,Hair Wash & Style", "Tuesday,Wednesday,Thursday,Friday,Saturday", "6 years", STYLIST_CALENDAR_IDS.get('Arjun', 'primary')),
                ("Meera", "Spa treatments,Facials,Threading & Waxing", "Monday,Wednesday,Thursday,Friday,Saturday", "5 years", STYLIST_CALENDAR_IDS.get('Meera', 'primary')),
                ("Rohan", "Unisex cuts,Hair styling,Manicure & Pedicure", "Monday,Tuesday,Thursday,Saturday,Sunday", "4 years", STYLIST_CALENDAR_IDS.get('Rohan', 'primary')),
                ("Ananya", "Bridal makeup,Traditional styles,Facial Treatment", "Wednesday,Thursday,Friday,Saturday,Sunday", "7 years", STYLIST_CALENDAR_IDS.get('Ananya', 'primary'))
            ]
            
            cursor.executemany('''
                INSERT OR IGNORE INTO stylists (name, specialties, availability, experience, google_calendar_id)
                VALUES (?, ?, ?, ?, ?)
            ''', stylists)
            
            conn.commit()
            conn.close()
            print("✅ Initial salon data populated")
            
        except Exception as e:
            print(f"❌ Error populating initial data: {e}")
    
    def _random_string(self, length: int) -> str:
        """Generate random string for session ID"""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    
    def check_stylist_availability(self, stylist_name: str, date: str, time: str, duration: int) -> Dict[str, Any]:
        """Check if stylist is available and provide intelligent feedback"""
        
        # Validate date/time first
        validation = self.datetime_validator.validate_appointment_time(date, time)
        if not validation['valid']:
            return {
                'available': False,
                'reason': validation['errors'][0],
                'suggestions': self.datetime_validator.suggest_next_available_slots(date, duration),
                'validation_errors': validation['errors']
            }
        
        # Check database availability
        db_available = self.db.check_availability(stylist_name, date, time, duration)
        
        # Check Google Calendar if connected
        calendar_available = True
        if self.calendar_manager.service:
            start_datetime = validation['appointment_datetime']
            end_datetime = start_datetime + datetime.timedelta(minutes=duration)
            
            # Get stylist's calendar ID from configuration
            calendar_id = STYLIST_CALENDAR_IDS.get(stylist_name, 'primary')
            calendar_available = self.calendar_manager.check_availability(
                calendar_id, 
                start_datetime.isoformat(), 
                end_datetime.isoformat()
            )
        
        available = db_available and calendar_available
        
        if not available:
            reason = f"{stylist_name} is already booked at that time"
            if not db_available:
                reason += " (database conflict)"
            if not calendar_available:
                reason += " (calendar conflict)"
            
            return {
                'available': False,
                'reason': reason,
                'suggestions': self.datetime_validator.suggest_next_available_slots(date, duration),
                'validation_errors': []
            }
        
        return {
            'available': True,
            'reason': f"{stylist_name} is available",
            'suggestions': [],
            'validation_errors': []
        }
    
    def book_appointment(self, booking_details: Dict[str, Any]) -> Dict[str, Any]:
        """Book an appointment with full validation and calendar integration"""
        
        # Validate required fields
        required_fields = ['customer_name', 'stylist_name', 'service_name', 'appointment_date', 'start_time']
        missing_fields = [field for field in required_fields if not booking_details.get(field)]
        
        if missing_fields:
            return {
                'success': False,
                'message': f"Missing required fields: {', '.join(missing_fields)}",
                'suggestions': []
            }
        
        # Get service details from database
        service = self.db.get_service_details(booking_details['service_name'])
        if not service:
            return {
                'success': False,
                'message': f"Service '{booking_details['service_name']}' not found",
                'suggestions': []
            }
        
        # Add service details to booking
        booking_details['service_duration'] = service['duration']
        booking_details['service_price'] = service['price']
        
        # Check availability first
        availability = self.check_stylist_availability(
            booking_details['stylist_name'],
            booking_details['appointment_date'],
            booking_details['start_time'],
            booking_details['service_duration']
        )
        
        if not availability['available']:
            return {
                'success': False,
                'message': availability['reason'],
                'suggestions': availability['suggestions'],
                'validation_errors': availability.get('validation_errors', [])
            }
        
        # Create calendar event if Google Calendar is connected
        calendar_event_id = None
        if self.calendar_manager.service:
            validation = self.datetime_validator.validate_appointment_time(
                booking_details['appointment_date'], 
                booking_details['start_time']
            )
            
            start_datetime = validation['appointment_datetime']
            end_datetime = start_datetime + datetime.timedelta(minutes=booking_details['service_duration'])
            
            event_details = {
                'summary': f"{booking_details['service_name']} - {booking_details['customer_name']}",
                'description': f"""Le Atmos Salon Appointment

Service: {booking_details['service_name']} ({booking_details['service_duration']} min)
Price: ₹{booking_details['service_price']}
Customer: {booking_details['customer_name']}
Phone: {booking_details.get('customer_phone', 'Not provided')}
Email: {booking_details.get('customer_email', 'Not provided')}

Booked via Le Atmos Voice Assistant
Session ID: {self.session_id}""",
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'Asia/Kolkata',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'Asia/Kolkata',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 24 hours
                        {'method': 'popup', 'minutes': 60},       # 1 hour
                    ],
                },
                'location': 'Le Atmos Salon, Gujarat',
                'colorId': '2'  # Green color for confirmed appointments
            }
            
            calendar_id = STYLIST_CALENDAR_IDS.get(booking_details['stylist_name'], 'primary')
            calendar_event_id = self.calendar_manager.create_event(calendar_id, event_details)
        
        # Calculate end time
        start_time = datetime.datetime.strptime(booking_details['start_time'], '%H:%M')
        end_time = start_time + datetime.timedelta(minutes=booking_details['service_duration'])
        
        # Prepare appointment data
        appointment_data = {
            **booking_details,
            'end_time': end_time.strftime('%H:%M'),
            'google_calendar_event_id': calendar_event_id,
            'session_id': self.session_id
        }
        
        # Save to database
        try:
            appointment_id = self.db.add_appointment(appointment_data)
            
            # Format confirmation details
            validation = self.datetime_validator.validate_appointment_time(
                booking_details['appointment_date'], 
                booking_details['start_time']
            )
            
            confirmation_details = {
                'appointment_id': appointment_id,
                'customer_name': booking_details['customer_name'],
                'service_name': booking_details['service_name'],
                'service_duration': booking_details['service_duration'],
                'service_price': booking_details['service_price'],
                'stylist_name': booking_details['stylist_name'],
                'date': validation['formatted_date'],
                'start_time': validation['formatted_time'],
                'end_time': end_time.strftime('%I:%M %p'),
                'calendar_event_created': bool(calendar_event_id)
            }
            
            return {
                'success': True,
                'appointment_id': appointment_id,
                'calendar_event_id': calendar_event_id,
                'message': f"Appointment confirmed for {booking_details['customer_name']}!",
                'details': confirmation_details
            }
            
        except Exception as e:
            # If database save failed but calendar event was created, try to clean up
            if calendar_event_id and self.calendar_manager.service:
                calendar_id = STYLIST_CALENDAR_IDS.get(booking_details['stylist_name'], 'primary')
                self.calendar_manager.delete_event(calendar_id, calendar_event_id)
            
            return {
                'success': False,
                'message': f"Failed to save appointment: {str(e)}",
                'suggestions': []
            }
    
    def get_system_prompt(self) -> str:
        """Generate enhanced system prompt with real-time awareness"""
        
        # Get available time suggestions for today and tomorrow
        today_suggestions = self.datetime_validator.suggest_next_available_slots(self.current_date_iso, 60)
        tomorrow_suggestions = self.datetime_validator.suggest_next_available_slots(self.tomorrow_date_iso, 60)
        
        today_times = ', '.join([s['display'] for s in today_suggestions[:3]])
        tomorrow_times = ', '.join([s['display'] for s in tomorrow_suggestions[:3]])
        
        system_prompt = f"""You are Monika, a highly skilled, friendly, and exceptionally helpful AI assistant for Le Atmos Salon - Gujarat's most premium and luxurious salon.

CRITICAL CURRENT DATE/TIME AWARENESS:
- Current Date: {self.current_date} ({self.current_date_iso})
- Current Time: {self.current_time} ({self.current_time_24})
- Tomorrow's Date: {self.tomorrow_date} ({self.tomorrow_date_iso})
- Day of Week: {self.current_day_of_week}
- Available today: {today_times}
- Available tomorrow: {tomorrow_times}

CORE SALON SERVICES & PRICING:
1. Haircut - 45 minutes - ₹500
2. Spa Treatment - 90 minutes - ₹1,200  
3. Hair Wash & Style - 60 minutes - ₹400
4. Facial Treatment - 75 minutes - ₹800
5. Manicure & Pedicure - 90 minutes - ₹600
6. Threading & Waxing - 45 minutes - ₹300
7. Bridal Makeup - 180 minutes - ₹2,500

EXPERT STYLISTS & SPECIALTIES:
- Kavya: Women's cuts, Hair coloring, Bridal Makeup (8 years experience)
- Arjun: Men's cuts, Beard styling, Hair Wash & Style (6 years experience)  
- Meera: Spa treatments, Facials, Threading & Waxing (5 years experience)
- Rohan: Unisex cuts, Hair styling, Manicure & Pedicure (4 years experience)
- Ananya: Bridal makeup, Traditional styles, Facial Treatment (7 years experience)

BOOKING GUIDELINES:
- Business Hours: 9:00 AM to 8:00 PM (Monday-Saturday, CLOSED Sundays)
- Always check availability before confirming bookings
- For today's appointments, suggest times after current time
- Use real-time calendar integration when available
- Provide alternative times if requested slot is unavailable

CONVERSATION STYLE:
- Be warm, professional, and enthusiastic about Le Atmos services
- Use natural, conversational language
- Always confirm details before finalizing bookings
- Offer helpful suggestions when availability is limited
- Maintain luxury salon standards in all interactions

IMPORTANT: Always use the exact current date/time provided above and suggest realistic available slots."""

        return system_prompt


class UltravoxAgent:
    """Enhanced Ultravox API integration"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = ULTRAVOX_API_URL
    
    def create_call(self, system_prompt: str, tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create Ultravox call with enhanced salon context"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        call_config = {
            "systemPrompt": system_prompt,
            "model": "ultravox-v0_3",
            "voice": "terrence",
            "temperature": 0.7,
            "maxDuration": 600,  # 10 minutes max
            "recordingEnabled": True,
            "transcriptionEnabled": True
        }
        
        # Add tools if provided
        if tools:
            call_config["tools"] = tools
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=call_config,
                timeout=30
            )
            
            if response.status_code == 201:
                return {
                    "success": True,
                    "call_data": response.json(),
                    "message": "Call created successfully"
                }
            else:
                return {
                    "success": False,
                    "error": f"API Error: {response.status_code}",
                    "message": response.text
                }
                
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": "Network Error",
                "message": str(e)
            }


# Initialize global services
salon_service = SalonBookingService()
ultravox_agent = UltravoxAgent(ULTRAVOX_API_KEY) if ULTRAVOX_API_KEY else None


# Flask Routes
@app.route('/salon-booking', methods=['POST', 'OPTIONS'])
def salon_booking():
    """Enhanced salon booking endpoint with comprehensive functionality"""
    
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    
    try:
        print("📞 Salon booking request received")
        print(f"Request data: {request.get_json()}")
        
        if not ultravox_agent:
            print("❌ Ultravox API key not configured")
            return jsonify({
                "success": False,
                "error": "Ultravox API key not configured"
            }), 500
        
        print("✅ Ultravox agent available")
        
        # Get enhanced system prompt with real-time context
        system_prompt = salon_service.get_system_prompt()
        print(f"📝 System prompt length: {len(system_prompt)} characters")
        
        # Define salon booking tools
        booking_tools = [
            {
                "toolName": "check_availability",
                "description": "Check if a stylist is available at a specific date and time",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stylist_name": {"type": "string"},
                        "date": {"type": "string", "format": "date"},
                        "time": {"type": "string"},
                        "duration": {"type": "integer", "default": 60}
                    },
                    "required": ["stylist_name", "date", "time"]
                }
            },
            {
                "toolName": "book_appointment",
                "description": "Book a salon appointment with full details",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name": {"type": "string"},
                        "customer_phone": {"type": "string"},
                        "customer_email": {"type": "string"},
                        "stylist_name": {"type": "string"},
                        "service_name": {"type": "string"},
                        "appointment_date": {"type": "string", "format": "date"},
                        "start_time": {"type": "string"}
                    },
                    "required": ["customer_name", "stylist_name", "service_name", "appointment_date", "start_time"]
                }
            },
            {
                "toolName": "get_services",
                "description": "Get list of available services with pricing",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "toolName": "get_stylists", 
                "description": "Get list of available stylists with specialties",
                "parameters": {"type": "object", "properties": {}}
            }
        ]
        
        print("🔧 Creating call with Ultravox...")
        
        # Create call with Ultravox
        result = ultravox_agent.create_call(system_prompt, booking_tools)
        
        print(f"🔄 Ultravox API response: {result}")
        
        if result["success"]:
            return jsonify({
                "success": True,
                "call_id": result["call_data"].get("callId"),
                "join_url": result["call_data"].get("joinUrl"),
                "session_id": salon_service.session_id,
                "salon_context": {
                    "current_date": salon_service.current_date,
                    "current_time": salon_service.current_time,
                    "business_hours": "9:00 AM - 8:00 PM",
                    "available_services": len(salon_service.db.get_all_services()),
                    "available_stylists": len(salon_service.db.get_all_stylists())
                }
            }), 200
        else:
            print(f"❌ Ultravox API error: {result}")
            return jsonify({
                "success": False,
                "error": result["error"],
                "message": result["message"],
                "details": result.get("details", "No additional details")
            }), 400
            
    except Exception as e:
        print(f"❌ Server error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "Server Error",
            "message": str(e)
        }), 500


@app.route('/check-availability', methods=['POST'])
def check_availability():
    """Check stylist availability endpoint"""
    try:
        data = request.get_json()
        
        result = salon_service.check_stylist_availability(
            data.get('stylist_name'),
            data.get('date'),
            data.get('time'),
            data.get('duration', 60)
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            "available": False,
            "error": str(e)
        }), 500


@app.route('/book-appointment', methods=['POST'])
def book_appointment():
    """Book appointment endpoint"""
    try:
        data = request.get_json()
        result = salon_service.book_appointment(data)
        
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Booking failed: {str(e)}"
        }), 500


@app.route('/get-suggestions', methods=['POST'])
def get_suggestions():
    """Get time slot suggestions"""
    try:
        data = request.get_json()
        date = data.get('date', salon_service.current_date_iso)
        duration = data.get('duration', 60)
        
        suggestions = salon_service.datetime_validator.suggest_next_available_slots(date, duration)
        
        return jsonify({
            "suggestions": suggestions,
            "date_requested": date
        }), 200
        
    except Exception as e:
        return jsonify({
            "suggestions": [],
            "error": str(e)
        }), 500


@app.route('/appointments', methods=['GET'])
def get_appointments():
    """Get appointments with optional filters"""
    try:
        date = request.args.get('date')
        stylist_name = request.args.get('stylist')
        
        appointments = salon_service.db.get_appointments(date, stylist_name)
        
        return jsonify({
            "appointments": appointments,
            "total": len(appointments)
        }), 200
        
    except Exception as e:
        return jsonify({
            "appointments": [],
            "error": str(e)
        }), 500


@app.route('/services', methods=['GET'])
def get_services():
    """Get all available services"""
    try:
        services = salon_service.db.get_all_services()
        return jsonify({"services": services}), 200
        
    except Exception as e:
        return jsonify({
            "services": [],
            "error": str(e)
        }), 500


@app.route('/stylists', methods=['GET'])
def get_stylists():
    """Get all stylists"""
    try:
        stylists = salon_service.db.get_all_stylists()
        return jsonify({"stylists": stylists}), 200
        
    except Exception as e:
        return jsonify({
            "stylists": [],
            "error": str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "services": {
            "database": "connected",
            "calendar": "connected" if salon_service.calendar_manager.service else "disconnected",
            "ultravox": "configured" if ULTRAVOX_API_KEY else "not configured"
        }
    }), 200


@app.route('/salon-info', methods=['GET'])
def salon_info():
    """Get salon information"""
    return jsonify({
        "name": "Le Atmos Salon",
        "location": "Gujarat, India",
        "business_hours": "9:00 AM - 8:00 PM",
        "working_days": "Monday - Saturday",
        "closed_days": "Sunday",
        "contact": {
            "booking": "Voice Assistant Available",
            "address": "Gujarat, India"
        },
        "current_context": {
            "date": salon_service.current_date,
            "time": salon_service.current_time,
            "day": salon_service.current_day_of_week
        }
    }), 200


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "available_endpoints": [
            "/salon-booking (POST)",
            "/check-availability (POST)",
            "/book-appointment (POST)",
            "/appointments (GET)",
            "/services (GET)",
            "/stylists (GET)",
            "/health (GET)",
            "/salon-info (GET)"
        ]
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Internal server error",
        "message": "Please try again later"
    }), 500


if __name__ == '__main__':
    print("🚀 Starting Le Atmos Salon Voice Assistant...")
    print(f"📅 Current Date: {salon_service.current_date}")
    print(f"⏰ Current Time: {salon_service.current_time}")
    print(f"🗓️  Session ID: {salon_service.session_id}")
    
    port = int(os.getenv('PORT', 5000))
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
