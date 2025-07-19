"""
Scheduling service for managing appointments and calendar events.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, time
from pydantic import BaseModel
from enum import Enum
import uuid

class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class AppointmentType(str, Enum):
    CONSULTATION = "consultation"
    INSPECTION = "inspection"
    ESTIMATE = "estimate"
    INSTALLATION = "installation"
    FOLLOW_UP = "follow_up"
    MAINTENANCE = "maintenance"

class TimeSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    available: bool = True
    appointment_id: Optional[str] = None

class Appointment(BaseModel):
    id: str
    customer_id: str
    customer_name: str
    appointment_type: AppointmentType
    status: AppointmentStatus
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    technician_id: Optional[str] = None
    technician_name: Optional[str] = None
    address: Dict[str, str]
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    reminder_sent: bool = False
    
class CalendarDay(BaseModel):
    date: datetime
    time_slots: List[TimeSlot]
    appointments: List[Appointment]

class SchedulingService:
    """Service for managing appointments and schedules."""
    
    def __init__(self):
        self.appointments: Dict[str, Appointment] = {}
        self.technician_schedules: Dict[str, List[str]] = {}
        
        # Business hours configuration
        self.business_hours = {
            0: None,  # Sunday - closed
            1: (time(8, 0), time(18, 0)),  # Monday
            2: (time(8, 0), time(18, 0)),  # Tuesday
            3: (time(8, 0), time(18, 0)),  # Wednesday
            4: (time(8, 0), time(18, 0)),  # Thursday
            5: (time(8, 0), time(18, 0)),  # Friday
            6: (time(9, 0), time(15, 0)),  # Saturday
        }
        
        # Appointment durations by type (minutes)
        self.appointment_durations = {
            AppointmentType.CONSULTATION: 30,
            AppointmentType.INSPECTION: 60,
            AppointmentType.ESTIMATE: 45,
            AppointmentType.INSTALLATION: 480,  # 8 hours
            AppointmentType.FOLLOW_UP: 30,
            AppointmentType.MAINTENANCE: 120,
        }
    
    def get_available_slots(self, 
                           date: datetime,
                           appointment_type: AppointmentType,
                           technician_id: Optional[str] = None) -> List[TimeSlot]:
        """Get available time slots for a specific date."""
        # Get business hours for the day
        weekday = date.weekday()
        hours = self.business_hours.get(weekday)
        
        if not hours:
            return []  # Closed on this day
        
        start_hour, end_hour = hours
        duration = self.appointment_durations[appointment_type]
        
        # Generate all possible time slots
        slots = []
        current_time = datetime.combine(date.date(), start_hour)
        end_time = datetime.combine(date.date(), end_hour)
        
        while current_time + timedelta(minutes=duration) <= end_time:
            slot_end = current_time + timedelta(minutes=duration)
            
            # Check if slot is available
            is_available = self._is_slot_available(
                current_time, slot_end, technician_id
            )
            
            slots.append(TimeSlot(
                start_time=current_time,
                end_time=slot_end,
                available=is_available
            ))
            
            # Move to next slot (30-minute intervals)
            current_time += timedelta(minutes=30)
        
        return slots
    
    def _is_slot_available(self, 
                          start_time: datetime,
                          end_time: datetime,
                          technician_id: Optional[str] = None) -> bool:
        """Check if a time slot is available."""
        for appointment in self.appointments.values():
            # Skip if checking specific technician
            if technician_id and appointment.technician_id != technician_id:
                continue
            
            # Check for overlap
            if (appointment.status not in [AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED] and
                appointment.start_time < end_time and
                appointment.end_time > start_time):
                return False
        
        return True
    
    def create_appointment(self,
                          customer_id: str,
                          customer_name: str,
                          appointment_type: AppointmentType,
                          start_time: datetime,
                          address: Dict[str, str],
                          technician_id: Optional[str] = None,
                          technician_name: Optional[str] = None,
                          notes: Optional[str] = None) -> Appointment:
        """Create a new appointment."""
        appointment_id = str(uuid.uuid4())
        duration = self.appointment_durations[appointment_type]
        end_time = start_time + timedelta(minutes=duration)
        
        # Check availability
        if not self._is_slot_available(start_time, end_time, technician_id):
            raise ValueError("Time slot is not available")
        
        appointment = Appointment(
            id=appointment_id,
            customer_id=customer_id,
            customer_name=customer_name,
            appointment_type=appointment_type,
            status=AppointmentStatus.SCHEDULED,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration,
            technician_id=technician_id,
            technician_name=technician_name,
            address=address,
            notes=notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.appointments[appointment_id] = appointment
        
        # Update technician schedule
        if technician_id:
            if technician_id not in self.technician_schedules:
                self.technician_schedules[technician_id] = []
            self.technician_schedules[technician_id].append(appointment_id)
        
        return appointment
    
    def update_appointment(self,
                          appointment_id: str,
                          status: Optional[AppointmentStatus] = None,
                          start_time: Optional[datetime] = None,
                          technician_id: Optional[str] = None,
                          notes: Optional[str] = None) -> Appointment:
        """Update an existing appointment."""
        if appointment_id not in self.appointments:
            raise ValueError("Appointment not found")
        
        appointment = self.appointments[appointment_id]
        
        # Update status
        if status:
            appointment.status = status
        
        # Update time if provided
        if start_time:
            duration = appointment.duration_minutes
            end_time = start_time + timedelta(minutes=duration)
            
            # Check availability (excluding current appointment)
            temp_status = appointment.status
            appointment.status = AppointmentStatus.CANCELLED  # Temporarily
            
            if not self._is_slot_available(start_time, end_time, appointment.technician_id):
                appointment.status = temp_status
                raise ValueError("New time slot is not available")
            
            appointment.status = temp_status
            appointment.start_time = start_time
            appointment.end_time = end_time
        
        # Update technician
        if technician_id and technician_id != appointment.technician_id:
            # Remove from old technician's schedule
            if appointment.technician_id in self.technician_schedules:
                self.technician_schedules[appointment.technician_id].remove(appointment_id)
            
            # Add to new technician's schedule
            if technician_id not in self.technician_schedules:
                self.technician_schedules[technician_id] = []
            self.technician_schedules[technician_id].append(appointment_id)
            
            appointment.technician_id = technician_id
        
        # Update notes
        if notes is not None:
            appointment.notes = notes
        
        appointment.updated_at = datetime.utcnow()
        return appointment
    
    def cancel_appointment(self, appointment_id: str, reason: Optional[str] = None) -> Appointment:
        """Cancel an appointment."""
        appointment = self.update_appointment(
            appointment_id,
            status=AppointmentStatus.CANCELLED,
            notes=f"Cancelled: {reason}" if reason else "Cancelled"
        )
        return appointment
    
    def get_appointment(self, appointment_id: str) -> Optional[Appointment]:
        """Get appointment by ID."""
        return self.appointments.get(appointment_id)
    
    def get_appointments_by_date(self, 
                                date: datetime,
                                technician_id: Optional[str] = None) -> List[Appointment]:
        """Get all appointments for a specific date."""
        start_of_day = datetime.combine(date.date(), time.min)
        end_of_day = datetime.combine(date.date(), time.max)
        
        appointments = []
        for appointment in self.appointments.values():
            if (appointment.start_time >= start_of_day and 
                appointment.start_time <= end_of_day):
                
                if technician_id and appointment.technician_id != technician_id:
                    continue
                    
                appointments.append(appointment)
        
        # Sort by start time
        appointments.sort(key=lambda x: x.start_time)
        return appointments
    
    def get_customer_appointments(self, 
                                 customer_id: str,
                                 include_past: bool = False) -> List[Appointment]:
        """Get all appointments for a customer."""
        appointments = []
        now = datetime.utcnow()
        
        for appointment in self.appointments.values():
            if appointment.customer_id == customer_id:
                if include_past or appointment.start_time >= now:
                    appointments.append(appointment)
        
        appointments.sort(key=lambda x: x.start_time)
        return appointments
    
    def get_technician_schedule(self, 
                               technician_id: str,
                               start_date: datetime,
                               end_date: datetime) -> List[Appointment]:
        """Get technician's schedule for a date range."""
        appointments = []
        
        if technician_id in self.technician_schedules:
            for appointment_id in self.technician_schedules[technician_id]:
                appointment = self.appointments.get(appointment_id)
                if (appointment and 
                    appointment.start_time >= start_date and
                    appointment.start_time <= end_date and
                    appointment.status not in [AppointmentStatus.CANCELLED]):
                    appointments.append(appointment)
        
        appointments.sort(key=lambda x: x.start_time)
        return appointments
    
    def get_upcoming_appointments(self, hours: int = 24) -> List[Appointment]:
        """Get appointments in the next N hours."""
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours)
        
        upcoming = []
        for appointment in self.appointments.values():
            if (appointment.start_time >= now and 
                appointment.start_time <= cutoff and
                appointment.status in [AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]):
                upcoming.append(appointment)
        
        upcoming.sort(key=lambda x: x.start_time)
        return upcoming
    
    def send_reminders(self) -> List[str]:
        """Send reminders for upcoming appointments."""
        # Get appointments in next 24 hours
        upcoming = self.get_upcoming_appointments(24)
        reminded = []
        
        for appointment in upcoming:
            if not appointment.reminder_sent:
                # In production, this would send actual reminders
                appointment.reminder_sent = True
                reminded.append(appointment.id)
        
        return reminded
    
    def get_calendar_view(self, 
                         start_date: datetime,
                         end_date: datetime,
                         technician_id: Optional[str] = None) -> List[CalendarDay]:
        """Get calendar view for date range."""
        calendar_days = []
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            date = datetime.combine(current_date, time.min)
            
            # Get appointments for the day
            appointments = self.get_appointments_by_date(date, technician_id)
            
            # Get time slots
            slots = []
            if appointments:
                # Generate slots based on appointments
                for appointment in appointments:
                    slots.append(TimeSlot(
                        start_time=appointment.start_time,
                        end_time=appointment.end_time,
                        available=False,
                        appointment_id=appointment.id
                    ))
            
            calendar_days.append(CalendarDay(
                date=date,
                time_slots=slots,
                appointments=appointments
            ))
            
            current_date += timedelta(days=1)
        
        return calendar_days

# Alias for backward compatibility
SchedulingEngine = SchedulingService