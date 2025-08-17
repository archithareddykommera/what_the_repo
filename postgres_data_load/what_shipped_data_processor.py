#!/usr/bin/env python3
"""
What Shipped Data Processor

This script extracts data from JSON file and populates the repo_prs Supabase table
for the "What shipped" UI page. It processes PR data to identify features, calculate risk scores,
and prepare data for the shipping dashboard.

Designed for ETL workflows - by default, it performs incremental updates using upsert operations
to handle new PRs being added to repositories over time.

Usage:
    python what_shipped_data_processor.py [--repo REPO_NAME] [--force-refresh] [--incremental]
    
    --repo REPO_NAME: Process specific repository only
    --force-refresh: Clear existing data and reprocess all PRs
    --incremental: Incremental mode (default) - upsert new/updated PRs
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict, Counter
import argparse
import logging

# Database imports
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('what_shipped_processor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class WhatShippedDataProcessor:
    def __init__(self):
        """Initialize connections to Supabase and load JSON data"""
        self.supabase_client = None
        self.pg_conn = None
        self.json_data = None
        
        # JSON file path - use script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.json_file_path = os.path.join(script_dir, 'pr_data_20250811_235048.json')
        
        # Initialize connections and load JSON data
        self._load_json_data()
        self._init_supabase()
        
    def _load_json_data(self):
        """Load PR data from JSON file"""
        try:
            if not os.path.exists(self.json_file_path):
                raise FileNotFoundError(f"JSON file not found: {self.json_file_path}")
            
            logger.info(f"[INFO] Loading PR data from {self.json_file_path}...")
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            # Handle different JSON structures
            if isinstance(raw_data, dict):
                # If it's a dict, it might have a 'data' key or be a single PR
                if 'data' in raw_data:
                    self.json_data = raw_data['data']
                elif 'prs' in raw_data:
                    self.json_data = raw_data['prs']
                elif 'pull_requests' in raw_data:
                    self.json_data = raw_data['pull_requests']
                else:
                    # Assume it's a single PR object
                    self.json_data = [raw_data]
            elif isinstance(raw_data, list):
                # If it's a list, check if it contains objects with 'pull_requests' key
                if raw_data and isinstance(raw_data[0], dict) and 'pull_requests' in raw_data[0]:
                    # Extract pull_requests from each item in the list
                    all_prs = []
                    for item in raw_data:
                        if isinstance(item, dict) and 'pull_requests' in item:
                            all_prs.extend(item['pull_requests'])
                    self.json_data = all_prs
                else:
                    # If it's already a list of PRs, use it directly
                    self.json_data = raw_data
            else:
                raise ValueError(f"Unexpected JSON structure: {type(raw_data)}")
            
            # Ensure we have a list of dictionaries
            if not isinstance(self.json_data, list):
                raise ValueError(f"Expected list of PRs, got {type(self.json_data)}")
            
            # Validate that each item is a dictionary
            for i, item in enumerate(self.json_data):
                if not isinstance(item, dict):
                    raise ValueError(f"Item {i} is not a dictionary: {type(item)}")
            
            logger.info(f"[SUCCESS] Loaded {len(self.json_data)} PR records from JSON")
            logger.info(f"[DEBUG] Sample PR keys: {list(self.json_data[0].keys()) if self.json_data else 'No data'}")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to load JSON data: {e}")
            raise
    
    def _init_supabase(self):
        """Initialize Supabase connection"""
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
            
            # Clear any proxy environment variables that might interfere
            proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NO_PROXY', 'no_proxy']
            for var in proxy_vars:
                if var in os.environ:
                    del os.environ[var]
            
            self.supabase_client = create_client(supabase_url, supabase_key)
            
            # Also create direct PostgreSQL connection for bulk operations
            db_url = os.getenv('SUPABASE_DB_URL')
            if db_url:
                self.pg_conn = psycopg2.connect(db_url)
                logger.info("[SUCCESS] Connected to Supabase PostgreSQL directly")
            else:
                logger.warning("[WARNING] SUPABASE_DB_URL not set, using Supabase client for database operations")
            
            logger.info("[SUCCESS] Connected to Supabase")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize Supabase: {e}")
            raise
    
    def get_all_repositories(self) -> List[str]:
        """Get list of all repositories from JSON data"""
        try:
            logger.info(f"[DEBUG] JSON data type: {type(self.json_data)}")
            logger.info(f"[DEBUG] JSON data length: {len(self.json_data) if self.json_data else 0}")
            
            if not self.json_data:
                logger.warning("[WARNING] No JSON data available")
                return []
            
            # Debug: Show first item structure
            if self.json_data:
                first_item = self.json_data[0]
                logger.info(f"[DEBUG] First item type: {type(first_item)}")
                logger.info(f"[DEBUG] First item keys: {list(first_item.keys()) if isinstance(first_item, dict) else 'Not a dict'}")
                logger.info(f"[DEBUG] First item repo_name: {first_item.get('repo_name', 'NOT_FOUND') if isinstance(first_item, dict) else 'Not a dict'}")
            
            repo_names = []
            for pr in self.json_data:
                if isinstance(pr, dict):
                    repo_name = pr.get('repo_name', '')
                    if repo_name:
                        repo_names.append(repo_name)
                else:
                    logger.warning(f"[WARNING] Skipping non-dict item: {type(pr)}")
            
            repo_names = list(set(repo_names))  # Remove duplicates
            repo_names.sort()
            
            logger.info(f"[INFO] Found {len(repo_names)} repositories: {repo_names}")
            return repo_names
            
        except Exception as e:
            logger.error(f"[ERROR] Error extracting repositories: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []
    
    def get_pr_data_for_repo(self, repo_name: str) -> List[Dict]:
        """Get all PR data for a specific repository from JSON"""
        try:
            # Filter PRs for the repository
            pr_data = [pr for pr in self.json_data if pr.get('repo_name') == repo_name]
            
            logger.info(f"[INFO] Found {len(pr_data)} PRs for {repo_name}")
            return pr_data
            
        except Exception as e:
            logger.error(f"[ERROR] Error filtering PR data for {repo_name}: {e}")
            return []
    
    def determine_feature_classification(self, pr: Dict) -> Tuple[str, float]:
        """Determine feature classification and confidence for a PR using the 'feature' attribute from JSON"""
        # Use the 'feature' attribute from JSON data
        feature = pr.get('feature', '')
        
        # If feature attribute exists and is not empty, classify as feature
        if feature and feature.strip():
            return 'label-allow', 0.9
        
        # Fallback to title/body analysis if no feature attribute
        title = pr.get('title', '')
        body = pr.get('body', '')
        
        # Handle None values safely
        title = title.lower() if title else ''
        body = body.lower() if body else ''
        
        # Get risk score from pr_risk_assessment
        risk_assessment = pr.get('pr_risk_assessment', {})
        if not risk_assessment:
            risk_assessment = {}
        risk_score = float(risk_assessment.get('risk_score', 0))
        
        # Check title for feature indicators
        feature_keywords = [
            'feature', 'add', 'implement', 'new', 'support', 'enable', 'introduce',
            'create', 'build', 'develop', 'enhance', 'improve', 'upgrade'
        ]
        
        title_has_feature = any(keyword in title for keyword in feature_keywords)
        if title_has_feature:
            return 'title-allow', 0.7
        
        # Check body for feature indicators
        body_has_feature = any(keyword in body for keyword in feature_keywords)
        if body_has_feature:
            return 'title-allow', 0.6
        
        # Low risk PRs might be features
        if risk_score < 3.0:
            return 'unlabeled-include', 0.3
        
        # Default to excluded
        return 'excluded', 0.0
    
    def extract_labels(self, pr: Dict) -> List[str]:
        """Extract labels from PR data"""
        labels = []
        
        # Add risk-based labels from pr_risk_assessment
        risk_assessment = pr.get('pr_risk_assessment', {})
        if not risk_assessment:
            risk_assessment = {}
        risk_score = float(risk_assessment.get('risk_score', 0))
        if risk_score >= 7.0:
            labels.append('high-risk')
        elif risk_score >= 4.0:
            labels.append('medium-risk')
        else:
            labels.append('low-risk')
        
        # Add feature label if applicable
        if pr.get('feature'):
            labels.append('feature')
        
        # Add status-based labels
        if pr.get('is_merged'):
            labels.append('merged')
        elif pr.get('is_closed'):
            labels.append('closed')
        else:
            labels.append('open')
        
        # Add size-based labels
        additions = pr.get('additions', 0)
        deletions = pr.get('deletions', 0)
        total_changes = additions + deletions
        
        if total_changes > 1000:
            labels.append('large-change')
        elif total_changes > 100:
            labels.append('medium-change')
        else:
            labels.append('small-change')
        
        return labels
    
    def get_top_risky_files_from_pr(self, pr: Dict, max_files: int = 5) -> List[Dict]:
        """Get top risky files from PR data"""
        files = pr.get('files', [])
        if not files:
            return []
        
        # Sort by risk score and lines changed
        sorted_files = sorted(
            files,
            key=lambda f: (float(f.get('risk_assessment', {}).get('risk_score_file', 0) if f.get('risk_assessment') else 0), f.get('lines_changed', 0)),
            reverse=True
        )
        
        top_files = []
        for file_change in sorted_files[:max_files]:
            risk_assessment = file_change.get('risk_assessment', {})
            if not risk_assessment:
                risk_assessment = {}
            risk_score = float(risk_assessment.get('risk_score_file', 0))
            if risk_score > 0:  # Only include files with risk scores
                top_files.append({
                    'file_path': file_change.get('filename', ''),
                    'risk': risk_score,
                    'lines': file_change.get('lines_changed', 0),
                    'status': file_change.get('status', ''),
                    'language': file_change.get('language', '')
                })
        
        return top_files
    
    def get_top_risky_files(self, files: List[Dict], max_files: int = 5) -> List[Dict]:
        """Get top risky files for a PR (legacy method)"""
        if not files:
            return []
        
        # Sort by risk score and lines changed
        sorted_files = sorted(
            files,
            key=lambda f: (float(f.get('risk_score_file', 0)), f.get('lines_changed', 0)),
            reverse=True
        )
        
        top_files = []
        for file_change in sorted_files[:max_files]:
            risk_score = float(file_change.get('risk_score_file', 0))
            if risk_score > 0:  # Only include files with risk scores
                top_files.append({
                    'file_path': file_change.get('file_path', ''),
                    'risk': risk_score,
                    'lines': file_change.get('lines_changed', 0),
                    'status': file_change.get('file_status', ''),
                    'language': file_change.get('language', '')
                })
        
        return top_files
    
    def process_pr_for_repo_prs(self, pr: Dict, files: List[Dict] = None) -> Dict:
        """Process a single PR for the repo_prs table"""
        try:
            # Determine feature classification using the 'feature' attribute from JSON
            feature_rule, feature_confidence = self.determine_feature_classification(pr)
            
            # Extract labels
            labels = self.extract_labels(pr)
            
            # Get top risky files from the files array in the PR
            top_risky_files = self.get_top_risky_files_from_pr(pr)
            
            # Convert ISO timestamps to datetime objects
            created_at = pr.get('created_at', '')
            if created_at:
                try:
                    created_at_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_at = created_at_dt.isoformat()
                except:
                    created_at = datetime.now().isoformat()
            
            # Handle merged_at timestamp
            merged_at = None
            if pr.get('merged_at'):
                try:
                    merged_at_dt = datetime.fromisoformat(pr.get('merged_at').replace('Z', '+00:00'))
                    merged_at = merged_at_dt.isoformat()
                except:
                    merged_at = created_at if pr.get('is_merged') else None
            elif pr.get('is_merged'):
                # If marked as merged but no merged_at timestamp, use created_at
                merged_at = created_at
                logger.debug(f"PR #{pr.get('pr_number')}: Using created_at as merged_at (no merged_at timestamp)")
            
            # Extract author from user object
            author = ''
            if pr.get('user') and isinstance(pr['user'], dict):
                author = pr['user'].get('login', '')
            
            # Extract risk assessment data
            risk_assessment = pr.get('pr_risk_assessment', {})
            if not risk_assessment:
                risk_assessment = {}
            risk_score = float(risk_assessment.get('risk_score', 0))
            risk_reasons = risk_assessment.get('risk_reasons', [])
            if not isinstance(risk_reasons, list):
                risk_reasons = []
            
            # Build the record
            record = {
                'repo_name': pr.get('repo_name', ''),
                'pr_number': pr.get('pr_number', 0),
                'title': pr.get('title', ''),
                'pr_summary': pr.get('pr_summary', ''),
                'author': author,
                'created_at': created_at,
                'merged_at': merged_at,
                'is_merged': pr.get('is_merged', False),
                'additions': pr.get('additions', 0),
                'deletions': pr.get('deletions', 0),
                'changed_files': pr.get('changed_files', 0),
                'labels_full': labels,
                'feature_rule': feature_rule,
                'feature_confidence': feature_confidence,
                'risk_score': risk_score,
                'high_risk': risk_score >= 7.0,
                'risk_reasons': risk_reasons,
                'top_risky_files': top_risky_files
            }
            
            return record
            
        except Exception as e:
            logger.error(f"[ERROR] Error processing PR {pr.get('pr_number', 'unknown')}: {e}")
            return None
    
    def upsert_repo_prs(self, records: List[Dict]):
        """Upsert records to the repo_prs table"""
        try:
            if not records:
                return
            
            if self.pg_conn and not self.pg_conn.closed:
                # Use direct PostgreSQL for bulk upsert
                try:
                    with self.pg_conn.cursor() as cursor:
                        for record in records:
                            cursor.execute("""
                                INSERT INTO public.repo_prs 
                                (repo_name, pr_number, title, pr_summary, author, created_at, merged_at,
                                 is_merged, additions, deletions, changed_files, labels_full, feature_rule,
                                 feature_confidence, risk_score, high_risk, risk_reasons, top_risky_files)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (repo_name, pr_number) DO UPDATE SET
                                    title = EXCLUDED.title,
                                    pr_summary = EXCLUDED.pr_summary,
                                    author = EXCLUDED.author,
                                    created_at = EXCLUDED.created_at,
                                    merged_at = EXCLUDED.merged_at,
                                    is_merged = EXCLUDED.is_merged,
                                    additions = EXCLUDED.additions,
                                    deletions = EXCLUDED.deletions,
                                    changed_files = EXCLUDED.changed_files,
                                    labels_full = EXCLUDED.labels_full,
                                    feature_rule = EXCLUDED.feature_rule,
                                    feature_confidence = EXCLUDED.feature_confidence,
                                    risk_score = EXCLUDED.risk_score,
                                    high_risk = EXCLUDED.high_risk,
                                    risk_reasons = EXCLUDED.risk_reasons,
                                    top_risky_files = EXCLUDED.top_risky_files,
                                    updated_at = NOW()
                            """, (
                                record['repo_name'], record['pr_number'], record['title'],
                                record['pr_summary'], record['author'], record['created_at'],
                                record['merged_at'], record['is_merged'], record['additions'],
                                record['deletions'], record['changed_files'], json.dumps(record['labels_full']),
                                record['feature_rule'], record['feature_confidence'], record['risk_score'],
                                record['high_risk'], json.dumps(record['risk_reasons']), json.dumps(record['top_risky_files'])
                            ))
                        self.pg_conn.commit()
                except Exception as db_error:
                    if not self.pg_conn.closed:
                        self.pg_conn.rollback()
                    logger.error(f"[ERROR] Database error in upsert_repo_prs: {db_error}")
                    # Fallback to Supabase client
                    for record in records:
                        self.supabase_client.table('repo_prs').upsert(record).execute()
            else:
                # Use Supabase client
                for record in records:
                    self.supabase_client.table('repo_prs').upsert(record).execute()
            
            logger.info(f"[SUCCESS] Upserted {len(records)} PR records to repo_prs")
            
        except Exception as e:
            logger.error(f"[ERROR] Error upserting repo_prs: {e}")
    
    def process_repository(self, repo_name: str, force_refresh: bool = False):
        """Process a single repository and populate repo_prs table"""
        try:
            logger.info(f"[PROCESSING] Processing repository: {repo_name}")
            
            # For ETL scenarios, we always process but use upsert to handle existing data
            # Only skip if explicitly told to skip and data exists
            if not force_refresh:
                existing_data = self.supabase_client.table('repo_prs').select('*').eq('repo_name', repo_name).limit(1).execute()
                if existing_data.data:
                    logger.info(f"[INFO] Data exists for {repo_name}, will upsert new/updated PRs")
                else:
                    logger.info(f"[INFO] No existing data for {repo_name}, will process all PRs")
            
            # Get PR data from JSON
            logger.info(f"[INFO] Fetching PR data for {repo_name}...")
            pr_data = self.get_pr_data_for_repo(repo_name)
            
            if not pr_data:
                logger.warning(f"[WARNING] No PR data found for {repo_name}")
                return
            
            # Process each PR (no file data from JSON, so we'll skip file processing)
            logger.info(f"[INFO] Processing {len(pr_data)} PRs for {repo_name}...")
            processed_records = []
            
            for pr in pr_data:
                record = self.process_pr_for_repo_prs(pr, [])  # Empty files list since we don't have file data
                if record:
                    processed_records.append(record)
            
            # Upsert to database
            logger.info(f"[INFO] Upserting {len(processed_records)} records to repo_prs...")
            self.upsert_repo_prs(processed_records)
            
            # Log summary statistics
            if processed_records:
                features = sum(1 for r in processed_records if r['feature_rule'] != 'excluded')
                high_risk = sum(1 for r in processed_records if r['high_risk'])
                merged = sum(1 for r in processed_records if r['is_merged'])
                
                # Check if this was incremental processing
                existing_count = len(existing_data.data) if 'existing_data' in locals() and existing_data.data else 0
                if existing_count > 0:
                    logger.info(f"[SUCCESS] Incremental update for {repo_name}: {len(processed_records)} PRs processed (upserted), {features} features, {high_risk} high-risk, {merged} merged")
                else:
                    logger.info(f"[SUCCESS] Initial processing for {repo_name}: {len(processed_records)} PRs, {features} features, {high_risk} high-risk, {merged} merged")
            
        except Exception as e:
            logger.error(f"[ERROR] Error processing repository {repo_name}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
    
    def process_all_repositories(self, force_refresh: bool = False):
        """Process all repositories"""
        try:
            repositories = self.get_all_repositories()
            
            if not repositories:
                logger.warning("[WARNING] No repositories found")
                return
            
            logger.info(f"[PROCESSING] Processing {len(repositories)} repositories...")
            
            total_processed = 0
            for i, repo in enumerate(repositories, 1):
                logger.info(f"[INFO] Processing {i}/{len(repositories)}: {repo}")
                self.process_repository(repo, force_refresh)
                
                # Small delay to avoid overwhelming the systems
                time.sleep(1)
            
            # Get final summary
            try:
                final_count = self.supabase_client.table('repo_prs').select('*', count='exact').execute().count
                logger.info(f"[SUCCESS] All repositories processed successfully. Total PRs in database: {final_count}")
            except Exception as e:
                logger.warning(f"[WARNING] Could not get final count: {e}")
                logger.info("[SUCCESS] All repositories processed successfully")
            
        except Exception as e:
            logger.error(f"[ERROR] Error processing all repositories: {e}")
    
    def close(self):
        """Close all connections"""
        try:
            if self.pg_conn:
                self.pg_conn.close()
                logger.info("[SUCCESS] Closed PostgreSQL connection")
        except Exception as e:
            logger.error(f"[ERROR] Error closing connections: {e}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Process What Shipped data from JSON to Supabase')
    parser.add_argument('--repo', type=str, help='Specific repository to process')
    parser.add_argument('--force-refresh', action='store_true', 
                       help='Force refresh even if data already exists (clears existing data)')
    parser.add_argument('--incremental', action='store_true',
                       help='Incremental mode: only process new/updated PRs (default behavior)')
    
    args = parser.parse_args()
    
    try:
        processor = WhatShippedDataProcessor()
        
        # Log the processing mode
        if args.force_refresh:
            logger.info("[MODE] Force refresh mode: Will clear existing data and reprocess all PRs")
        elif args.incremental:
            logger.info("[MODE] Incremental mode: Will upsert new/updated PRs (default behavior)")
        else:
            logger.info("[MODE] Default mode: Will upsert new/updated PRs (same as incremental)")
        
        if args.repo:
            # Process specific repository
            processor.process_repository(args.repo, args.force_refresh)
        else:
            # Process all repositories
            processor.process_all_repositories(args.force_refresh)
        
        processor.close()
        
    except Exception as e:
        logger.error(f"[ERROR] Fatal error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
