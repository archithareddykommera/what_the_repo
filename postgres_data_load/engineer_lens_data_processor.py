#!/usr/bin/env python3
"""
Engineer Lens Data Processor

This script extracts data from JSON files and populates Supabase PostgreSQL tables
for the Engineer Lens UI dashboard. It calculates metrics like throughput, review activity,
contribution heatmaps, and feature analysis for each engineer.

Usage:
    python engineer_lens_data_processor.py --json-file PATH [--repo REPO_NAME] [--window-days 30] [--force-refresh]
    
    --json-file PATH: Path to JSON file with PR data (required)
    --repo REPO_NAME: Process specific repository only
    --window-days DAYS: Metrics window size in days (7, 14, 30, 90, default: 30)
    --force-refresh: Clear existing data and reprocess all
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
import argparse
import logging

# Database imports
import psycopg2
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('engineer_lens_processor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class EngineerLensDataProcessor:
    def __init__(self, json_file_path: str):
        """Initialize connections to Supabase"""
        self.supabase_client = None
        self.pg_conn = None
        
        # JSON file path - must be provided
        if not json_file_path:
            raise ValueError("json_file_path is required")
        
        self.json_file_path = json_file_path
        
        # Initialize connections
        self._init_supabase()
        

    
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
        """Get list of all repositories in the JSON file"""
        try:
            # Read from JSON file
            if not os.path.exists(self.json_file_path):
                logger.error(f"[ERROR] JSON file not found: {self.json_file_path}")
                return []
            
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract PR data from the JSON structure
            pr_data = data.get('pull_requests', [])
            if not pr_data:
                logger.error(f"[ERROR] No pull_requests found in JSON file")
                return []
            
            repo_names = list(set(pr['repo_name'] for pr in pr_data if pr.get('repo_name')))
            repo_names.sort()
            
            logger.info(f"[INFO] Found {len(repo_names)} repositories: {repo_names}")
            return repo_names
            
        except Exception as e:
            logger.error(f"[ERROR] Error fetching repositories: {e}")
            return []
    
    def get_pr_data_for_repo(self, repo_name: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get PR data for a specific repository from JSON file within a date range"""
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            # Read from JSON file
            if not os.path.exists(self.json_file_path):
                logger.error(f"[ERROR] JSON file not found: {self.json_file_path}")
                return []
            
            logger.info(f"[INFO] Reading PR data from {self.json_file_path}")
            
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract PR data from the JSON structure
            pr_data = data.get('pull_requests', [])
            if not pr_data:
                logger.error(f"[ERROR] No pull_requests found in JSON file")
                return []
            
            # Filter PRs for the specific repository and date range
            results = []
            for pr in pr_data:
                # Check if PR belongs to the repository
                if pr.get('repo_name') != repo_name:
                    continue
                
                # Check if PR is within the date range
                created_at = pr.get('created_at')
                if not created_at:
                    continue
                
                # Convert timestamp to int if it's a string
                if isinstance(created_at, str):
                    try:
                        created_at = int(datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp())
                    except:
                        continue
                
                if start_timestamp <= created_at <= end_timestamp:
                    results.append(pr)
            
            logger.info(f"[INFO] Found {len(results)} PRs for {repo_name} in date range")
            
            # Check for duplicates in the raw results
            pr_ids = [r.get('pr_id') or r.get('id') or r.get('number') for r in results]
            unique_pr_ids = set(pr_ids)
            if len(pr_ids) != len(unique_pr_ids):
                logger.warning(f"[WARNING] Duplicate PRs found in JSON results: {len(pr_ids)} total, {len(unique_pr_ids)} unique")
            
            # Debug: Show date range and sample data
            if results:
                logger.info(f"[DEBUG] Date range timestamps: {start_timestamp} to {end_timestamp}")
                logger.info(f"[DEBUG] Sample PR created_at: {results[0].get('created_at')}")
                logger.info(f"[DEBUG] Sample PR merged_at: {results[0].get('merged_at')}")
                logger.info(f"[DEBUG] Sample PR author: {results[0].get('author_name', results[0].get('author', {}).get('login', 'unknown'))}")
            else:
                logger.warning(f"[WARNING] No PRs found in date range for {repo_name}")
                logger.info(f"[DEBUG] Date range timestamps: {start_timestamp} to {end_timestamp}")
            
            return results
            
        except Exception as e:
            logger.error(f"[ERROR] Error fetching PR data for {repo_name}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []
    

    
    def process_authors(self, repo_name: str, pr_data: List[Dict]) -> List[Dict]:
        """Process and upsert authors to the authors table"""
        try:
            # Extract unique authors from PR data
            authors = {}
            
            # Process PR data authors
            for pr in pr_data:
                # Handle different possible author field names
                author_name = None
                if 'author_name' in pr:
                    author_name = pr.get('author_name', '').strip()
                elif 'author' in pr and isinstance(pr['author'], dict):
                    author_name = pr['author'].get('login', '').strip()
                elif 'user' in pr and isinstance(pr['user'], dict):
                    author_name = pr['user'].get('login', '').strip()
                
                if author_name and author_name not in authors:
                    authors[author_name] = {
                        'username': author_name,
                        'display_name': author_name,  # Could be enhanced with GitHub API
                        'avatar_url': f"https://github.com/{author_name}.png"  # Default GitHub avatar
                    }
            
            # Upsert authors to Supabase
            if authors:
                authors_list = list(authors.values())
                
                if self.pg_conn:
                    # Use direct PostgreSQL for bulk upsert
                    try:
                        with self.pg_conn.cursor() as cursor:
                            for author in authors_list:
                                cursor.execute("""
                                    INSERT INTO public.authors (username, display_name, avatar_url)
                                    VALUES (%s, %s, %s)
                                    ON CONFLICT (username) DO UPDATE SET
                                        display_name = EXCLUDED.display_name,
                                        avatar_url = EXCLUDED.avatar_url
                                """, (author['username'], author['display_name'], author['avatar_url']))
                            self.pg_conn.commit()
                    except Exception as db_error:
                        self.pg_conn.rollback()
                        logger.error(f"[ERROR] Database error in process_authors: {db_error}")
                        # Fallback to Supabase client
                        for author in authors_list:
                            self.supabase_client.table('authors').upsert(author).execute()
                else:
                    # Use Supabase client
                    for author in authors_list:
                        self.supabase_client.table('authors').upsert(author).execute()
                
                logger.info(f"[SUCCESS] Processed {len(authors)} authors for {repo_name}")
            
            return list(authors.values())
            
        except Exception as e:
            logger.error(f"[ERROR] Error processing authors for {repo_name}: {e}")
            return []
    
    def calculate_daily_metrics(self, repo_name: str, pr_data: List[Dict], start_date: date, end_date: date) -> List[Dict]:
        """Calculate daily metrics for each author for every calendar day in the date range"""
        try:
            # Get all unique authors from PR data
            all_authors = set()
            for pr in pr_data:
                # Handle different possible author field names
                author = None
                if 'author_name' in pr:
                    author = pr.get('author_name', '').strip()
                elif 'author' in pr and isinstance(pr['author'], dict):
                    author = pr['author'].get('login', '').strip()
                elif 'user' in pr and isinstance(pr['user'], dict):
                    author = pr['user'].get('login', '').strip()
                
                if author:
                    all_authors.add(author)
            
            logger.info(f"[DEBUG] Found {len(all_authors)} unique authors: {sorted(list(all_authors))}")
            
            # Create a complete date range
            current_date = start_date
            all_dates = []
            while current_date <= end_date:
                all_dates.append(current_date)
                current_date += timedelta(days=1)
            
            # Initialize metrics for every author for every day
            daily_metrics = []
            
            for author in all_authors:
                for day in all_dates:
                    daily_metrics.append({
                        'username': author,
                        'repo_name': repo_name,
                        'day': day.isoformat(),
                        'prs_submitted': 0,
                        'prs_merged': 0,
                        'lines_changed': 0,
                        'high_risk_prs': 0,
                        'features_merged': 0
                    })
            
            logger.info(f"[DEBUG] Created {len(daily_metrics)} daily metric records")
            logger.info(f"[DEBUG] Sample daily metric: {daily_metrics[0] if daily_metrics else 'No metrics'}")
            logger.info(f"[DEBUG] Date range: {all_dates[0] if all_dates else 'No dates'} to {all_dates[-1] if all_dates else 'No dates'}")
            
            # Process PR data to populate the metrics
            pr_count_by_author = defaultdict(int)
            pr_count_by_author_date = defaultdict(lambda: defaultdict(int))
            processed_pr_ids = set()  # Track processed PR IDs to avoid duplicates
            
            # Debug: Show sample PR data structure
            if pr_data:
                sample_pr = pr_data[0]
                logger.info(f"[DEBUG] Sample PR structure: {list(sample_pr.keys())}")
                logger.info(f"[DEBUG] Sample PR author_name: {sample_pr.get('author_name')}")
                logger.info(f"[DEBUG] Sample PR author: {sample_pr.get('author')}")
                logger.info(f"[DEBUG] Sample PR user: {sample_pr.get('user')}")
                logger.info(f"[DEBUG] Sample PR is_merged: {sample_pr.get('is_merged')}")
                logger.info(f"[DEBUG] Sample PR merged_at: {sample_pr.get('merged_at')}")
                logger.info(f"[DEBUG] Sample PR additions: {sample_pr.get('additions')}")
                logger.info(f"[DEBUG] Sample PR deletions: {sample_pr.get('deletions')}")
                logger.info(f"[DEBUG] Sample PR feature: {sample_pr.get('feature')}")
                
                # Show more detailed author extraction debugging
                for i, pr in enumerate(pr_data[:5]):
                    logger.info(f"[DEBUG] PR {i+1} author extraction:")
                    logger.info(f"  - author_name: {pr.get('author_name')}")
                    logger.info(f"  - author: {pr.get('author')}")
                    logger.info(f"  - user: {pr.get('user')}")
                    
                    # Test the extraction logic
                    author = None
                    if 'author_name' in pr:
                        author = pr.get('author_name', '').strip()
                    elif 'author' in pr and isinstance(pr['author'], dict):
                        author = pr['author'].get('login', '').strip()
                    elif 'user' in pr and isinstance(pr['user'], dict):
                        author = pr['user'].get('login', '').strip()
                    
                    logger.info(f"  - Extracted author: {author}")
            
            for pr in pr_data:
                # Check for duplicate PRs - use a more robust ID
                pr_id = pr.get('pr_id') or pr.get('id') or pr.get('number')
                if not pr_id:
                    logger.warning(f"[WARNING] PR has no ID, skipping: {pr.get('title', 'unknown')}")
                    continue
                    
                if pr_id in processed_pr_ids:
                    # Don't log every duplicate, just count them
                    continue
                processed_pr_ids.add(pr_id)
                # Handle different possible author field names
                author = None
                if 'author_name' in pr:
                    author = pr.get('author_name', '').strip()
                elif 'author' in pr and isinstance(pr['author'], dict):
                    author = pr['author'].get('login', '').strip()
                elif 'user' in pr and isinstance(pr['user'], dict):
                    author = pr['user'].get('login', '').strip()
                
                if not author:
                    logger.warning(f"[WARNING] Could not extract author from PR: {pr.get('pr_number', 'unknown')}")
                    continue
                
                # Track PR count by author for debugging
                pr_count_by_author[author] += 1
                
                # Debug: Show first few PRs being processed
                if len(processed_pr_ids) <= 5:
                    logger.info(f"[DEBUG] Processing PR {pr_id}: author={author}, is_merged={pr.get('is_merged')}, additions={pr.get('additions')}, deletions={pr.get('deletions')}")
                
                # Convert timestamps to dates
                created_at = pr.get('created_at')
                merged_at = pr.get('merged_at')
                
                # Handle string timestamps
                if isinstance(created_at, str):
                    try:
                        created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).date()
                    except:
                        logger.warning(f"[WARNING] Could not parse created_at timestamp: {created_at}")
                        continue
                elif isinstance(created_at, (int, float)):
                    created_date = datetime.fromtimestamp(created_at).date()
                else:
                    logger.warning(f"[WARNING] Invalid created_at format: {created_at}")
                    continue
                
                merged_date = None
                if merged_at:
                    if isinstance(merged_at, str):
                        try:
                            merged_date = datetime.fromisoformat(merged_at.replace('Z', '+00:00')).date()
                        except:
                            logger.warning(f"[WARNING] Could not parse merged_at timestamp: {merged_at}")
                            merged_date = None
                    elif isinstance(merged_at, (int, float)):
                        merged_date = datetime.fromtimestamp(merged_at).date()
                
                # Validate dates are within our range
                if created_date < start_date or created_date > end_date:
                    logger.warning(f"[WARNING] PR {pr.get('pr_number', 'unknown')} created date {created_date} outside range {start_date} to {end_date}")
                    continue
                
                # Track PR count by author and date for debugging
                pr_count_by_author_date[author][created_date.isoformat()] += 1
                
                # Find the corresponding daily metric record for this author and created date
                metric_found = False
                for metric in daily_metrics:
                    if metric['username'] == author and metric['day'] == created_date.isoformat():
                        # Count submitted PRs
                        metric['prs_submitted'] += 1
                        
                        # Count high risk PRs from submitted PRs using pr_risk_assessment.high_risk flag
                        pr_risk_assessment = pr.get('pr_risk_assessment', {}) or {}
                        high_risk = pr_risk_assessment.get('high_risk', False) if pr_risk_assessment else False
                        if high_risk:
                            metric['high_risk_prs'] += 1
                        
                        # Add lines changed from the PR itself (for all PRs, not just merged ones)
                        additions = pr.get('additions', 0)
                        deletions = pr.get('deletions', 0)
                        lines_changed = additions + deletions
                        metric['lines_changed'] += lines_changed
                        
                        metric_found = True
                        logger.info(f"[DEBUG] Updated submitted metrics for {author} on {created_date}: prs_submitted={metric['prs_submitted']}, high_risk_prs={metric['high_risk_prs']}, lines_changed={metric['lines_changed']}")
                        break
                
                if not metric_found:
                    logger.warning(f"[WARNING] Could not find daily metric for author {author} on date {created_date}")
                    logger.debug(f"[DEBUG] Available metrics for {author}: {[m['day'] for m in daily_metrics if m['username'] == author][:5]}")
                
                # If PR was merged, update the merged date metrics
                if pr.get('is_merged') and merged_date:
                    if merged_date < start_date or merged_date > end_date:
                        logger.warning(f"[WARNING] PR {pr.get('pr_number', 'unknown')} merged date {merged_date} outside range {start_date} to {end_date}")
                        continue
                    
                    metric_found = False
                    for metric in daily_metrics:
                        if metric['username'] == author and metric['day'] == merged_date.isoformat():
                            # Count merged PRs
                            metric['prs_merged'] += 1
                    
                    # Count features (only for merged PRs)
                            if pr.get('feature') and pr.get('feature') is not None:
                                metric['features_merged'] += 1
                            
                            metric_found = True
                            logger.info(f"[DEBUG] Updated merged metrics for {author} on {merged_date}: prs_merged={metric['prs_merged']}, features_merged={metric['features_merged']}")
                            break
                    
                    if not metric_found:
                        logger.warning(f"[WARNING] Could not find daily metric for author {author} on merged date {merged_date}")
                        logger.debug(f"[DEBUG] Available metrics for {author}: {[m['day'] for m in daily_metrics if m['username'] == author][:5]}")
            
            # Note: Lines changed are now calculated from PR data directly, not from file data
            # File data processing removed to avoid double-counting
            
            logger.info(f"[SUCCESS] Calculated daily metrics for {len(daily_metrics)} author-day combinations")
            logger.info(f"[INFO] Date range: {start_date} to {end_date} ({len(all_dates)} days)")
            logger.info(f"[INFO] Authors: {len(all_authors)}")
            
            # Debug: Show PR count by author
            logger.info(f"[DEBUG] Total PRs in data: {len(pr_data)}")
            logger.info(f"[DEBUG] Unique PRs processed: {len(processed_pr_ids)}")
            logger.info(f"[DEBUG] Duplicates skipped: {len(pr_data) - len(processed_pr_ids)}")
            logger.info(f"[DEBUG] PR count by author: {dict(pr_count_by_author)}")
            
            # Debug: Show risk score and feature distribution
            high_risk_count = sum(1 for pr in pr_data if (pr.get('pr_risk_assessment', {}) or {}).get('high_risk', False))
            feature_count = sum(1 for pr in pr_data if pr.get('feature') and pr.get('feature') is not None)
            merged_with_features = sum(1 for pr in pr_data if pr.get('is_merged') and pr.get('feature') and pr.get('feature') is not None)
            
            logger.info(f"[DEBUG] Risk and feature summary:")
            logger.info(f"  - High risk PRs (pr_risk_assessment.high_risk): {high_risk_count}")
            logger.info(f"  - PRs with features: {feature_count}")
            logger.info(f"  - Merged PRs with features: {merged_with_features}")
            
            # Show sample risk scores
            risk_scores = [float(pr.get('risk_score', 0)) for pr in pr_data]
            if risk_scores:
                logger.info(f"[DEBUG] Risk score range: min={min(risk_scores)}, max={max(risk_scores)}, avg={sum(risk_scores)/len(risk_scores):.2f}")
            
            # Show sample features
            features = [pr.get('feature') for pr in pr_data if pr.get('feature') and pr.get('feature') is not None]
            if features:
                logger.info(f"[DEBUG] Sample features: {features[:5]}")
            
            # Debug: Show specific author data if requested
            if 'xinran-waibel' in pr_count_by_author:
                logger.info(f"[DEBUG] xinran-waibel PR count: {pr_count_by_author['xinran-waibel']}")
                logger.info(f"[DEBUG] xinran-waibel PR count by date: {dict(pr_count_by_author_date['xinran-waibel'])}")
                
                # Show xinran-waibel's lines changed calculation
                xinran_metrics = [m for m in daily_metrics if m['username'] == 'xinran-waibel']
                if xinran_metrics:
                    total_lines = sum(m['lines_changed'] for m in xinran_metrics)
                    logger.info(f"[DEBUG] xinran-waibel total lines changed across all days: {total_lines}")
                    
                    # Show individual PRs for xinran-waibel
                    xinran_prs = [pr for pr in pr_data if (pr.get('user', {}).get('login') == 'xinran-waibel' or 
                                                          pr.get('author_name') == 'xinran-waibel' or
                                                          (pr.get('author') and pr.get('author', {}).get('login') == 'xinran-waibel'))]
                    logger.info(f"[DEBUG] xinran-waibel PRs found: {len(xinran_prs)}")
                    for pr in xinran_prs:
                        additions = pr.get('additions', 0)
                        deletions = pr.get('deletions', 0)
                        lines = additions + deletions
                        risk_score = float(pr.get('risk_score', 0))
                        pr_risk_assessment = pr.get('pr_risk_assessment', {}) or {}
                        is_high_risk = pr_risk_assessment.get('high_risk', False) if pr_risk_assessment else False
                        feature = pr.get('feature')
                        is_merged = pr.get('is_merged', False)
                        logger.info(f"[DEBUG] xinran-waibel PR {pr.get('pr_number')}: additions={additions}, deletions={deletions}, total={lines}, risk_score={risk_score}, is_high_risk={is_high_risk}, feature={feature}, merged={is_merged}")
            
            # Debug: Show some sample data
            if daily_metrics:
                # Show first few records for debugging
                sample_metrics = [m for m in daily_metrics if m['prs_submitted'] > 0 or m['prs_merged'] > 0][:3]
                if sample_metrics:
                    logger.info(f"[DEBUG] Sample daily metrics with activity: {sample_metrics}")
                else:
                    logger.info(f"[DEBUG] Sample daily metrics (no activity): {daily_metrics[:3]}")
                
                # Show summary of processed data
                total_prs_submitted = sum(m['prs_submitted'] for m in daily_metrics)
                total_prs_merged = sum(m['prs_merged'] for m in daily_metrics)
                total_lines_changed = sum(m['lines_changed'] for m in daily_metrics)
                total_features_merged = sum(m['features_merged'] for m in daily_metrics)
                
                logger.info(f"[DEBUG] Summary of processed data:")
                logger.info(f"  - Total PRs submitted across all days: {total_prs_submitted}")
                logger.info(f"  - Total PRs merged across all days: {total_prs_merged}")
                logger.info(f"  - Total lines changed across all days: {total_lines_changed}")
                logger.info(f"  - Total features merged across all days: {total_features_merged}")
                
                # Show high risk PRs summary
                total_high_risk = sum(m['high_risk_prs'] for m in daily_metrics)
                logger.info(f"  - Total high risk PRs across all days: {total_high_risk}")
                
                # Show metrics by author
                author_summary = {}
                for metric in daily_metrics:
                    author = metric['username']
                    if author not in author_summary:
                        author_summary[author] = {
                            'prs_submitted': 0,
                            'prs_merged': 0,
                            'lines_changed': 0,
                            'high_risk_prs': 0,
                            'features_merged': 0
                        }
                    author_summary[author]['prs_submitted'] += metric['prs_submitted']
                    author_summary[author]['prs_merged'] += metric['prs_merged']
                    author_summary[author]['lines_changed'] += metric['lines_changed']
                    author_summary[author]['high_risk_prs'] += metric['high_risk_prs']
                    author_summary[author]['features_merged'] += metric['features_merged']
                
                logger.info(f"[DEBUG] Author summary:")
                for author, summary in author_summary.items():
                    if summary['prs_submitted'] > 0 or summary['prs_merged'] > 0:
                        logger.info(f"  - {author}: submitted={summary['prs_submitted']}, merged={summary['prs_merged']}, lines={summary['lines_changed']}, high_risk={summary['high_risk_prs']}, features={summary['features_merged']}")
                
                # Show some sample daily metrics with activity
                active_metrics = [m for m in daily_metrics if m['prs_submitted'] > 0 or m['prs_merged'] > 0]
                logger.info(f"[DEBUG] Days with activity: {len(active_metrics)} out of {len(daily_metrics)} total days")
                if active_metrics:
                    logger.info(f"[DEBUG] Sample active day: {active_metrics[0]}")
            else:
                logger.warning(f"[WARNING] No daily metrics generated for {repo_name}")
                logger.info(f"[DEBUG] PR data count: {len(pr_data)}")
                if pr_data:
                    logger.info(f"[DEBUG] Sample PR: {pr_data[0]}")
            
            return daily_metrics
            
        except Exception as e:
            logger.error(f"[ERROR] Error calculating daily metrics for {repo_name}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []
    
    def calculate_window_metrics(self, repo_name: str, daily_metrics: List[Dict], 
                               window_days, start_date: date, end_date: date) -> List[Dict]:
        """Calculate windowed metrics for a specific window period for each author using daily metrics data"""
        try:
            # Group daily metrics by author
            author_daily = defaultdict(list)
            for metric in daily_metrics:
                author_daily[metric['username']].append(metric)
            
            logger.info(f"[DEBUG] Found {len(author_daily)} authors in daily metrics: {list(author_daily.keys())}")
            
            window_metrics = []
            
            for author, daily_list in author_daily.items():
                # Filter to window period
                if window_days == 'all_time':
                    window_end_date = end_date
                    window_start_date = start_date
                else:
                    window_end_date = end_date
                    window_start_date = end_date - timedelta(days=window_days - 1)
                
                window_daily = [
                    d for d in daily_list 
                    if window_start_date <= datetime.strptime(d['day'], '%Y-%m-%d').date() <= window_end_date
                ]
                
                logger.info(f"[DEBUG] Author {author}: {len(window_daily)} days in {window_days}-day window")
                
                # Aggregate metrics for the window period
                total_prs_submitted = sum(d['prs_submitted'] for d in window_daily)
                total_prs_merged = sum(d['prs_merged'] for d in window_daily)
                total_high_risk_prs = sum(d['high_risk_prs'] for d in window_daily)
                total_lines_changed = sum(d['lines_changed'] for d in window_daily)
                
                # Calculate high risk rate (high_risk_prs / prs_merged)
                high_risk_rate = (total_high_risk_prs / total_prs_merged * 100) if total_prs_merged > 0 else 0
                
                # Convert window_days to integer for database storage
                if window_days == 'all_time':
                    window_days_int = 999  # Special value for all_time
                else:
                    window_days_int = window_days
                
                window_metrics.append({
                    'username': author,
                    'repo_name': repo_name,
                    'window_days': window_days_int,
                    'start_date': window_start_date.isoformat(),
                    'end_date': window_end_date.isoformat(),
                    'prs_submitted': total_prs_submitted,
                    'prs_merged': total_prs_merged,
                    'high_risk_prs': total_high_risk_prs,
                    'high_risk_rate': round(high_risk_rate, 2),
                    'lines_changed': total_lines_changed,
                    'ownership_low_risk_prs': 0  # Placeholder for future metric
                })
            
            logger.info(f"[SUCCESS] Calculated {window_days}-day window metrics for {len(window_metrics)} authors")
            logger.info(f"[INFO] Window period: {window_start_date} to {window_end_date} ({window_days} days)")
            logger.info(f"[DEBUG] Window calculation: end_date={end_date}, window_days={window_days}, start_date={window_start_date}")
            
            # Debug: Show some sample window metrics
            if window_metrics:
                sample_metrics = [m for m in window_metrics if m['prs_submitted'] > 0 or m['prs_merged'] > 0][:3]
                if sample_metrics:
                    logger.info(f"[DEBUG] Sample {window_days}-day window metrics with activity: {sample_metrics}")
                else:
                    logger.info(f"[DEBUG] Sample {window_days}-day window metrics (no activity): {window_metrics[:3]}")
            
            return window_metrics
            
        except Exception as e:
            logger.error(f"[ERROR] Error calculating {window_days}-day window metrics for {repo_name}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []
    
    def calculate_all_window_metrics(self, repo_name: str, daily_metrics: List[Dict], 
                                   start_date: date, end_date: date) -> List[Dict]:
        """Calculate windowed metrics for multiple time periods (7, 15, 30, 60, 90 days, all_time) for each author"""
        try:
            window_periods = [7, 15, 30, 60, 90, 'all_time']
            all_window_metrics = []
            
            for window_days in window_periods:
                logger.info(f"[INFO] Calculating {window_days}-day window metrics...")
                window_metrics = self.calculate_window_metrics(repo_name, daily_metrics, window_days, start_date, end_date)
                all_window_metrics.extend(window_metrics)
            
            logger.info(f"[SUCCESS] Calculated window metrics for all periods: {window_periods}")
            logger.info(f"[INFO] Total window metrics records: {len(all_window_metrics)}")
            
            return all_window_metrics
            
        except Exception as e:
            logger.error(f"[ERROR] Error calculating all window metrics for {repo_name}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []
    
    def calculate_all_file_ownership(self, repo_name: str, pr_data: List[Dict], 
                                   start_date: date, end_date: date) -> List[Dict]:
        """Calculate file ownership percentages for each author for all window periods (7, 15, 30, 60, 90 days, all_time)"""
        try:
            window_periods = [7, 15, 30, 60, 90, 'all_time']
            all_ownership_data = []
            
            for window_days in window_periods:
                logger.info(f"[INFO] Calculating file ownership for {window_days}-day window...")
                ownership_data = self.calculate_file_ownership(repo_name, pr_data, window_days, start_date, end_date)
                all_ownership_data.extend(ownership_data)
            
            logger.info(f"[SUCCESS] Calculated file ownership for all periods: {window_periods}")
            logger.info(f"[INFO] Total file ownership records: {len(all_ownership_data)}")
            
            # Debug: Show breakdown by window period
            window_breakdown = {}
            for ownership in all_ownership_data:
                window_days = ownership['window_days']
                if window_days not in window_breakdown:
                    window_breakdown[window_days] = 0
                window_breakdown[window_days] += 1
            
            logger.info(f"[DEBUG] File ownership breakdown by window period: {window_breakdown}")
            
            return all_ownership_data
            
        except Exception as e:
            logger.error(f"[ERROR] Error calculating all file ownership for {repo_name}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return []
    
    def calculate_file_ownership(self, repo_name: str, pr_data: List[Dict],
                               window_days, start_date: date, end_date: date) -> List[Dict]:
        """Calculate file ownership percentages for each author"""
        try:
            # Filter PR data to window period and merged status
            window_prs = []
            
            for pr in pr_data:
                if not pr.get('is_merged'):
                    continue
                
                # Handle merged_at timestamp conversion
                merged_at = pr.get('merged_at')
                if not merged_at:
                    continue
                
                merged_date = None
                if isinstance(merged_at, str):
                    try:
                        merged_date = datetime.fromisoformat(merged_at.replace('Z', '+00:00')).date()
                    except:
                        continue
                elif isinstance(merged_at, (int, float)):
                    merged_date = datetime.fromtimestamp(merged_at).date()
                else:
                    continue
                
                # Check if merged date is within window
                if window_days == 'all_time':
                    window_end_date = end_date
                    window_start_date = start_date
                else:
                    window_end_date = end_date
                    window_start_date = end_date - timedelta(days=window_days - 1)
                
                if window_start_date <= merged_date <= window_end_date:
                    window_prs.append(pr)
            
            # Group by file and calculate ownership
            file_ownership = defaultdict(lambda: defaultdict(int))
            file_paths = {}
            file_last_touched = {}
            
            logger.info(f"[DEBUG] Processing {len(window_prs)} PRs for file ownership calculation")
            
            # First pass: collect all files and their changes
            all_files = {}  # file_id -> {author -> lines_changed}
            file_paths = {}
            file_last_touched = {}
            
            for pr in window_prs:
                # Try different author field names
                author = None
                if 'author_name' in pr:
                    author = pr.get('author_name', '').strip()
                elif 'author' in pr and isinstance(pr['author'], dict):
                    author = pr['author'].get('login', '').strip()
                elif 'user' in pr and isinstance(pr['user'], dict):
                    author = pr['user'].get('login', '').strip()
                
                if not author:
                    logger.debug(f"[DEBUG] No author found for PR {pr.get('pr_number', 'unknown')}")
                    continue
                
                # Get files from the PR
                files = pr.get('files', [])
                if not files:
                    logger.debug(f"[DEBUG] No files found in PR {pr.get('pr_number', 'unknown')}")
                    continue
                
                logger.debug(f"[DEBUG] PR {pr.get('pr_number', 'unknown')} has {len(files)} files")
                
                # Process each file in the PR
                for file_data in files:
                    filename = file_data.get('filename', '')
                    if not filename:
                        continue
                    
                    # Create unique file_id and use filename as file_path
                    file_id = f"{repo_name}:{filename}"
                    file_path = filename
                    
                    # Get additions and deletions for this specific file
                    additions = file_data.get('additions', 0)
                    deletions = file_data.get('deletions', 0)
                    lines_changed = additions + deletions
                    
                    if lines_changed > 0:  # Only track files with actual changes
                        # Initialize file entry if not exists
                        if file_id not in all_files:
                            all_files[file_id] = {}
                        
                        # Add author's contribution
                        if author not in all_files[file_id]:
                            all_files[file_id][author] = 0
                        all_files[file_id][author] += lines_changed
                        
                        file_paths[file_id] = file_path
                        
                        # Track last touched time for this file
                        merged_at = pr.get('merged_at', 0)
                        merged_timestamp = 0
                        if isinstance(merged_at, str):
                            try:
                                merged_timestamp = datetime.fromisoformat(merged_at.replace('Z', '+00:00')).timestamp()
                            except:
                                merged_timestamp = 0
                        elif isinstance(merged_at, (int, float)):
                            merged_timestamp = merged_at
                        
                        if file_id not in file_last_touched or merged_timestamp > file_last_touched[file_id]:
                            file_last_touched[file_id] = merged_timestamp
            
            # Calculate ownership percentages
            ownership_data = []
            logger.info(f"[DEBUG] Found {len(all_files)} unique files with changes")
            
            for file_id, author_lines in all_files.items():
                total_lines = sum(author_lines.values())
                if total_lines == 0:
                    continue
                
                logger.debug(f"[DEBUG] File {file_id}: {len(author_lines)} authors, {total_lines} total lines")
                
                for author, lines in author_lines.items():
                    ownership_pct = (lines / total_lines) * 100
                    
                    # Convert window_days to integer for database storage
                    if window_days == 'all_time':
                        window_days_int = 999  # Special value for all_time
                        window_end_date = end_date
                        window_start_date = start_date
                    else:
                        window_days_int = window_days
                        window_end_date = end_date
                        window_start_date = end_date - timedelta(days=window_days - 1)
                    
                    ownership_data.append({
                        'username': author,
                        'repo_name': repo_name,
                        'window_days': window_days_int,
                        'start_date': window_start_date.isoformat(),
                        'end_date': window_end_date.isoformat(),
                        'file_id': file_id,
                        'file_path': file_paths.get(file_id, ''),
                        'ownership_pct': round(ownership_pct, 2),
                        'author_lines': lines,
                        'total_lines': total_lines,
                        'last_touched': datetime.fromtimestamp(file_last_touched.get(file_id, 0)).isoformat() if file_last_touched.get(file_id) else None
                    })
            
            logger.info(f"[SUCCESS] Calculated file ownership for {len(ownership_data)} author-file combinations")
            return ownership_data
            
        except Exception as e:
            logger.error(f"[ERROR] Error calculating file ownership for {repo_name}: {e}")
            return []
    
    def process_pr_features(self, repo_name: str, pr_data: List[Dict], 
                          start_date: date, end_date: date) -> List[Dict]:
        """Process PR features and create author PR window data for multiple window periods"""
        try:
            window_periods = [7, 15, 30, 60, 90, 'all_time']
            all_pr_window_data = []
            
            for window_days in window_periods:
                logger.info(f"[INFO] Processing PR features for {window_days}-day window...")
                
                # Calculate window end date and start date
                if window_days == 'all_time':
                    window_end_date = end_date
                    window_start_date = start_date
                else:
                    window_end_date = end_date
                    window_start_date = end_date - timedelta(days=window_days - 1)
                
            # Filter PRs to window period and merged status
                window_prs = []
                
                for pr in pr_data:
                    if not pr.get('is_merged'):
                        continue
                    
                    # Handle merged_at timestamp conversion
                    merged_at = pr.get('merged_at')
                    if not merged_at:
                        continue
                    
                    merged_date = None
                    if isinstance(merged_at, str):
                        try:
                            merged_date = datetime.fromisoformat(merged_at.replace('Z', '+00:00')).date()
                        except:
                            continue
                    elif isinstance(merged_at, (int, float)):
                        merged_date = datetime.fromtimestamp(merged_at).date()
                    else:
                        continue
                    
                    # Check if merged date is within window
                    if window_start_date <= merged_date <= window_end_date:
                        window_prs.append(pr)
                
                logger.info(f"[DEBUG] Found {len(window_prs)} PRs in {window_days}-day window ({window_start_date} to {window_end_date})")
            
            pr_window_data = []
            
            for pr in window_prs:
                # Handle different possible author field names
                author = None
                if 'author_name' in pr:
                    author = pr.get('author_name', '').strip()
                elif 'author' in pr and isinstance(pr['author'], dict):
                    author = pr['author'].get('login', '').strip()
                elif 'user' in pr and isinstance(pr['user'], dict):
                    author = pr['user'].get('login', '').strip()
                
                # Debug: Log author extraction
                if not author:
                    logger.debug(f"[DEBUG] Could not extract author from PR {pr.get('pr_number', 'unknown')}. Available fields: {list(pr.keys())}")
                    if 'author' in pr:
                        logger.debug(f"[DEBUG] Author field content: {pr['author']}")
                    if 'user' in pr:
                        logger.debug(f"[DEBUG] User field content: {pr['user']}")
                    continue
                
                # Determine feature classification
                feature_rule = 'excluded'
                feature_confidence = 0.0
                
                if pr.get('feature') and pr.get('feature') is not None:
                    feature_rule = 'title-allow'
                    feature_confidence = 0.8
                elif 'feature' in pr.get('title', '').lower():
                    feature_rule = 'title-allow'
                    feature_confidence = 0.6
                elif float(pr.get('risk_score', 0)) < 3.0:  # Low risk PRs might be features
                    feature_rule = 'unlabeled-include'
                    feature_confidence = 0.3
                
                # Handle merged_at timestamp for output
                merged_at = pr.get('merged_at')
                merged_at_iso = None
                if isinstance(merged_at, str):
                    try:
                        merged_at_iso = datetime.fromisoformat(merged_at.replace('Z', '+00:00')).isoformat()
                    except:
                        merged_at_iso = merged_at
                elif isinstance(merged_at, (int, float)):
                    merged_at_iso = datetime.fromtimestamp(merged_at).isoformat()
                
                # Convert window_days to integer for database storage
                if window_days == 'all_time':
                    window_days_int = 999  # Special value for all_time
                else:
                    window_days_int = window_days
                
                pr_window_data.append({
                    'username': author,
                    'repo_name': repo_name,
                    'window_days': window_days_int,
                    'start_date': window_start_date.isoformat(),
                    'end_date': window_end_date.isoformat(),
                    'pr_number': pr.get('pr_number', 0),
                    'title': pr.get('title', ''),
                    'pr_summary': pr.get('body', ''),  # Use 'body' field for PR summary
                    'merged_at': merged_at_iso,
                    'risk_score': round(float(pr.get('risk_score', 0)), 2),
                    'high_risk': float(pr.get('risk_score', 0)) >= 7.0,
                    'feature_rule': feature_rule,
                    'feature_confidence': round(float(feature_confidence), 2)
                })
            
                all_pr_window_data.extend(pr_window_data)
                logger.info(f"[INFO] Processed {len(pr_window_data)} PRs for {window_days}-day window")
            
            logger.info(f"[SUCCESS] Processed {len(all_pr_window_data)} total PRs for feature analysis across all windows")
            
            # Debug: Show breakdown by window period
            window_breakdown = {}
            for pr_data in all_pr_window_data:
                window_days = pr_data['window_days']
                if window_days not in window_breakdown:
                    window_breakdown[window_days] = 0
                window_breakdown[window_days] += 1
            
            logger.info(f"[DEBUG] PR window data breakdown by window period: {window_breakdown}")
            return all_pr_window_data
            
        except Exception as e:
            logger.error(f"[ERROR] Error processing PR features for {repo_name}: {e}")
            return []
    
    def upsert_daily_metrics(self, metrics: List[Dict]):
        """Upsert daily metrics to Supabase"""
        try:
            if not metrics:
                return
            
            # Process in smaller batches to avoid connection issues
            batch_size = 50
            for i in range(0, len(metrics), batch_size):
                batch = metrics[i:i + batch_size]
                
                try:
                    if self.pg_conn and not self.pg_conn.closed:
                        # Use direct PostgreSQL for bulk upsert
                        try:
                            with self.pg_conn.cursor() as cursor:
                                for metric in batch:
                                    cursor.execute("""
                                        INSERT INTO public.author_metrics_daily 
                                        (username, repo_name, day, prs_submitted, prs_merged, lines_changed, high_risk_prs, features_merged)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                        ON CONFLICT (username, repo_name, day) DO UPDATE SET
                                            prs_submitted = EXCLUDED.prs_submitted,
                                            prs_merged = EXCLUDED.prs_merged,
                                            lines_changed = EXCLUDED.lines_changed,
                                            high_risk_prs = EXCLUDED.high_risk_prs,
                                            features_merged = EXCLUDED.features_merged,
                                            updated_at = NOW()
                                    """, (
                                        metric['username'], metric['repo_name'], metric['day'],
                                        metric['prs_submitted'], metric['prs_merged'], metric['lines_changed'],
                                        metric['high_risk_prs'], metric['features_merged']
                                    ))
                            self.pg_conn.commit()
                            logger.info(f"[SUCCESS] Upserted batch {i//batch_size + 1} ({len(batch)} metrics)")
                        except Exception as db_error:
                            if not self.pg_conn.closed:
                                self.pg_conn.rollback()
                            logger.error(f"[ERROR] Database error in upsert_daily_metrics batch {i//batch_size + 1}: {db_error}")
                            # Fallback to Supabase client for this batch
                            for metric in batch:
                                try:
                                    # Use upsert with conflict resolution
                                    self.supabase_client.table('author_metrics_daily').upsert(
                                        metric, 
                                        on_conflict='username,repo_name,day'
                                    ).execute()
                                except Exception as e:
                                    logger.error(f"[ERROR] Failed to upsert metric for {metric.get('username', 'unknown')}: {e}")
                    else:
                        # Use Supabase client
                        for metric in batch:
                            try:
                                # Use upsert with conflict resolution
                                self.supabase_client.table('author_metrics_daily').upsert(
                                    metric, 
                                    on_conflict='username,repo_name,day'
                                ).execute()
                            except Exception as e:
                                logger.error(f"[ERROR] Failed to upsert metric for {metric.get('username', 'unknown')}: {e}")
                
                except Exception as batch_error:
                    logger.error(f"[ERROR] Error processing batch {i//batch_size + 1}: {batch_error}")
                    continue
            
            logger.info(f"[SUCCESS] Completed upserting {len(metrics)} daily metrics")
            
        except Exception as e:
            logger.error(f"[ERROR] Error upserting daily metrics: {e}")
    
    def upsert_window_metrics(self, metrics: List[Dict]):
        """Upsert window metrics to Supabase"""
        try:
            if not metrics:
                return
            
            # Process in smaller batches to avoid connection issues
            batch_size = 50
            for i in range(0, len(metrics), batch_size):
                batch = metrics[i:i + batch_size]
                
                try:
                    if self.pg_conn and not self.pg_conn.closed:
                        # Use direct PostgreSQL for bulk upsert
                        try:
                            with self.pg_conn.cursor() as cursor:
                                for metric in batch:
                                    # Debug: Log the metric data being inserted
                                    logger.info(f"[DEBUG] Inserting window metric: username={metric['username']}, window_days={metric['window_days']} (type: {type(metric['window_days'])})")
                                    
                                    cursor.execute("""
                                        INSERT INTO public.author_metrics_window 
                                        (username, repo_name, window_days, start_date, end_date, prs_submitted, prs_merged, 
                                         high_risk_prs, high_risk_rate, lines_changed, ownership_low_risk_prs)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        ON CONFLICT (username, repo_name, window_days, start_date, end_date) DO UPDATE SET
                                            prs_submitted = EXCLUDED.prs_submitted,
                                            prs_merged = EXCLUDED.prs_merged,
                                            high_risk_prs = EXCLUDED.high_risk_prs,
                                            high_risk_rate = EXCLUDED.high_risk_rate,
                                            lines_changed = EXCLUDED.lines_changed,
                                            ownership_low_risk_prs = EXCLUDED.ownership_low_risk_prs,
                                            updated_at = NOW()
                                    """, (
                                        metric['username'], metric['repo_name'], metric['window_days'],
                                        metric['start_date'], metric['end_date'], metric['prs_submitted'],
                                        metric['prs_merged'], metric['high_risk_prs'], metric['high_risk_rate'],
                                        metric['lines_changed'], metric['ownership_low_risk_prs']
                                    ))
                            self.pg_conn.commit()
                            logger.info(f"[SUCCESS] Upserted batch {i//batch_size + 1} ({len(batch)} window metrics)")
                        except Exception as db_error:
                            if not self.pg_conn.closed:
                                self.pg_conn.rollback()
                            logger.error(f"[ERROR] Database error in upsert_window_metrics batch {i//batch_size + 1}: {db_error}")
                            # Fallback to Supabase client for this batch
                            for metric in batch:
                                try:
                                    # Use upsert with conflict resolution
                                    result = self.supabase_client.table('author_metrics_window').upsert(
                                        metric, 
                                        on_conflict='username,repo_name,window_days,start_date,end_date'
                                    ).execute()
                                    logger.info(f"[DEBUG] Supabase upsert result for {metric.get('username', 'unknown')}: {len(result.data) if result.data else 0} rows affected")
                                except Exception as e:
                                    logger.error(f"[ERROR] Failed to upsert window metric for {metric.get('username', 'unknown')}: {e}")
                    else:
                        # Use Supabase client
                        for metric in batch:
                            try:
                                # Use upsert with conflict resolution
                                self.supabase_client.table('author_metrics_window').upsert(
                                    metric, 
                                    on_conflict='username,repo_name,window_days,start_date,end_date'
                                ).execute()
                            except Exception as e:
                                logger.error(f"[ERROR] Failed to upsert window metric for {metric.get('username', 'unknown')}: {e}")
                
                except Exception as batch_error:
                    logger.error(f"[ERROR] Error processing batch {i//batch_size + 1}: {batch_error}")
                    continue
            
            logger.info(f"[SUCCESS] Completed upserting {len(metrics)} window metrics")
            
        except Exception as e:
            logger.error(f"[ERROR] Error upserting window metrics: {e}")
    
    def upsert_file_ownership(self, ownership_data: List[Dict]):
        """Upsert file ownership data to Supabase"""
        try:
            if not ownership_data:
                return
            
            # Process in smaller batches to avoid connection issues
            batch_size = 50
            for i in range(0, len(ownership_data), batch_size):
                batch = ownership_data[i:i + batch_size]
                
                try:
                    if self.pg_conn and not self.pg_conn.closed:
                        # Use direct PostgreSQL for bulk upsert
                        try:
                            with self.pg_conn.cursor() as cursor:
                                for ownership in batch:
                                    cursor.execute("""
                                        INSERT INTO public.author_file_ownership 
                                        (username, repo_name, window_days, start_date, end_date, file_id, file_path,
                                         ownership_pct, author_lines, total_lines, last_touched)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        ON CONFLICT (username, repo_name, window_days, start_date, end_date, file_id) DO UPDATE SET
                                            file_path = EXCLUDED.file_path,
                                            ownership_pct = EXCLUDED.ownership_pct,
                                            author_lines = EXCLUDED.author_lines,
                                            total_lines = EXCLUDED.total_lines,
                                            last_touched = EXCLUDED.last_touched,
                                            updated_at = NOW()
                                    """, (
                                        ownership['username'], ownership['repo_name'], ownership['window_days'],
                                        ownership['start_date'], ownership['end_date'], ownership['file_id'],
                                        ownership['file_path'], ownership['ownership_pct'], ownership['author_lines'],
                                        ownership['total_lines'], ownership['last_touched']
                                    ))
                            self.pg_conn.commit()
                            logger.info(f"[SUCCESS] Upserted batch {i//batch_size + 1} ({len(batch)} file ownership records)")
                        except Exception as db_error:
                            if not self.pg_conn.closed:
                                self.pg_conn.rollback()
                            logger.error(f"[ERROR] Database error in upsert_file_ownership batch {i//batch_size + 1}: {db_error}")
                            # Fallback to Supabase client for this batch
                            for ownership in batch:
                                try:
                                    # Use upsert with conflict resolution
                                    self.supabase_client.table('author_file_ownership').upsert(
                                        ownership, 
                                        on_conflict='username,repo_name,window_days,start_date,end_date,file_id'
                                    ).execute()
                                except Exception as e:
                                    logger.error(f"[ERROR] Failed to upsert file ownership for {ownership.get('username', 'unknown')}: {e}")
                    else:
                        # Use Supabase client
                        for ownership in batch:
                            try:
                                # Use upsert with conflict resolution
                                self.supabase_client.table('author_file_ownership').upsert(
                                    ownership, 
                                    on_conflict='username,repo_name,window_days,start_date,end_date,file_id'
                                ).execute()
                            except Exception as e:
                                logger.error(f"[ERROR] Failed to upsert file ownership for {ownership.get('username', 'unknown')}: {e}")
                
                except Exception as batch_error:
                    logger.error(f"[ERROR] Error processing batch {i//batch_size + 1}: {batch_error}")
                    continue
            
            logger.info(f"[SUCCESS] Completed upserting {len(ownership_data)} file ownership records")
            
        except Exception as e:
            logger.error(f"[ERROR] Error upserting file ownership: {e}")
    
    def upsert_pr_window_data(self, pr_data: List[Dict]):
        """Upsert PR window data to Supabase"""
        try:
            if not pr_data:
                return
            
            # Process in smaller batches to avoid connection issues
            batch_size = 50
            for i in range(0, len(pr_data), batch_size):
                batch = pr_data[i:i + batch_size]
                
                try:
                    if self.pg_conn and not self.pg_conn.closed:
                        # Use direct PostgreSQL for bulk upsert
                        try:
                            with self.pg_conn.cursor() as cursor:
                                for pr in batch:
                                    cursor.execute("""
                                        INSERT INTO public.author_prs_window 
                                        (username, repo_name, window_days, start_date, end_date, pr_number, title,
                                         pr_summary, merged_at, risk_score, high_risk, feature_rule, feature_confidence)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        ON CONFLICT (username, repo_name, window_days, start_date, end_date, pr_number) DO UPDATE SET
                                            title = EXCLUDED.title,
                                            pr_summary = EXCLUDED.pr_summary,
                                            merged_at = EXCLUDED.merged_at,
                                            risk_score = EXCLUDED.risk_score,
                                            high_risk = EXCLUDED.high_risk,
                                            feature_rule = EXCLUDED.feature_rule,
                                            feature_confidence = EXCLUDED.feature_confidence,
                                            updated_at = NOW()
                                    """, (
                                        pr['username'], pr['repo_name'], pr['window_days'],
                                        pr['start_date'], pr['end_date'], pr['pr_number'],
                                        pr['title'], pr['pr_summary'], pr['merged_at'],
                                        pr['risk_score'], pr['high_risk'], pr['feature_rule'],
                                        pr['feature_confidence']
                                    ))
                            self.pg_conn.commit()
                            logger.info(f"[SUCCESS] Upserted batch {i//batch_size + 1} ({len(batch)} PR window records)")
                        except Exception as db_error:
                            if not self.pg_conn.closed:
                                self.pg_conn.rollback()
                            logger.error(f"[ERROR] Database error in upsert_pr_window_data batch {i//batch_size + 1}: {db_error}")
                            # Fallback to Supabase client for this batch
                            for pr in batch:
                                try:
                                    # Use upsert with conflict resolution
                                    self.supabase_client.table('author_prs_window').upsert(
                                        pr, 
                                        on_conflict='username,repo_name,window_days,start_date,end_date,pr_number'
                                    ).execute()
                                except Exception as e:
                                    logger.error(f"[ERROR] Failed to upsert PR window data for {pr.get('username', 'unknown')}: {e}")
                    else:
                        # Use Supabase client
                        for pr in batch:
                            try:
                                # Use upsert with conflict resolution
                                self.supabase_client.table('author_prs_window').upsert(
                                    pr, 
                                    on_conflict='username,repo_name,window_days,start_date,end_date,pr_number'
                                ).execute()
                            except Exception as e:
                                logger.error(f"[ERROR] Failed to upsert PR window data for {pr.get('username', 'unknown')}: {e}")
                
                except Exception as batch_error:
                    logger.error(f"[ERROR] Error processing batch {i//batch_size + 1}: {batch_error}")
                    continue
            
            logger.info(f"[SUCCESS] Completed upserting {len(pr_data)} PR window records")
            
        except Exception as e:
            logger.error(f"[ERROR] Error upserting PR window data: {e}")
    
    def process_repository(self, repo_name: str, window_days: int = 30, data_window_days: int = 365, force_refresh: bool = False, update_table: str = 'all'):
        """Process a single repository and populate all tables"""
        try:
            logger.info(f"[PROCESSING] Processing repository: {repo_name}")
            
            # Calculate date range - use a larger window to get more data
            end_date = date.today()
            # Use the provided data window to capture historical data
            start_date = end_date - timedelta(days=data_window_days)
            
            logger.info(f"[DEBUG] Date range: {start_date} to {end_date} (data window: {data_window_days} days, metrics window: {window_days} days)")
            logger.info(f"[INFO] Update table option: {update_table}")
            
            # Check if data already exists and skip if not forcing refresh (only for full processing)
            if not force_refresh and update_table == 'all':
                existing_data = self.supabase_client.table('author_metrics_window').select('*').eq('repo_name', repo_name).eq('window_days', window_days).execute()
                if existing_data.data:
                    logger.info(f"[SKIPPING] Data already exists for {repo_name}, skipping (use --force-refresh to override)")
                    return
            
            # Get data from JSON file
            logger.info(f"[INFO] Fetching PR data for {repo_name}...")
            pr_data = self.get_pr_data_for_repo(repo_name, datetime.combine(start_date, datetime.min.time()), datetime.combine(end_date, datetime.max.time()))
            
            # Debug: Show data summary
            if pr_data:
                logger.info(f"[DEBUG] PR data summary:")
                logger.info(f"  - Total PRs: {len(pr_data)}")
                logger.info(f"  - Merged PRs: {sum(1 for pr in pr_data if pr.get('is_merged'))}")
                logger.info(f"  - High risk PRs: {sum(1 for pr in pr_data if float(pr.get('risk_score', 0)) >= 7.0)}")
                logger.info(f"  - Feature PRs: {sum(1 for pr in pr_data if pr.get('feature') and pr.get('feature') is not None)}")
                
                # Convert string timestamps to datetime for date range calculation
                created_dates = []
                for pr in pr_data:
                    created_at = pr.get('created_at')
                    if isinstance(created_at, str):
                        try:
                            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            created_dates.append(dt)
                        except:
                            continue
                    elif isinstance(created_at, (int, float)):
                        created_dates.append(datetime.fromtimestamp(created_at))
                
                if created_dates:
                    logger.info(f"  - Date range: {min(created_dates).date()} to {max(created_dates).date()}")
                else:
                    logger.info(f"  - Date range: Unable to determine")
            

            
            if not pr_data:
                logger.warning(f"[WARNING] No PR data found for {repo_name}")
                return
            
            # Process authors
            if update_table in ['authors', 'all']:
                logger.info(f"[AUTHORS] Processing authors for {repo_name}...")
                authors = self.process_authors(repo_name, pr_data)
                logger.info(f"[AUTHORS] Successfully processed {len(authors)} authors for {repo_name}")
            elif update_table == 'authors':
                logger.info(f"[AUTHORS] Authors-only mode: skipping other table processing")
            
            # Calculate daily metrics
            if update_table in ['author_metrics_daily', 'all']:
                logger.info(f"[CALCULATING] Calculating daily metrics for {repo_name}...")
                daily_metrics = self.calculate_daily_metrics(repo_name, pr_data, start_date, end_date)
                self.upsert_daily_metrics(daily_metrics)
            elif update_table in ['author_metrics_window', 'author_file_ownership', 'author_prs_window']:
                # For table updates that need daily metrics, load existing ones
                logger.info(f"[INFO] Loading existing daily metrics for {repo_name}...")
                daily_metrics = self.get_existing_daily_metrics(repo_name, start_date, end_date)
            else:
                # For authors-only updates, we don't need daily metrics
                daily_metrics = []
            
            # Only calculate daily metrics from raw data for window calculations when needed
            if update_table in ['author_metrics_window', 'all'] and update_table != 'author_metrics_daily' and daily_metrics:
                logger.info(f"[INFO] Calculating daily metrics from raw data for window calculations...")
                daily_metrics = self.calculate_daily_metrics(repo_name, pr_data, start_date, end_date)
            
            # Calculate window metrics for all periods (7, 15, 30, 60, 90 days, all_time)
            if update_table in ['author_metrics_window', 'all']:
                logger.info(f"[INFO] Calculating window metrics for all periods for {repo_name}...")
                
                if daily_metrics:
                    logger.info(f"[DEBUG] Using {len(daily_metrics)} daily metrics records for window calculation")
                    
                    # Debug: Show what authors we have in daily metrics
                    unique_authors = set(metric['username'] for metric in daily_metrics)
                    logger.info(f"[DEBUG] Authors in daily metrics: {sorted(list(unique_authors))}")
                    
                    # Show sample of daily metrics to verify data quality
                    sample_metrics = [m for m in daily_metrics if m['prs_submitted'] > 0 or m['prs_merged'] > 0][:3]
                    if sample_metrics:
                        logger.info(f"[DEBUG] Sample daily metrics with activity: {sample_metrics}")
                else:
                    logger.info(f"[INFO] No daily metrics available for window calculations")
                
                window_metrics = self.calculate_all_window_metrics(repo_name, daily_metrics, start_date, end_date)
                self.upsert_window_metrics(window_metrics)
            
            # Calculate file ownership for all window periods (using PR data for file information)
            if update_table in ['author_file_ownership', 'all']:
                logger.info(f"[FILES] Calculating file ownership for all window periods for {repo_name}...")
                ownership_data = self.calculate_all_file_ownership(repo_name, pr_data, start_date, end_date)
                self.upsert_file_ownership(ownership_data)
            
            # Process PR features
            if update_table in ['author_prs_window', 'all']:
                logger.info(f"[FEATURES] Processing PR features for {repo_name}...")
                pr_window_data = self.process_pr_features(repo_name, pr_data, start_date, end_date)
                self.upsert_pr_window_data(pr_window_data)
            
            logger.info(f"[SUCCESS] Successfully processed {repo_name}")
            
        except Exception as e:
            logger.error(f"[ERROR] Error processing repository {repo_name}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
    
    def get_existing_daily_metrics(self, repo_name: str, start_date: date, end_date: date) -> List[Dict]:
        """Get existing daily metrics from the database"""
        try:
            # Query existing daily metrics from the database
            result = self.supabase_client.table('author_metrics_daily').select('*').eq('repo_name', repo_name).gte('day', start_date.isoformat()).lte('day', end_date.isoformat()).execute()
            
            if result.data:
                logger.info(f"[INFO] Loaded {len(result.data)} existing daily metrics for {repo_name}")
                
                # Debug: Show unique authors in the daily metrics
                unique_authors = set(metric['username'] for metric in result.data)
                logger.info(f"[DEBUG] Found {len(unique_authors)} unique authors in daily metrics: {sorted(list(unique_authors))}")
                
                # Debug: Show date range of the data
                dates = [metric['day'] for metric in result.data]
                if dates:
                    logger.info(f"[DEBUG] Daily metrics date range: {min(dates)} to {max(dates)}")
                
                return result.data
            else:
                logger.warning(f"[WARNING] No existing daily metrics found for {repo_name}")
                return []
                
        except Exception as e:
            logger.error(f"[ERROR] Error loading existing daily metrics for {repo_name}: {e}")
            return []
    
    def process_all_repositories(self, window_days: int = 30, data_window_days: int = 365, force_refresh: bool = False, update_table: str = 'all'):
        """Process all repositories"""
        try:
            repositories = self.get_all_repositories()
            
            if not repositories:
                logger.warning("[WARNING] No repositories found")
                return
            
            logger.info(f"[PROCESSING] Processing {len(repositories)} repositories...")
            
            for i, repo in enumerate(repositories, 1):
                logger.info(f"[INFO] Processing {i}/{len(repositories)}: {repo}")
                self.process_repository(repo, window_days, data_window_days, force_refresh, update_table)
                
                # Small delay to avoid overwhelming the systems
                time.sleep(1)
            
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
    parser = argparse.ArgumentParser(description='Process Engineer Lens data from JSON to Supabase')
    parser.add_argument('--json-file', type=str, required=True,
                       help='Path to JSON file with PR data')
    parser.add_argument('--repo', type=str, help='Specific repository to process')
    parser.add_argument('--window-days', type=int, default=30, choices=[7, 14, 30, 90], 
                       help='Metrics window size in days (default: 30)')
    parser.add_argument('--data-window-days', type=int, default=365, 
                       help='Data collection window in days (default: 365)')
    parser.add_argument('--force-refresh', action='store_true', 
                       help='Force refresh even if data already exists')
    parser.add_argument('--update-table', type=str, choices=['authors', 'author_metrics_daily', 'author_metrics_window', 'author_prs_window', 'author_file_ownership', 'all'],
                       help='Update specific table(s) only. Options: authors, author_metrics_daily, author_metrics_window, author_prs_window, author_file_ownership, all')
    
    args = parser.parse_args()
    
    try:
        processor = EngineerLensDataProcessor(json_file_path=args.json_file)
        
        if args.repo:
            # Process specific repository
            processor.process_repository(args.repo, args.window_days, args.data_window_days, args.force_refresh, args.update_table or 'all')
        else:
            # Process all repositories
            processor.process_all_repositories(args.window_days, args.data_window_days, args.force_refresh, args.update_table or 'all')
        
        processor.close()
        
    except Exception as e:
        logger.error(f"[ERROR] Fatal error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
