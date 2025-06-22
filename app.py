import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import json
from typing import List, Dict, Tuple

# Configure page
st.set_page_config(
    page_title="Resource Management System",
    page_icon="👥",
    layout="wide"
)

# Database setup
DB_NAME = "resource_management.db"

def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create employees table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            emp_id TEXT PRIMARY KEY,
            current_workload REAL DEFAULT 0,
            next_free_time REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create tasks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            duration REAL NOT NULL,
            assigned_to TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_to) REFERENCES employees (emp_id)
        )
    ''')
    
    conn.commit()
    conn.close()

class DatabaseManager:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def add_employee(self, emp_id: str) -> bool:
        """Add new employee to database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO employees (emp_id) VALUES (?)", (emp_id,))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def remove_employee(self, emp_id: str):
        """Remove employee and their tasks"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE assigned_to = ?", (emp_id,))
        cursor.execute("DELETE FROM employees WHERE emp_id = ?", (emp_id,))
        conn.commit()
        conn.close()
    
    def get_all_employees(self) -> List[Dict]:
        """Get all employees with their current workload"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT emp_id, current_workload, next_free_time FROM employees")
        employees = []
        for row in cursor.fetchall():
            employees.append({
                'emp_id': row[0],
                'current_workload': row[1],
                'next_free_time': row[2],
                'available_hours': max(0, 9 - row[1]),
                'is_available': row[1] < 9
            })
        conn.close()
        return employees
    
    def add_task(self, task_id: str, description: str, duration: float, assigned_to: str):
        """Add task and update employee workload"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Add task
        cursor.execute('''
            INSERT INTO tasks (task_id, description, duration, assigned_to) 
            VALUES (?, ?, ?, ?)
        ''', (task_id, description, duration, assigned_to))
        
        # Update employee workload
        cursor.execute('''
            UPDATE employees 
            SET current_workload = current_workload + ?,
                next_free_time = current_workload + ?
            WHERE emp_id = ?
        ''', (duration, duration, assigned_to))
        
        conn.commit()
        conn.close()
    
    def get_all_tasks(self) -> List[Dict]:
        """Get all tasks"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT task_id, description, duration, assigned_to, created_at 
            FROM tasks ORDER BY created_at DESC
        ''')
        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'task_id': row[0],
                'description': row[1],
                'duration': row[2],
                'assigned_to': row[3],
                'created_at': row[4]
            })
        conn.close()
        return tasks
    
    def get_task_assignments(self) -> Dict[str, List[Dict]]:
        """Get tasks grouped by employee"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT emp_id, task_id, description, duration, created_at
            FROM employees e
            LEFT JOIN tasks t ON e.emp_id = t.assigned_to
            ORDER BY e.emp_id, t.created_at
        ''')
        
        assignments = {}
        for row in cursor.fetchall():
            emp_id = row[0]
            if emp_id not in assignments:
                assignments[emp_id] = []
            
            if row[1]:  # If task exists
                assignments[emp_id].append({
                    'task_id': row[1],
                    'description': row[2],
                    'duration': row[3],
                    'created_at': row[4]
                })
        
        conn.close()
        return assignments
    
    def reset_all_data(self):
        """Reset all data in database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks")
        cursor.execute("DELETE FROM employees")
        conn.commit()
        conn.close()

class TaskScheduler:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def find_best_employee(self, task_duration: float) -> str:
        employees = self.db_manager.get_all_employees()
        
        if not employees:
            return None
        
        # First, try to find employees who can fit the task today
        available_employees = []
        for emp in employees:
            if emp['available_hours'] >= task_duration:
                available_employees.append((emp['current_workload'], emp['emp_id']))
        
        if available_employees:
            # Sort by current workload (least loaded first)
            available_employees.sort()
            return available_employees[0][1]
        
        # If no one can fit it today, assign to who gets free first
        next_free_times = [(emp['next_free_time'], emp['emp_id']) for emp in employees]
        next_free_times.sort()
        return next_free_times[0][1]

# Initialize database
init_database()
db_manager = DatabaseManager()

def main():
    st.title("🏢 Resource Management System")
    st.markdown("*Data is now persistently stored in SQLite database*")
    st.markdown("---")
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    tab = st.sidebar.radio("Select Section", ["Employee Management", "Task Management", "Dashboard", "Task Assignments"])
    
    if tab == "Employee Management":
        employee_management()
    elif tab == "Task Management":
        task_management()
    elif tab == "Dashboard":
        dashboard()
    elif tab == "Task Assignments":
        task_assignments()

