# What the Repo - Data Cleaning & Quality

**How to read this doc**: This document describes data cleaning rules, normalization procedures, and quality assurance processes for the What the Repo application.

## Data Normalization Rules

### Username Normalization

**Rule**: Standardize GitHub usernames across all data sources

**Process**:
1. **Case Normalization**: Convert to lowercase
2. **Whitespace Removal**: Strip leading/trailing whitespace
3. **Special Character Handling**: Preserve GitHub username format (alphanumeric + hyphens)
4. **Duplicate Detection**: Identify and merge duplicate usernames

**Examples**:
```
"John-Doe" → "john-doe"
"  jane_smith  " → "jane_smith"
"USER123" → "user123"
```

**Implementation**:
```python
def normalize_username(username: str) -> str:
    if not username:
        return ""
    return username.lower().strip()
```

### Timestamp Normalization

**Rule**: All timestamps stored in UTC format

**Process**:
1. **Timezone Conversion**: Convert all timestamps to UTC
2. **Format Standardization**: ISO 8601 format with timezone
3. **Unix Timestamp**: Store as Unix timestamp for Milvus
4. **Date Range Validation**: Ensure timestamps are within reasonable bounds

**Examples**:
```
"2024-01-20T10:30:00-05:00" → "2024-01-20T15:30:00Z"
"1705752000" → "2024-01-20T15:30:00Z"
```

**Implementation**:
```python
def normalize_timestamp(timestamp: str) -> str:
    if isinstance(timestamp, str):
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.utcnow().isoformat() + 'Z'
    elif isinstance(timestamp, (int, float)):
        dt = datetime.fromtimestamp(timestamp)
        return dt.utcnow().isoformat() + 'Z'
    return None
```

### File ID Stability

**Rule**: Create stable, unique file identifiers

**Process**:
1. **Repository Prefix**: `{repo_name}:{filename}`
2. **Path Normalization**: Handle different path separators
3. **Case Sensitivity**: Preserve case for file systems
4. **Special Characters**: URL-encode special characters

**Examples**:
```
"src/auth/login.py" → "my-app:src/auth/login.py"
"API/endpoints.py" → "my-app:API/endpoints.py"
"config/db.yml" → "my-app:config/db.yml"
```

**Implementation**:
```python
def create_file_id(repo_name: str, filename: str) -> str:
    return f"{repo_name}:{filename}"
```

## Label Handling

### Feature Classification Labels

**Default Behavior**: `excluded` for unclassified PRs

**Label Hierarchy**:
1. `label-allow` (90% confidence): Explicit feature attribute
2. `title-allow` (70% confidence): Feature keywords in title
3. `title-allow` (60% confidence): Feature keywords in body
4. `unlabeled-include` (30% confidence): Low risk PRs
5. `excluded` (0% confidence): Default fallback

**Feature Keywords**:
```python
feature_keywords = [
    'feature', 'add', 'implement', 'new', 'support', 'enable', 'introduce',
    'create', 'build', 'develop', 'enhance', 'improve', 'upgrade'
]
```

**Implementation**:
```python
def determine_feature_classification(pr: Dict) -> Tuple[str, float]:
    # Check explicit feature attribute first
    if pr.get('feature') and pr.get('feature').strip():
        return 'label-allow', 0.9
    
    # Fallback to content analysis
    title = pr.get('title', '').lower()
    body = pr.get('body', '').lower()
    
    if any(keyword in title for keyword in feature_keywords):
        return 'title-allow', 0.7
    
    if any(keyword in body for keyword in feature_keywords):
        return 'title-allow', 0.6
    
    # Low risk PRs might be features
    risk_score = float(pr.get('risk_score', 0))
    if risk_score < 3.0:
        return 'unlabeled-include', 0.3
    
    return 'excluded', 0.0
```

### Risk Score Labels

**Thresholds**:
- **High Risk**: ≥ 7.0
- **Medium Risk**: ≥ 4.0 and < 7.0
- **Low Risk**: < 4.0

**Label Assignment**:
```python
def assign_risk_label(risk_score: float) -> str:
    if risk_score >= 7.0:
        return 'high-risk'
    elif risk_score >= 4.0:
        return 'medium-risk'
    else:
        return 'low-risk'
```

## Risk Roll-up Formula

### File-Level Risk Aggregation

**Formula**: Weighted average of file risks based on lines changed

```python
def calculate_pr_risk_score(files: List[Dict]) -> float:
    if not files:
        return 0.0
    
    total_lines = sum(f.get('lines_changed', 0) for f in files)
    if total_lines == 0:
        return 0.0
    
    weighted_sum = sum(
        f.get('risk_score', 0) * f.get('lines_changed', 0) 
        for f in files
    )
    
    return weighted_sum / total_lines
```

### Risk Score Calculation

**Components**:
1. **File Complexity**: Lines changed, file type
2. **Content Analysis**: LLM assessment of changes
3. **Context Factors**: Security implications, external dependencies

**Example**:
```python
# File risk assessment
file_risk = {
    'lines_changed': 320,
    'file_type': 'python',
    'security_impact': 'high',
    'external_deps': True,
    'risk_score': 7.2
}

# PR risk aggregation
pr_files = [file_risk, ...]
pr_risk = calculate_pr_risk_score(pr_files)
```

## Edge Cases & Backfills

### Missing Data Handling

**Null Values**:
- **Timestamps**: Use current time or reasonable defaults
- **Usernames**: Skip records with missing authors
- **File Paths**: Skip records with missing file information
- **Risk Scores**: Default to 0.0

