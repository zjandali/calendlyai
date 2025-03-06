from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class TimeSlot(BaseModel):
    """Time slot model"""
    start: str = Field(..., description="Start time in format 'HH:MM AM/PM'")
    end: str = Field(..., description="End time in format 'HH:MM AM/PM'")


class DaySlots(BaseModel):
    """Model for a day's available slots"""
    date: str = Field(..., description="Date in format 'Day of week, Month Day, Year'")
    free_slots: List[TimeSlot] = Field(default_factory=list, description="List of free time slots")


class MockCalendar(BaseModel):
    """Model for mock calendar data"""
    week_of: str = Field(..., description="Week of date")
    timezone: str = Field("America/Los_Angeles", description="Timezone")
    available_slots: List[DaySlots] = Field(default_factory=list)


class CalendlyTimeSlot(BaseModel):
    """Model for a Calendly time slot"""
    time: str = Field(..., description="Time in format 'HH:MM AM/PM'")
    iso_time: str = Field(..., description="ISO 8601 formatted time")


class CalendlyDate(BaseModel):
    """Model for Calendly date with available times"""
    date: str = Field(..., description="Date in format 'Month Day, Year'")
    times: List[str] = Field(default_factory=list)
    iso_times: List[str] = Field(default_factory=list)


class CalendlyCalendar(BaseModel):
    """Model for formatted Calendly calendar data"""
    timezone: str = Field(..., description="Timezone")
    available_dates: List[CalendlyDate] = Field(default_factory=list)


class UnifiedTimeSlot(BaseModel):
    """Model for a unified time slot format"""
    date: str = Field(..., description="Date in format 'Month Day, Year'")
    day_of_week: str = Field(..., description="Day of week")
    available_times: List[str] = Field(default_factory=list, description="Available times in 'HH:MM AM/PM' format")


class UnifiedCalendar(BaseModel):
    """Model for unified calendar format"""
    timezone: str = Field(..., description="Timezone")
    available_days: List[UnifiedTimeSlot] = Field(default_factory=list)


class BookingResult(BaseModel):
    """Model for booking result"""
    success: bool = Field(..., description="Whether the booking was successful")
    result: Optional[str] = Field(None, description="Result message from Anchor Browser")
    booking_url: Optional[str] = Field(None, description="URL used for booking")
    suggested_time_iso: Optional[str] = Field(None, description="Suggested time in ISO format")
    suggested_time_pst: Optional[str] = Field(None, description="Suggested time in PST readable format")
    timestamp: str = Field(..., description="Timestamp of the booking attempt")
    session_id: Optional[str] = Field(None, description="Anchor Browser session ID")
    error: Optional[str] = Field(None, description="Error message if booking failed")
    traceback: Optional[str] = Field(None, description="Traceback if booking failed")


class RunSummary(BaseModel):
    """Model for run summary"""
    run_timestamp: str = Field(..., description="Timestamp of the run")
    this_run: Dict[str, Any] = Field(..., description="Results of this run")
    overall: Dict[str, Any] = Field(..., description="Overall results") 