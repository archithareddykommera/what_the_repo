#!/usr/bin/env python3
"""
Time parsing module for natural language queries.
Converts time expressions to epoch timestamps.
"""

import re
from datetime import datetime, timedelta, date
from typing import Tuple, Optional
import calendar

def parse_time(query: str) -> Tuple[int, int]:
    """
    Parse time expressions from natural language queries.
    
    Args:
        query: Natural language query string
        
    Returns:
        Tuple of (start_epoch, end_epoch) timestamps
    """
    query_lower = query.lower()
    
    # Check for time expressions first (priority over file-specific detection)
    if has_time_expression(query_lower):
        # Extract time expressions
        time_expr = extract_time_expression(query_lower)
        if time_expr:
            # Parse the time expression
            start_time, end_time = parse_time_expression(time_expr)
            
            # Convert to epoch timestamps
            start_epoch = int(start_time.timestamp())
            end_epoch = int(end_time.timestamp())
            
            print(f"⏰ Time Parsing Results:")
            print(f"   Query: '{query}'")
            print(f"   Start time: {start_time} ({start_epoch})")
            print(f"   End time: {end_time} ({end_epoch})")
            print(f"   Duration: {end_time - start_time}")
            
            return start_epoch, end_epoch
    
    # If no time expression found, default to all time for comprehensive search
    return get_all_time_window()

def has_time_expression(query: str) -> bool:
    """Check if query contains time-related keywords"""
    # Use word boundaries to avoid false matches
    import re
    
    time_patterns = [
        r'\blast\b',  # last week, last month, etc.
        r'\byesterday\b',
        r'\btoday\b',
        r'\bthis week\b',
        r'\bthis month\b',
        r'\bthis year\b',
        r'\bin\b',  # in July 2025
        r'\bduring\b',
        r'\bsince\b',
        r'\bfrom\b',
        r'\bto\b',
        r'\bbetween\b',
        r'\bjanuary\b', r'\bfebruary\b', r'\bmarch\b', r'\bapril\b', r'\bmay\b', r'\bjune\b',
        r'\bjuly\b', r'\baugust\b', r'\bseptember\b', r'\boctober\b', r'\bnovember\b', r'\bdecember\b',
        r'\bjan\b', r'\bfeb\b', r'\bmar\b', r'\bapr\b', r'\bjun\b', r'\bjul\b', r'\baug\b', r'\bsep\b', r'\boct\b', r'\bnov\b', r'\bdec\b'
    ]
    
    return any(re.search(pattern, query.lower()) for pattern in time_patterns)

def extract_time_expression(query: str) -> Optional[str]:
    """Extract time expression from query"""
    # Patterns for time expressions
    patterns = [
        r'last\s+(\d+)\s+(day|week|month|year)s?',
        r'last\s+(one|two|three|four|five|six|seven|eight|nine|ten)\s+(day|week|month|year)s?',
        r'last\s+(day|week|month|year)',
        r'yesterday',
        r'today',
        r'this\s+(week|month|year)',
        r'in\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}',
        r'in\s+(jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}',
        r'(\d{1,2})/(\d{1,2})/(\d{4})',
        r'(\d{4})-(\d{1,2})-(\d{1,2})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(0)
    
    return None

def parse_time_expression(time_expr: str) -> Tuple[datetime, datetime]:
    """Parse time expression and return start and end datetime objects"""
    time_expr_lower = time_expr.lower()
    now = datetime.now()
    
    # Last N days/weeks/months/years
    if time_expr_lower.startswith('last'):
        return parse_last_expression(time_expr_lower, now)
    
    # Yesterday
    elif time_expr_lower == 'yesterday':
        yesterday = now - timedelta(days=1)
        start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_time, end_time
    
    # Today
    elif time_expr_lower == 'today':
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_time, end_time
    
    # This week/month/year
    elif time_expr_lower.startswith('this'):
        return parse_this_expression(time_expr_lower, now)
    
    # Month and year (e.g., "in July 2025")
    elif time_expr_lower.startswith('in'):
        return parse_month_year_expression(time_expr_lower)
    
    # Date formats
    elif '/' in time_expr or '-' in time_expr:
        return parse_date_expression(time_expr)
    
    # Default fallback
    return get_default_time_window_datetime()

def parse_last_expression(time_expr: str, now: datetime) -> Tuple[datetime, datetime]:
    """Parse 'last N days/weeks/months/years' expressions"""
    # Extract number and unit - handle both digits and written numbers
    match = re.search(r'last\s+(\d+)\s+(day|week|month|year)s?', time_expr)
    if not match:
        # Try written numbers
        match = re.search(r'last\s+(one|two|three|four|five|six|seven|eight|nine|ten)\s+(day|week|month|year)s?', time_expr)
        if not match:
            # Try "last week", "last month", etc. (no number)
            match = re.search(r'last\s+(day|week|month|year)s?', time_expr)
            if not match:
                return get_default_time_window_datetime()
            number = 1
            unit = match.group(1)
        else:
            number_str = match.group(1)
            unit = match.group(2)
            
            # Convert written numbers to digits
            word_to_number = {
                'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
            }
            number = word_to_number.get(number_str.lower(), 1)
    else:
        number_str = match.group(1)
        unit = match.group(2)
        number = int(number_str)
    
    # Calculate start time based on unit
    if unit == 'day':
        start_time = now - timedelta(days=number)
    elif unit == 'week':
        start_time = now - timedelta(weeks=number)
    elif unit == 'month':
        # Approximate month as 30 days
        start_time = now - timedelta(days=number * 30)
    elif unit == 'year':
        start_time = now - timedelta(days=number * 365)
    else:
        return get_default_time_window_datetime()
    
    # Set end time to now
    end_time = now
    
    return start_time, end_time

def parse_this_expression(time_expr: str, now: datetime) -> Tuple[datetime, datetime]:
    """Parse 'this week/month/year' expressions"""
    if 'week' in time_expr:
        # Start of current week (Monday)
        days_since_monday = now.weekday()
        start_time = now - timedelta(days=days_since_monday)
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now
    elif 'month' in time_expr:
        # Start of current month
        start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_time = now
    elif 'year' in time_expr:
        # Start of current year
        start_time = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_time = now
    else:
        return get_default_time_window_datetime()
    
    return start_time, end_time

def parse_month_year_expression(time_expr: str) -> Tuple[datetime, datetime]:
    """Parse 'in Month Year' expressions"""
    month_names = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    # Extract month and year
    match = re.search(r'in\s+(\w+)\s+(\d{4})', time_expr)
    if not match:
        return get_default_time_window_datetime()
    
    month_name = match.group(1).lower()
    year = int(match.group(2))
    
    if month_name not in month_names:
        return get_default_time_window_datetime()
    
    month = month_names[month_name]
    
    # Start of month
    start_time = datetime(year, month, 1, 0, 0, 0)
    
    # End of month
    last_day = calendar.monthrange(year, month)[1]
    end_time = datetime(year, month, last_day, 23, 59, 59)
    
    return start_time, end_time

def parse_date_expression(date_expr: str) -> Tuple[datetime, datetime]:
    """Parse date expressions like MM/DD/YYYY or YYYY-MM-DD"""
    # Try MM/DD/YYYY format
    match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_expr)
    if match:
        month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        start_time = datetime(year, month, day, 0, 0, 0)
        end_time = datetime(year, month, day, 23, 59, 59)
        return start_time, end_time
    
    # Try YYYY-MM-DD format
    match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_expr)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        start_time = datetime(year, month, day, 0, 0, 0)
        end_time = datetime(year, month, day, 23, 59, 59)
        return start_time, end_time
    
    return get_default_time_window_datetime()

