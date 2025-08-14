#!/usr/bin/env python3
"""
Engineer Lens Data Processor

This script extracts data from Milvus collections and populates Supabase PostgreSQL tables
for the Engineer Lens UI dashboard. It calculates metrics like throughput, review activity,
contribution heatmaps, and feature analysis for each engineer.

Usage:
    python engineer_lens_data_processor.py [--repo REPO_NAME] [--window-days 30] [--force-refresh]
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

# Database and vector store imports
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from pymilvus import connections, Collection, utility
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
    def __init__(self):
        """Initialize connections to Milvus and Supabase"""
        self.milvus_collection = None
        self.file_collection = None
        self.supabase_client = None
        self.pg_conn = None
        
        # Configuration - define these before initializing connections
        self.pr_collection_name = os.getenv('PR_COLLECTION_NAME', 'pr_index_what_the_repo')
        self.file_collection_name = os.getenv('FILE_COLLECTION_NAME', 'file_changes_what_the_repo')
        
        # Initialize connections
        self._init_milvus()
        self._init_supabase()
        
    def _init_milvus(self):
        """Initialize Milvus connection"""
        try:
            milvus_url = os.getenv('MILVUS_URL')
            milvus_token = os.getenv('MILVUS_TOKEN')
            
            if not milvus_url or not milvus_token:
                raise ValueError("MILVUS_URL and MILVUS_TOKEN environment variables are required")
            
            connections.connect(
                alias="default",
                uri=milvus_url,
                token=milvus_token
            )
            
            # Load PR collection
            if not utility.has_collection(self.pr_collection_name):
                raise ValueError(f"Collection '{self.pr_collection_name}' does not exist")
            
            self.milvus_collection = Collection(self.pr_collection_name)
            self.milvus_collection.load()
            
            # Load file collection if it exists
            if utility.has_collection(self.file_collection_name):
                self.file_collection = Collection(self.file_collection_name)
                self.file_collection.load()
                logger.info(f"[SUCCESS] Loaded file collection: {self.file_collection_name}")
            
            logger.info(f"[SUCCESS] Connected to Milvus collection: {self.pr_collection_name}")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize Milvus: {e}")
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
        """Get list of all repositories in the Milvus collection"""
        try:
            results = self.milvus_collection.query(
                expr="",
                output_fields=["repo_name"],
                limit=10000
            )
            
            repo_names = list(set(result['repo_name'] for result in results if result.get('repo_name')))
            repo_names.sort()
            
            logger.info(f"[INFO] Found {len(repo_names)} repositories: {repo_names}")
            return repo_names
            
        except Exception as e:
            logger.error(f"[ERROR] Error fetching repositories: {e}")
            return []
    
    def get_pr_data_for_repo(self, repo_name: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get PR data for a specific repository within a date range"""
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            # Query PRs within the date range
            expr = f'repo_name == "{repo_name}" and created_at >= {start_timestamp} and created_at <= {end_timestamp}'
            
            results = self.milvus_collection.query(
                expr=expr,
                output_fields=[
                    "pr_id", "pr_number", "title", "body", "author_name", 
                    "created_at", "merged_at", "status", "repo_name", 
                    "is_merged", "is_closed", "feature", "pr_summary", 
                    "risk_score", "risk_band", "risk_reasons", 
                    "additions", "deletions", "changed_files"
                ],
                limit=10000
            )
            
            logger.info(f"[INFO] Found {len(results)} PRs for {repo_name} in date range")
            
            # Debug: Show date range and sample data
            if results:
                logger.info(f"[DEBUG] Date range timestamps: {start_timestamp} to {end_timestamp}")
                logger.info(f"[DEBUG] Sample PR created_at: {results[0].get('created_at')}")
                logger.info(f"[DEBUG] Sample PR merged_at: {results[0].get('merged_at')}")
            else:
                logger.warning(f"[WARNING] No PRs found in date range for {repo_name}")
                logger.info(f"[DEBUG] Date range timestamps: {start_timestamp} to {end_timestamp}")
            
            return results
            
        except Exception as e:
            logger.error(f"[ERROR] Error fetching PR data for {repo_name}: {e}")
            return []
    
    def get_file_data_for_repo(self, repo_name: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get file change data for a specific repository within a date range"""
        if not self.file_collection:
            logger.warning("[WARNING] File collection not available")
            return []
        
        try:
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            # Query file changes within the date range
            expr = f'repo_name == "{repo_name}" and merged_at >= {start_timestamp} and merged_at <= {end_timestamp}'
            
            results = self.file_collection.query(
                expr=expr,
                output_fields=[
                    "file_id", "file_path", "file_status", "language", 
                    "additions", "deletions", "lines_changed", "ai_summary", 
                    "risk_score_file", "high_risk_flag", "pr_id", "author_name",
                    "merged_at"
                ],
                limit=10000
            )
            
            logger.info(f"[INFO] Found {len(results)} file changes for {repo_name} in date range")
            return results
            
        except Exception as e:
            logger.error(f"[ERROR] Error fetching file data for {repo_name}: {e}")
            return []
    
    def process_authors(self, repo_name: str, pr_data: List[Dict], file_data: List[Dict] = None) -> List[Dict]:
        """Process and upsert authors to the authors table"""
        try:
            # Extract unique authors from both PR and file data
            authors = {}
            
            # Process PR data authors
            for pr in pr_data:
                author_name = pr.get('author_name', '').strip()
                if author_name and author_name not in authors:
                    authors[author_name] = {
                        'username': author_name,
                        'display_name': author_name,  # Could be enhanced with GitHub API
                        'avatar_url': f"https://github.com/{author_name}.png"  # Default GitHub avatar
                    }
            
            # Process file data authors if available
            if file_data:
                for file_change in file_data:
                    author_name = file_change.get('author_name', '').strip()
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
    
    def calculate_daily_metrics(self, repo_name: str, pr_data: List[Dict], file_data: List[Dict]) -> List[Dict]:
        """Calculate daily metrics for each author"""
        try:
            # Group data by author and date
            daily_metrics = defaultdict(lambda: defaultdict(lambda: {
                'prs_submitted': 0,
                'prs_merged': 0,
                'lines_changed': 0,
                'high_risk_prs': 0,
                'features_merged': 0
            }))
            
            # Process PR data
            for pr in pr_data:
                author = pr.get('author_name', '').strip()
                if not author:
                    continue
                
                # Convert timestamp to date
                created_date = datetime.fromtimestamp(pr.get('created_at', 0)).date()
                merged_date = None
                if pr.get('merged_at'):
                    merged_date = datetime.fromtimestamp(pr.get('merged_at', 0)).date()
                
                # Count submitted PRs
                daily_metrics[author][created_date]['prs_submitted'] += 1
                
                # Count merged PRs
                if pr.get('is_merged') and merged_date:
                    daily_metrics[author][merged_date]['prs_merged'] += 1
                    
                    # Count high risk PRs (only for merged PRs)
                    risk_score = float(pr.get('risk_score', 0))
                    if risk_score >= 7.0:
                        daily_metrics[author][merged_date]['high_risk_prs'] += 1
                    
                    # Count features (only for merged PRs)
                    if pr.get('feature'):
                        daily_metrics[author][merged_date]['features_merged'] += 1
            
            # Process file data for lines changed
            for file_change in file_data:
                author = file_change.get('author_name', '').strip()
                if not author:
                    continue
                
                merged_date = datetime.fromtimestamp(file_change.get('merged_at', 0)).date()
                additions = file_change.get('additions', 0)
                deletions = file_change.get('deletions', 0)
                
                daily_metrics[author][merged_date]['lines_changed'] += (additions + deletions)
            
            # Convert to list format for database insertion
            metrics_list = []
            for author, dates in daily_metrics.items():
                for day, metrics in dates.items():
                    metrics_list.append({
                        'username': author,
                        'repo_name': repo_name,
                        'day': day.isoformat(),
                        'prs_submitted': metrics['prs_submitted'],
                        'prs_merged': metrics['prs_merged'],
                        'lines_changed': metrics['lines_changed'],
                        'high_risk_prs': metrics['high_risk_prs'],
                        'features_merged': metrics['features_merged']
                    })
            
            logger.info(f"[SUCCESS] Calculated daily metrics for {len(metrics_list)} author-day combinations")
            
            # Debug: Show some sample data
            if metrics_list:
                logger.info(f"[DEBUG] Sample daily metrics: {metrics_list[:3]}")
            else:
                logger.warning(f"[WARNING] No daily metrics generated for {repo_name}")
                logger.info(f"[DEBUG] PR data count: {len(pr_data)}")
                logger.info(f"[DEBUG] File data count: {len(file_data)}")
                if pr_data:
                    logger.info(f"[DEBUG] Sample PR: {pr_data[0]}")
            
            return metrics_list
            
        except Exception as e:
            logger.error(f"[ERROR] Error calculating daily metrics for {repo_name}: {e}")
            return []
    
    def calculate_window_metrics(self, repo_name: str, daily_metrics: List[Dict], 
                               window_days: int, start_date: date, end_date: date) -> List[Dict]:
        """Calculate windowed metrics (7/14/30/90 days) for each author"""
        try:
            # Group daily metrics by author
            author_daily = defaultdict(list)
            for metric in daily_metrics:
                author_daily[metric['username']].append(metric)
            
            window_metrics = []
            
            for author, daily_list in author_daily.items():
                # Filter to window period
                window_daily = [
                    d for d in daily_list 
                    if start_date <= datetime.strptime(d['day'], '%Y-%m-%d').date() <= end_date
                ]
                
                if not window_daily:
                    continue
                
                # Aggregate metrics
                total_prs_submitted = sum(d['prs_submitted'] for d in window_daily)
                total_prs_merged = sum(d['prs_merged'] for d in window_daily)
                total_high_risk_prs = sum(d['high_risk_prs'] for d in window_daily)
                total_lines_changed = sum(d['lines_changed'] for d in window_daily)
                
                # Calculate high risk rate
                high_risk_rate = (total_high_risk_prs / total_prs_merged * 100) if total_prs_merged > 0 else 0
                
                window_metrics.append({
                    'username': author,
                    'repo_name': repo_name,
                    'window_days': window_days,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'prs_submitted': total_prs_submitted,
                    'prs_merged': total_prs_merged,
                    'high_risk_prs': total_high_risk_prs,
                    'high_risk_rate': round(high_risk_rate, 2),
                    'lines_changed': total_lines_changed,
                    'ownership_low_risk_prs': 0  # Placeholder for future metric
                })
            
            logger.info(f"[SUCCESS] Calculated window metrics for {len(window_metrics)} authors")
            return window_metrics
            
        except Exception as e:
            logger.error(f"[ERROR] Error calculating window metrics for {repo_name}: {e}")
            return []
    
    def calculate_file_ownership(self, repo_name: str, file_data: List[Dict], 
                               window_days: int, start_date: date, end_date: date) -> List[Dict]:
        """Calculate file ownership percentages for each author"""
        try:
            # Filter file data to window period
            start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp())
            end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp())
            
            window_files = [
                f for f in file_data 
                if start_timestamp <= f.get('merged_at', 0) <= end_timestamp
            ]
            
            # Group by file and calculate ownership
            file_ownership = defaultdict(lambda: defaultdict(int))
            file_paths = {}
            file_last_touched = {}
            
            for file_change in window_files:
                file_id = file_change.get('file_id', '')
                file_path = file_change.get('file_path', '')
                author = file_change.get('author_name', '').strip()
                additions = file_change.get('additions', 0)
                deletions = file_change.get('deletions', 0)
                merged_at = file_change.get('merged_at', 0)
                
                if not file_id or not author:
                    continue
                
                lines_changed = additions + deletions
                file_ownership[file_id][author] += lines_changed
                file_paths[file_id] = file_path
                
                # Track last touched time
                if file_id not in file_last_touched or merged_at > file_last_touched[file_id]:
                    file_last_touched[file_id] = merged_at
            
            # Calculate ownership percentages
            ownership_data = []
            for file_id, author_lines in file_ownership.items():
                total_lines = sum(author_lines.values())
                if total_lines == 0:
                    continue
                
                for author, lines in author_lines.items():
                    ownership_pct = (lines / total_lines) * 100
                    
                    ownership_data.append({
                        'username': author,
                        'repo_name': repo_name,
                        'window_days': window_days,
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
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
                          window_days: int, start_date: date, end_date: date) -> List[Dict]:
        """Process PR features and create author PR window data"""
        try:
            # Filter PRs to window period and merged status
            start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp())
            end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp())
            
            window_prs = [
                pr for pr in pr_data 
                if pr.get('is_merged') and 
                start_timestamp <= pr.get('merged_at', 0) <= end_timestamp
            ]
            
            pr_window_data = []
            
            for pr in window_prs:
                author = pr.get('author_name', '').strip()
                if not author:
                    continue
                
                # Determine feature classification
                feature_rule = 'excluded'
                feature_confidence = 0.0
                
                if pr.get('feature'):
                    feature_rule = 'title-allow'
                    feature_confidence = 0.8
                elif 'feature' in pr.get('title', '').lower():
                    feature_rule = 'title-allow'
                    feature_confidence = 0.6
                elif float(pr.get('risk_score', 0)) < 3.0:  # Low risk PRs might be features
                    feature_rule = 'unlabeled-include'
                    feature_confidence = 0.3
                
                pr_window_data.append({
                    'username': author,
                    'repo_name': repo_name,
                    'window_days': window_days,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'pr_number': pr.get('pr_number', 0),
                    'title': pr.get('title', ''),
                    'pr_summary': pr.get('pr_summary', ''),
                    'merged_at': datetime.fromtimestamp(pr.get('merged_at', 0)).isoformat(),
                    'risk_score': round(float(pr.get('risk_score', 0)), 2),
                    'high_risk': float(pr.get('risk_score', 0)) >= 7.0,
                    'feature_rule': feature_rule,
                    'feature_confidence': round(float(feature_confidence), 2)
                })
            
            logger.info(f"[SUCCESS] Processed {len(pr_window_data)} PRs for feature analysis")
            return pr_window_data
            
        except Exception as e:
            logger.error(f"[ERROR] Error processing PR features for {repo_name}: {e}")
            return []
    
    def upsert_daily_metrics(self, metrics: List[Dict]):
        """Upsert daily metrics to Supabase"""
        try:
            if not metrics:
                return
            
            if self.pg_conn and not self.pg_conn.closed:
                # Use direct PostgreSQL for bulk upsert
                try:
                    with self.pg_conn.cursor() as cursor:
                        for metric in metrics:
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
                except Exception as db_error:
                    if not self.pg_conn.closed:
                        self.pg_conn.rollback()
                    logger.error(f"[ERROR] Database error in upsert_daily_metrics: {db_error}")
                    # Fallback to Supabase client
                    for metric in metrics:
                        self.supabase_client.table('author_metrics_daily').upsert(metric).execute()
            else:
                # Use Supabase client
                for metric in metrics:
                    self.supabase_client.table('author_metrics_daily').upsert(metric).execute()
            
            logger.info(f"[SUCCESS] Upserted {len(metrics)} daily metrics")
            
        except Exception as e:
            logger.error(f"[ERROR] Error upserting daily metrics: {e}")
    
    def upsert_window_metrics(self, metrics: List[Dict]):
        """Upsert window metrics to Supabase"""
        try:
            if not metrics:
                return
            
            if self.pg_conn and not self.pg_conn.closed:
                # Use direct PostgreSQL for bulk upsert
                try:
                    with self.pg_conn.cursor() as cursor:
                        for metric in metrics:
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
                except Exception as db_error:
                    if not self.pg_conn.closed:
                        self.pg_conn.rollback()
                    logger.error(f"[ERROR] Database error in upsert_window_metrics: {db_error}")
                    # Fallback to Supabase client
                    for metric in metrics:
                        self.supabase_client.table('author_metrics_window').upsert(metric).execute()
            else:
                # Use Supabase client
                for metric in metrics:
                    self.supabase_client.table('author_metrics_window').upsert(metric).execute()
            
            logger.info(f"[SUCCESS] Upserted {len(metrics)} window metrics")
            
        except Exception as e:
            logger.error(f"[ERROR] Error upserting window metrics: {e}")
    
    def upsert_file_ownership(self, ownership_data: List[Dict]):
        """Upsert file ownership data to Supabase"""
        try:
            if not ownership_data:
                return
            
            if self.pg_conn and not self.pg_conn.closed:
                # Use direct PostgreSQL for bulk upsert
                try:
                    with self.pg_conn.cursor() as cursor:
                        for ownership in ownership_data:
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
                except Exception as db_error:
                    if not self.pg_conn.closed:
                        self.pg_conn.rollback()
                    logger.error(f"[ERROR] Database error in upsert_file_ownership: {db_error}")
                    # Fallback to Supabase client
                    for ownership in ownership_data:
                        self.supabase_client.table('author_file_ownership').upsert(ownership).execute()
            else:
                # Use Supabase client
                for ownership in ownership_data:
                    self.supabase_client.table('author_file_ownership').upsert(ownership).execute()
            
            logger.info(f"[SUCCESS] Upserted {len(ownership_data)} file ownership records")
            
        except Exception as e:
            logger.error(f"[ERROR] Error upserting file ownership: {e}")
    
    def upsert_pr_window_data(self, pr_data: List[Dict]):
        """Upsert PR window data to Supabase"""
        try:
            if not pr_data:
                return
            
            if self.pg_conn and not self.pg_conn.closed:
                # Use direct PostgreSQL for bulk upsert
                try:
                    with self.pg_conn.cursor() as cursor:
                        for pr in pr_data:
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
                except Exception as db_error:
                    if not self.pg_conn.closed:
                        self.pg_conn.rollback()
                    logger.error(f"[ERROR] Database error in upsert_pr_window_data: {db_error}")
                    # Fallback to Supabase client
                    for pr in pr_data:
                        self.supabase_client.table('author_prs_window').upsert(pr).execute()
            else:
                # Use Supabase client
                for pr in pr_data:
                    self.supabase_client.table('author_prs_window').upsert(pr).execute()
            
            logger.info(f"[SUCCESS] Upserted {len(pr_data)} PR window records")
            
        except Exception as e:
            logger.error(f"[ERROR] Error upserting PR window data: {e}")
    
    def process_repository(self, repo_name: str, window_days: int = 30, data_window_days: int = 365, force_refresh: bool = False):
        """Process a single repository and populate all tables"""
        try:
            logger.info(f"[PROCESSING] Processing repository: {repo_name}")
            
            # Calculate date range - use a larger window to get more data
            end_date = date.today()
            # Use the provided data window to capture historical data
            start_date = end_date - timedelta(days=data_window_days)
            
            logger.info(f"[DEBUG] Date range: {start_date} to {end_date} (data window: {data_window_days} days, metrics window: {window_days} days)")
            
            # Check if data already exists and skip if not forcing refresh
            if not force_refresh:
                existing_data = self.supabase_client.table('author_metrics_window').select('*').eq('repo_name', repo_name).eq('window_days', window_days).execute()
                if existing_data.data:
                    logger.info(f"[SKIPPING] Data already exists for {repo_name}, skipping (use --force-refresh to override)")
                    return
            
            # Get data from Milvus
            logger.info(f"[INFO] Fetching PR data for {repo_name}...")
            pr_data = self.get_pr_data_for_repo(repo_name, datetime.combine(start_date, datetime.min.time()), datetime.combine(end_date, datetime.max.time()))
            
            logger.info(f"[INFO] Fetching file data for {repo_name}...")
            file_data = self.get_file_data_for_repo(repo_name, datetime.combine(start_date, datetime.min.time()), datetime.combine(end_date, datetime.max.time()))
            
            if not pr_data:
                logger.warning(f"[WARNING] No PR data found for {repo_name}")
                return
            
            # Process authors
            logger.info(f"[AUTHORS] Processing authors for {repo_name}...")
            authors = self.process_authors(repo_name, pr_data, file_data)
            
            # Calculate daily metrics
            logger.info(f"[CALCULATING] Calculating daily metrics for {repo_name}...")
            daily_metrics = self.calculate_daily_metrics(repo_name, pr_data, file_data)
            self.upsert_daily_metrics(daily_metrics)
            
            # Calculate window metrics
            logger.info(f"[INFO] Calculating window metrics for {repo_name}...")
            window_metrics = self.calculate_window_metrics(repo_name, daily_metrics, window_days, start_date, end_date)
            self.upsert_window_metrics(window_metrics)
            
            # Calculate file ownership
            logger.info(f"[FILES] Calculating file ownership for {repo_name}...")
            ownership_data = self.calculate_file_ownership(repo_name, file_data, window_days, start_date, end_date)
            self.upsert_file_ownership(ownership_data)
            
            # Process PR features
            logger.info(f"[FEATURES] Processing PR features for {repo_name}...")
            pr_window_data = self.process_pr_features(repo_name, pr_data, window_days, start_date, end_date)
            self.upsert_pr_window_data(pr_window_data)
            
            logger.info(f"[SUCCESS] Successfully processed {repo_name}")
            
        except Exception as e:
            logger.error(f"[ERROR] Error processing repository {repo_name}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
    
    def process_all_repositories(self, window_days: int = 30, data_window_days: int = 365, force_refresh: bool = False):
        """Process all repositories"""
        try:
            repositories = self.get_all_repositories()
            
            if not repositories:
                logger.warning("[WARNING] No repositories found")
                return
            
            logger.info(f"[PROCESSING] Processing {len(repositories)} repositories...")
            
            for i, repo in enumerate(repositories, 1):
                logger.info(f"[INFO] Processing {i}/{len(repositories)}: {repo}")
                self.process_repository(repo, window_days, data_window_days, force_refresh)
                
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
    parser = argparse.ArgumentParser(description='Process Engineer Lens data from Milvus to Supabase')
    parser.add_argument('--repo', type=str, help='Specific repository to process')
    parser.add_argument('--window-days', type=int, default=30, choices=[7, 14, 30, 90], 
                       help='Metrics window size in days (default: 30)')
    parser.add_argument('--data-window-days', type=int, default=365, 
                       help='Data collection window in days (default: 365)')
    parser.add_argument('--force-refresh', action='store_true', 
                       help='Force refresh even if data already exists')
    
    args = parser.parse_args()
    
    try:
        processor = EngineerLensDataProcessor()
        
        if args.repo:
            # Process specific repository
            processor.process_repository(args.repo, args.window_days, args.data_window_days, args.force_refresh)
        else:
            # Process all repositories
            processor.process_all_repositories(args.window_days, args.data_window_days, args.force_refresh)
        
        processor.close()
        
    except Exception as e:
        logger.error(f"[ERROR] Fatal error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