def employee_management():
    st.header("👥 Employee Management")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Add New Employee")
        emp_id = st.text_input("Employee ID", placeholder="e.g., EMP001")
        
        if st.button("Add Employee", type="primary"):
            if emp_id:
                if db_manager.add_employee(emp_id):
                    st.success(f"Employee {emp_id} added successfully!")
                    st.rerun()
                else:
                    st.error("Employee ID already exists!")
            else:
                st.error("Please enter a valid Employee ID!")
    
    with col2:
        st.subheader("Current Employees")
        employees = db_manager.get_all_employees()
        
        if employees:
            emp_data = []
            for emp in employees:
                emp_data.append({
                    "Employee ID": emp['emp_id'],
                    "Current Workload (hrs)": f"{emp['current_workload']:.1f}/9",
                    "Available Hours": f"{emp['available_hours']:.1f}",
                    "Status": "Available" if emp['is_available'] else "Fully Loaded"
                })
            
            df = pd.DataFrame(emp_data)
            st.dataframe(df, use_container_width=True)
            
            # Remove employee option
            st.subheader("Remove Employee")
            emp_ids = [emp['emp_id'] for emp in employees]
            emp_to_remove = st.selectbox("Select employee to remove", emp_ids)
            if st.button("Remove Employee", type="secondary"):
                db_manager.remove_employee(emp_to_remove)
                st.success(f"Employee {emp_to_remove} removed!")
                st.rerun()
        else:
            st.info("No employees added yet. Add some employees to get started!")

def task_management():
    st.header("📋 Task Management")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Add New Task")
        task_desc = st.text_area("Task Description", placeholder="Describe the task...")
        task_duration = st.number_input("Time Required (hours)", min_value=0.1, max_value=24.0, step=0.1, value=1.0)
        
        if st.button("Add Task", type="primary"):
            if task_desc and task_duration > 0:
                employees = db_manager.get_all_employees()
                if employees:
                    # Auto-assign task
                    scheduler = TaskScheduler(db_manager)
                    best_emp = scheduler.find_best_employee(task_duration)
                    
                    if best_emp:
                        # Generate task ID
                        existing_tasks = db_manager.get_all_tasks()
                        task_id = f"TASK_{len(existing_tasks) + 1:03d}"
                        
                        db_manager.add_task(task_id, task_desc, task_duration, best_emp)
                        st.success(f"Task {task_id} assigned to {best_emp}!")
                        st.rerun()
                    else:
                        st.error("No employees available!")
                else:
                    st.error("Please add employees first!")
            else:
                st.error("Please fill in all fields!")
    
    with col2:
        st.subheader("All Tasks")
        tasks = db_manager.get_all_tasks()
        
        if tasks:
            task_data = []
            for task in tasks:
                desc = task['description']
                short_desc = desc[:50] + "..." if len(desc) > 50 else desc
                task_data.append({
                    "Task ID": task['task_id'],
                    "Description": short_desc,
                    "Duration (hrs)": task['duration'],
                    "Assigned To": task['assigned_to'],
                    "Created": task['created_at'][:16]  # Remove seconds
                })
            
            df = pd.DataFrame(task_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No tasks added yet.")

def dashboard():
    st.header("📊 Dashboard")
    
    employees = db_manager.get_all_employees()
    tasks = db_manager.get_all_tasks()
    
    if not employees:
        st.info("Add employees and tasks to see the dashboard.")
        return
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Employees", len(employees))
    
    with col2:
        st.metric("Total Tasks", len(tasks))
    
    with col3:
        available_emp = sum(1 for emp in employees if emp['is_available'])
        st.metric("Available Employees", available_emp)
    
    with col4:
        total_hours = sum(task['duration'] for task in tasks)
        st.metric("Total Task Hours", f"{total_hours:.1f}")
    
    st.markdown("---")
    
    # Employee workload visualization
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Employee Workload Distribution")
        if employees:
            emp_workload = []
            for emp in employees:
                emp_workload.append({
                    "Employee": emp['emp_id'],
                    "Workload": emp['current_workload'],
                    "Available": emp['available_hours']
                })
            
            df = pd.DataFrame(emp_workload)
            st.bar_chart(df.set_index("Employee")[["Workload", "Available"]])
    
    with col2:
        st.subheader("Task Distribution")
        assignments = db_manager.get_task_assignments()
        if assignments:
            task_dist = {emp_id: len(tasks) for emp_id, tasks in assignments.items() if tasks}
            if task_dist:
                st.bar_chart(task_dist)

def task_assignments():
    st.header("📝 Task Assignments")
    
    assignments = db_manager.get_task_assignments()
    
    if not any(tasks for tasks in assignments.values()):
        st.info("No task assignments yet. Add some tasks to see assignments.")
        return
    
    for emp_id, tasks in assignments.items():
        if tasks:
            with st.expander(f"👤 {emp_id} - {len(tasks)} task(s) assigned"):
                for task in tasks:
                    st.write(f"**{task['task_id']}** - {task['description']}")
                    st.write(f"⏱️ Duration: {task['duration']} hours")
                    st.write(f"📅 Created: {task['created_at']}")
                    st.markdown("---")
    
    # Reset functionality
    st.markdown("---")
    st.subheader("⚠️ Danger Zone")
    if st.button("🔄 Reset All Data", type="secondary"):
        if st.button("⚠️ Confirm Reset - This will delete everything!", type="secondary"):
            db_manager.reset_all_data()
            st.success("All data has been reset!")
            st.rerun()

if __name__ == "__main__":
    main()