def get_default_time_window() -> Tuple[int, int]:
    """Get default time window (last 14 days) as epoch timestamps"""
    start_time, end_time = get_default_time_window_datetime()
    return int(start_time.timestamp()), int(end_time.timestamp())

def get_default_time_window_datetime() -> Tuple[datetime, datetime]:
    """Get default time window (last 14 days) as datetime objects"""
    now = datetime.now()
    start_time = now - timedelta(days=14)
    return start_time, now

def is_file_specific_query(query: str) -> bool:
    """Check if query is asking for a specific file (no time constraint needed)"""
    file_patterns = [
        r'show\s+changes?\s+in\s+[a-zA-Z0-9_.-]+',
        r'changes?\s+to\s+[a-zA-Z0-9_.-]+',
        r'[a-zA-Z0-9_.-]+\.(py|js|java|cpp|c|h|ts|jsx|tsx|md|txt|json|yaml|yml)$'
    ]
    
    return any(re.search(pattern, query) for pattern in file_patterns)

def get_all_time_window() -> Tuple[int, int]:
    """Get a very wide time window (last 5 years) for comprehensive searches"""
    start_time, end_time = get_all_time_window_datetime()
    return int(start_time.timestamp()), int(end_time.timestamp())

def get_all_time_window_datetime() -> Tuple[datetime, datetime]:
    """Get a very wide time window (last 5 years) as datetime objects"""
    now = datetime.now()
    start_time = now - timedelta(days=1825)  # 5 years
    return start_time, now

def is_author_specific_query(query: str) -> bool:
    """Check if query is asking about a specific author"""
    author_patterns = [
        r'changes?\s+(made|done)\s+by\s+[a-zA-Z0-9_-]+',
        r'prs?\s+(by|from)\s+[a-zA-Z0-9_-]+',
        r'[a-zA-Z0-9_-]+\s+(prs?|changes?|commits?)',
        r'what\s+did\s+[a-zA-Z0-9_-]+\s+do'
    ]
    
    return any(re.search(pattern, query) for pattern in author_patterns)

def get_author_default_time_window() -> Tuple[int, int]:
    """Get default time window for author queries (last 3 months) as epoch timestamps"""
    start_time, end_time = get_author_default_time_window_datetime()
    return int(start_time.timestamp()), int(end_time.timestamp())

def get_author_default_time_window_datetime() -> Tuple[datetime, datetime]:
    """Get default time window for author queries (last 3 months) as datetime objects"""
    now = datetime.now()
    start_time = now - timedelta(days=90)  # 3 months
    return start_time, now

def is_risk_related_query(query: str) -> bool:
    """Check if query is asking about risk-related information"""
    risk_patterns = [
        r'\b(riskiest|most\s+risky|high\s+risk)\b',
        r'\b(risk|vulnerability|security)\b',
        r'\b(dangerous|critical|sensitive)\b'
    ]
    
    return any(re.search(pattern, query.lower()) for pattern in risk_patterns)

def get_risk_default_time_window() -> Tuple[int, int]:
    """Get default time window for risk queries (last 2 years) as epoch timestamps"""
    start_time, end_time = get_risk_default_time_window_datetime()
    return int(start_time.timestamp()), int(end_time.timestamp())

def get_risk_default_time_window_datetime() -> Tuple[datetime, datetime]:
    """Get default time window for risk queries (last 2 years) as datetime objects"""
    now = datetime.now()
    start_time = now - timedelta(days=730)  # 2 years
    return start_time, now
