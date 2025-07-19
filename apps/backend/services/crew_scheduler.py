"""
Crew scheduling and optimization service.
"""

from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta, time
from enum import Enum
import uuid
from sqlalchemy.orm import Session
from ..db.business_models import User
from collections import defaultdict


class CrewSkill(str, Enum):
    SHINGLE_INSTALLATION = "shingle_installation"
    FLAT_ROOF = "flat_roof"
    METAL_ROOF = "metal_roof"
    TILE_ROOF = "tile_roof"
    SOLAR_INSTALLATION = "solar_installation"
    GUTTER_INSTALLATION = "gutter_installation"
    INSPECTION = "inspection"
    TEAR_OFF = "tear_off"
    REPAIRS = "repairs"
    EMERGENCY = "emergency"


class CrewStatus(str, Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    ON_JOB = "on_job"
    BREAK = "break"
    OFF_DUTY = "off_duty"
    VACATION = "vacation"
    TRAINING = "training"


class CrewScheduler:
    """Service for intelligent crew scheduling and assignment."""
    
    def __init__(self):
        self.crews: Dict[str, Dict[str, Any]] = {}
        self.crew_members: Dict[str, Dict[str, Any]] = {}
        self.assignments: Dict[str, Dict[str, Any]] = {}
        self.schedule: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._initialize_sample_data()
        
    def _initialize_sample_data(self):
        """Initialize with sample crew data."""
        # Create sample crew members
        sample_members = [
            {
                "id": str(uuid.uuid4()),
                "name": "John Smith",
                "skills": [CrewSkill.SHINGLE_INSTALLATION, CrewSkill.TEAR_OFF],
                "status": CrewStatus.AVAILABLE,
                "hourly_rate": 35.0,
                "performance_score": 4.5
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Mike Johnson",
                "skills": [CrewSkill.METAL_ROOF, CrewSkill.FLAT_ROOF],
                "status": CrewStatus.AVAILABLE,
                "hourly_rate": 38.0,
                "performance_score": 4.7
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Sarah Williams",
                "skills": [CrewSkill.INSPECTION, CrewSkill.REPAIRS],
                "status": CrewStatus.AVAILABLE,
                "hourly_rate": 32.0,
                "performance_score": 4.8
            }
        ]
        
        for member in sample_members:
            self.crew_members[member["id"]] = member
    
    async def find_best_assignee(
        self,
        task_type: str,
        required_skills: List[str],
        preferred_time: Optional[datetime],
        location: Optional[Tuple[float, float]]
    ) -> Optional[Dict[str, Any]]:
        """
        Find the best assignee for a task based on multiple factors.
        
        Considers:
        - Skill match
        - Availability
        - Current workload
        - Location proximity
        - Performance history
        """
        candidates = []
        
        # Convert required skills to enum
        required_skill_enums = []
        for skill in required_skills:
            try:
                required_skill_enums.append(CrewSkill(skill))
            except ValueError:
                continue
        
        # Evaluate each crew member
        for member_id, member in self.crew_members.items():
            if member["status"] != CrewStatus.AVAILABLE:
                continue
                
            # Calculate skill match score
            member_skills = set(member["skills"])
            required_skills_set = set(required_skill_enums)
            skill_match = len(member_skills.intersection(required_skills_set)) / len(required_skills_set) if required_skills_set else 1.0
            
            if skill_match == 0:
                continue
                
            # Calculate availability score
            availability_score = 1.0 if member["status"] == CrewStatus.AVAILABLE else 0.5
            
            # Calculate workload score (mock - would check actual schedule)
            current_workload = len(self.schedule.get(member_id, []))
            workload_score = max(0, 1.0 - (current_workload / 10))  # Assuming 10 is max workload
            
            # Calculate location score (mock)
            location_score = 0.8  # Would calculate based on actual distance
            
            # Calculate overall score
            overall_score = (
                skill_match * 0.4 +
                availability_score * 0.3 +
                workload_score * 0.2 +
                location_score * 0.1
            )
            
            candidates.append({
                "user_id": member_id,
                "name": member["name"],
                "score": overall_score,
                "factors": {
                    "skill_match": skill_match,
                    "availability": availability_score,
                    "workload": workload_score,
                    "location": location_score,
                    "performance": member["performance_score"] / 5.0
                },
                "crew_ids": []
            })
        
        # Return best candidate
        if candidates:
            return max(candidates, key=lambda x: x["score"])
        
        return None
    
    async def check_crew_availability(
        self,
        crew_ids: List[str],
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """
        Check availability of crew members for a time period.
        """
        available = []
        conflicts = []
        
        for crew_id in crew_ids:
            member = self.crew_members.get(crew_id)
            if not member:
                conflicts.append({
                    "user_id": crew_id,
                    "conflict": "Crew member not found"
                })
                continue
                
            # Check current status
            if member["status"] != CrewStatus.AVAILABLE:
                conflicts.append({
                    "user_id": crew_id,
                    "conflict": f"Status: {member['status']}"
                })
                continue
                
            # Check schedule conflicts
            member_schedule = self.schedule.get(crew_id, [])
            has_conflict = False
            
            for assignment in member_schedule:
                assignment_start = datetime.fromisoformat(assignment["start_time"])
                assignment_end = datetime.fromisoformat(assignment["end_time"])
                
                # Check for time overlap
                if not (end_time <= assignment_start or start_time >= assignment_end):
                    conflicts.append({
                        "user_id": crew_id,
                        "conflict": f"Already scheduled for job {assignment['job_id']}"
                    })
                    has_conflict = True
                    break
                    
            if not has_conflict:
                available.append(crew_id)
        
        return {
            "available": available,
            "conflicts": conflicts,
            "fully_available": len(conflicts) == 0
        }
    
    async def optimize_schedule(
        self,
        tasks: List[Dict[str, Any]],
        constraints: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Optimize task scheduling across multiple crews.
        
        Uses constraint satisfaction and optimization algorithms.
        """
        optimized_assignments = []
        unassigned_tasks = []
        
        # Sort tasks by priority and estimated duration
        sorted_tasks = sorted(
            tasks,
            key=lambda x: (x.get("priority", 0), x.get("estimated_hours", 0)),
            reverse=True
        )
        
        # Track assigned crew members
        assigned_members = set()
        
        for task in sorted_tasks:
            # Find best assignee for this task
            required_skills = task.get("required_skills", [])
            preferred_time = datetime.fromisoformat(task.get("preferred_time", datetime.now().isoformat()))
            location = task.get("location")
            
            best_assignee = await self.find_best_assignee(
                task.get("type", "general"),
                required_skills,
                preferred_time,
                location
            )
            
            if best_assignee and best_assignee["user_id"] not in assigned_members:
                # Check availability
                start_time = preferred_time
                end_time = start_time + timedelta(hours=task.get("estimated_hours", 4))
                
                availability = await self.check_crew_availability(
                    [best_assignee["user_id"]],
                    start_time,
                    end_time
                )
                
                if availability["fully_available"]:
                    # Create assignment
                    assignment = {
                        "task_id": task.get("id", str(uuid.uuid4())),
                        "user_id": best_assignee["user_id"],
                        "user_name": best_assignee["name"],
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "assignment_score": best_assignee["score"],
                        "job_id": task.get("job_id")
                    }
                    
                    # Update schedule
                    self.schedule[best_assignee["user_id"]].append(assignment)
                    assigned_members.add(best_assignee["user_id"])
                    
                    optimized_assignments.append(assignment)
                else:
                    unassigned_tasks.append(task)
            else:
                unassigned_tasks.append(task)
                
        return {
            "optimized_assignments": optimized_assignments,
            "unassigned_tasks": unassigned_tasks,
            "total_tasks": len(tasks),
            "assigned_count": len(optimized_assignments),
            "unassigned_count": len(unassigned_tasks),
            "optimization_rate": len(optimized_assignments) / len(tasks) if tasks else 0
        }
    
    async def get_crew_workload(
        self,
        user_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """
        Get workload metrics for a crew member.
        """
        member = self.crew_members.get(user_id)
        if not member:
            return None
            
        # Calculate workload from schedule
        member_schedule = self.schedule.get(user_id, [])
        total_hours = 0
        task_count = 0
        overtime_hours = 0
        
        for assignment in member_schedule:
            start = datetime.fromisoformat(assignment["start_time"])
            end = datetime.fromisoformat(assignment["end_time"])
            
            # Check if within period
            if start >= period_start and end <= period_end:
                task_hours = (end - start).total_seconds() / 3600
                total_hours += task_hours
                task_count += 1
                
                # Calculate overtime (over 8 hours per day)
                if task_hours > 8:
                    overtime_hours += task_hours - 8
                    
        # Calculate scheduled hours (business days * 8 hours)
        business_days = 0
        current_date = period_start
        while current_date <= period_end:
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                business_days += 1
            current_date += timedelta(days=1)
            
        scheduled_hours = business_days * 8
        utilization = total_hours / scheduled_hours if scheduled_hours > 0 else 0
        
        return {
            "user_id": user_id,
            "user_name": member["name"],
            "total_hours": total_hours,
            "scheduled_hours": scheduled_hours,
            "utilization": utilization,
            "task_count": task_count,
            "overtime_hours": overtime_hours,
            "hourly_rate": member["hourly_rate"],
            "estimated_cost": total_hours * member["hourly_rate"]
        }
    
    async def schedule_crew_assignment(
        self,
        crew_id: str,
        job_id: str,
        start_time: datetime,
        estimated_hours: float,
        location: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Schedule a crew member for a specific job."""
        member = self.crew_members.get(crew_id)
        if not member:
            raise ValueError(f"Crew member {crew_id} not found")
            
        end_time = start_time + timedelta(hours=estimated_hours)
        
        # Check availability
        availability = await self.check_crew_availability(
            [crew_id],
            start_time,
            end_time
        )
        
        if not availability["fully_available"]:
            raise ValueError(f"Crew member not available: {availability['conflicts'][0]['conflict']}")
            
        # Create assignment
        assignment_id = str(uuid.uuid4())
        assignment = {
            "id": assignment_id,
            "user_id": crew_id,
            "job_id": job_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "estimated_hours": estimated_hours,
            "location": location,
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Update schedule and assignments
        self.assignments[assignment_id] = assignment
        self.schedule[crew_id].append(assignment)
        
        # Update member status
        member["status"] = CrewStatus.ASSIGNED
        
        return {
            "assignment_id": assignment_id,
            "crew_member": {
                "id": crew_id,
                "name": member["name"],
                "skills": [skill.value for skill in member["skills"]]
            },
            "scheduled_time": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration_hours": estimated_hours
            }
        }