**Implementation**:
```python
def handle_missing_data(pr: Dict) -> Dict:
    # Handle missing timestamps
    if not pr.get('created_at'):
        pr['created_at'] = datetime.now().isoformat()
    
    # Handle missing author
    if not pr.get('author'):
        return None  # Skip this PR
    
    # Handle missing risk score
    if not pr.get('risk_score'):
        pr['risk_score'] = 0.0
    
    return pr
```

### Data Type Validation

**Validation Rules**:
1. **Numeric Fields**: Ensure integers/floats, handle string conversion
2. **Boolean Fields**: Convert string booleans to actual booleans
3. **Date Fields**: Validate date format and range
4. **JSON Fields**: Validate JSON structure

**Implementation**:
```python
def validate_data_types(record: Dict) -> Dict:
    # Validate numeric fields
    for field in ['additions', 'deletions', 'changed_files']:
        if field in record:
            try:
                record[field] = int(record[field])
            except (ValueError, TypeError):
                record[field] = 0
    
    # Validate boolean fields
    for field in ['is_merged', 'high_risk']:
        if field in record:
            if isinstance(record[field], str):
                record[field] = record[field].lower() in ['true', '1', 'yes']
    
    # Validate risk score
    if 'risk_score' in record:
        try:
            record['risk_score'] = float(record['risk_score'])
        except (ValueError, TypeError):
            record['risk_score'] = 0.0
    
    return record
```

### Duplicate Detection

**Duplicate Criteria**:
1. **PR Duplicates**: Same `repo_name` + `pr_number`
2. **File Duplicates**: Same `file_id` + `pr_id`
3. **Author Duplicates**: Same `username` with different casing

**Handling Strategy**:
```python
def handle_duplicates(records: List[Dict]) -> List[Dict]:
    seen = set()
    unique_records = []
    
    for record in records:
        # Create unique key
        if 'pr_number' in record:
            key = f"{record['repo_name']}:{record['pr_number']}"
        elif 'file_id' in record:
            key = f"{record['file_id']}:{record['pr_id']}"
        else:
            key = str(record)
        
        if key not in seen:
            seen.add(key)
            unique_records.append(record)
    
    return unique_records
```

## Data Quality Metrics

### Completeness Metrics

**Required Fields**:
- PR: `repo_name`, `pr_number`, `title`, `author`, `created_at`
- File: `file_id`, `repo_name`, `filename`, `pr_id`
- Author: `username`, `display_name`

**Completeness Calculation**:
```python
def calculate_completeness(records: List[Dict], required_fields: List[str]) -> float:
    if not records:
        return 0.0
    
    total_fields = len(records) * len(required_fields)
    filled_fields = sum(
        sum(1 for field in required_fields if record.get(field) is not None)
        for record in records
    )
    
    return filled_fields / total_fields
```

### Consistency Checks

**Cross-Reference Validation**:
1. **PR-File Consistency**: All files belong to valid PRs
2. **Author Consistency**: All PRs have valid authors
3. **Timestamp Consistency**: Created dates before merge dates

**Implementation**:
```python
def validate_consistency(prs: List[Dict], files: List[Dict]) -> Dict:
    issues = []
    
    # Check PR-file consistency
    pr_ids = {pr['pr_id'] for pr in prs}
    for file in files:
        if file['pr_id'] not in pr_ids:
            issues.append(f"File {file['file_id']} references invalid PR {file['pr_id']}")
    
    # Check timestamp consistency
    for pr in prs:
        if pr.get('merged_at') and pr.get('created_at'):
            if pr['merged_at'] < pr['created_at']:
                issues.append(f"PR {pr['pr_number']} merged before creation")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'total_records': len(prs) + len(files)
    }
```

## Backfill Procedures

### Historical Data Backfill

**Process**:
1. **Data Extraction**: Export historical data from GitHub API
2. **Risk Assessment**: Run LLM analysis on historical PRs
3. **Feature Classification**: Apply classification rules to historical data
4. **Batch Processing**: Process in chunks to avoid rate limits

**Backfill Script**:
```python
def backfill_historical_data(start_date: str, end_date: str):
    # Extract historical PRs
    prs = extract_historical_prs(start_date, end_date)
    
    # Process in batches
    batch_size = 100
    for i in range(0, len(prs), batch_size):
        batch = prs[i:i + batch_size]
        
        # Assess risks
        for pr in batch:
            pr['risk_score'] = assess_pr_risk(pr)
        
        # Classify features
        for pr in batch:
            pr['feature_rule'], pr['feature_confidence'] = determine_feature_classification(pr)
        
        # Load to database
        load_pr_batch(batch)
        
        # Rate limiting
        time.sleep(1)
```

### Data Correction

**Correction Types**:
1. **Risk Score Updates**: Re-run risk assessment for specific PRs
2. **Feature Reclassification**: Update feature labels based on new rules
3. **Author Normalization**: Fix username inconsistencies
4. **Timestamp Corrections**: Fix timezone or format issues

**Correction Process**:
```python
def correct_data(record_type: str, record_id: str, corrections: Dict):
    if record_type == 'pr':
        # Update PR record
        update_pr_record(record_id, corrections)
    elif record_type == 'file':
        # Update file record
        update_file_record(record_id, corrections)
    elif record_type == 'author':
        # Update author record
        update_author_record(record_id, corrections)
```

## Gaps & Assumptions

### Missing Quality Controls
- No automated data quality monitoring
- No data lineage tracking
- No data versioning for schema changes
- No automated anomaly detection

### Assumptions
- GitHub API data is authoritative
- LLM risk assessments are consistent
- File paths remain stable over time
- Username changes are infrequent
