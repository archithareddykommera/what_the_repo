#!/usr/bin/env python3
"""
Script to load GitHub PR data into Milvus vector database.
Processes JSON data and creates embeddings for semantic search.
Loads data into two collections: pr_index_what_the_repo and file_changes_what_the_repo
"""

import os
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
import re
import time
import numpy as np
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
import openai
from openai import OpenAI

class MilvusPRLoader:
    def __init__(self, milvus_url: str = None, milvus_token: str = None):
        """
        Initialize Milvus PR Loader for Milvus/Zilliz Cloud
        
        Args:
            milvus_url (str): Milvus/Zilliz Cloud URL (e.g., "https://your-cluster.zillizcloud.com")
            milvus_token (str): Milvus/Zilliz Cloud API token
        """
        self.milvus_url = milvus_url or os.getenv('MILVUS_URL')
        self.milvus_token = milvus_token or os.getenv('MILVUS_TOKEN')
        self.embedding_dim = 1536  # text-embedding-ada-002 returns 1536 dimensions
        
        # Collection names
        self.pr_collection_name = 'pr_index_what_the_repo'
        self.file_collection_name = 'file_changes_what_the_repo'
        
        if not self.milvus_url or not self.milvus_token:
            raise ValueError("Milvus URL and token are required. Set MILVUS_URL and MILVUS_TOKEN environment variables.")
        
        # Initialize OpenAI client for embeddings
        self.openai_client = None
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if openai_api_key:
            try:
                # Use the newer OpenAI client
                self.openai_client = OpenAI(api_key=openai_api_key)
                print("[PASS] OpenAI client initialized successfully")
            except ImportError:
                # Fallback to older openai library
                openai.api_key = openai_api_key
                self.openai_client = openai
                print("[PASS] OpenAI client initialized (legacy mode)")
        else:
            print("[ERROR] OPENAI_API_KEY not found. Embeddings cannot be generated.")
            raise ValueError("OPENAI_API_KEY is required for embeddings")
        
        # Connect to Milvus
        self._connect_to_milvus()
        
    def _connect_to_milvus(self):
        """Connect to Milvus/Zilliz Cloud"""
        try:
            connections.connect(
                alias="default",
                uri=self.milvus_url,
                token=self.milvus_token
            )
            print(f"[PASS] Connected to Milvus at {self.milvus_url}")
        except Exception as e:
            print(f"[FAIL] Failed to connect to Milvus: {e}")
            raise
    
    def _create_pr_collection(self):
        """Create the PR index collection with the specified schema"""
        if utility.has_collection(self.pr_collection_name):
            print(f"Collection '{self.pr_collection_name}' already exists")
            return
        
        # Define fields for PR collection
        fields = [
            FieldSchema(name="primary_key", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
            FieldSchema(name="repo_id", dtype=DataType.INT64),
            FieldSchema(name="repo_name", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="pr_number", dtype=DataType.INT64),
            FieldSchema(name="pr_id", dtype=DataType.INT64),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="body", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="author_id", dtype=DataType.INT64),
            FieldSchema(name="author_name", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="created_at", dtype=DataType.INT64),
            FieldSchema(name="merged_at", dtype=DataType.INT64),
            FieldSchema(name="is_merged", dtype=DataType.BOOL),
            FieldSchema(name="labels_full", dtype=DataType.JSON),
            FieldSchema(name="additions", dtype=DataType.INT32),
            FieldSchema(name="is_closed", dtype=DataType.BOOL),
            FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="deletions", dtype=DataType.INT32),
            FieldSchema(name="changed_files", dtype=DataType.INT32),
            FieldSchema(name="feature", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="pr_summary", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="risk_score", dtype=DataType.FLOAT),
            FieldSchema(name="risk_band", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="high_risk", dtype=DataType.BOOL),
            FieldSchema(name="risk_reasons", dtype=DataType.JSON)
        ]
        
        schema = CollectionSchema(fields, description="GitHub PR index data with embeddings")
        collection = Collection(self.pr_collection_name, schema)
        
        # Create index on vector field
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="vector", index_params=index_params)
        
        print(f"[PASS] Created PR collection '{self.pr_collection_name}' with index")
    
    def _create_file_collection(self):
        """Create the file changes collection with the specified schema"""
        if utility.has_collection(self.file_collection_name):
            print(f"Collection '{self.file_collection_name}' already exists")
            return
        
        # Define fields for file collection
        fields = [
            FieldSchema(name="primary_key", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
            FieldSchema(name="repo_id", dtype=DataType.INT64),
            FieldSchema(name="repo_name", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="pr_number", dtype=DataType.INT64),
            FieldSchema(name="pr_id", dtype=DataType.INT64),
            FieldSchema(name="author_id", dtype=DataType.INT64),
            FieldSchema(name="author_name", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="merged_at", dtype=DataType.INT64),
            FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="file_status", dtype=DataType.VARCHAR, max_length=16),
            FieldSchema(name="language", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="additions", dtype=DataType.INT32),
            FieldSchema(name="deletions", dtype=DataType.INT32),
            FieldSchema(name="lines_changed", dtype=DataType.INT32),
            FieldSchema(name="is_binary", dtype=DataType.BOOL),
            FieldSchema(name="is_config_file", dtype=DataType.BOOL),
            FieldSchema(name="is_documentation", dtype=DataType.BOOL),
            FieldSchema(name="is_test_file", dtype=DataType.BOOL),
            FieldSchema(name="is_source_code", dtype=DataType.BOOL),
            FieldSchema(name="patch", dtype=DataType.VARCHAR, max_length=32768),
            FieldSchema(name="ai_summary", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="risk_score_file", dtype=DataType.FLOAT),
            FieldSchema(name="high_risk_flag", dtype=DataType.BOOL),
            FieldSchema(name="file_risk_reasons", dtype=DataType.JSON)
        ]
        
        schema = CollectionSchema(fields, description="GitHub file changes data with embeddings")
        collection = Collection(self.file_collection_name, schema)
        
        # Create index on vector field
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="vector", index_params=index_params)
        
        print(f"[PASS] Created file collection '{self.file_collection_name}' with index")
    
    def _validate_and_format_vector(self, vector: List[float]) -> List[float]:
        """
        Validate and format vector to ensure it's float32 with correct dimension
        
        Args:
            vector (List[float]): Input vector
            
        Returns:
            List[float]: Validated and formatted vector
        """
        # Convert to numpy array and ensure float32 type
        vector_data = np.array(vector, dtype=np.float32)
        
        # Handle dimension mismatch
        if vector_data.shape[0] != self.embedding_dim:
            if vector_data.shape[0] > self.embedding_dim:
                # Truncate if too long
                print(f"[WARN] Truncating vector from {vector_data.shape[0]} to {self.embedding_dim} dimensions")
                vector_data = vector_data[:self.embedding_dim]
            else:
                # Pad with zeros if too short
                print(f"[WARN] Padding vector from {vector_data.shape[0]} to {self.embedding_dim} dimensions")
                padding = np.zeros(self.embedding_dim - vector_data.shape[0], dtype=np.float32)
                vector_data = np.concatenate([vector_data, padding])
        
        return vector_data.tolist()
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI API
        
        Args:
            text (str): Text to embed
            
        Returns:
            List[float]: Embedding vector
        """
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized")
        
        # Truncate text to reasonable length for embedding
        truncated_text = text[:8000] if len(text) > 8000 else text
        
        try:
            # Try newer OpenAI client first
            if hasattr(self.openai_client, 'embeddings'):
                response = self.openai_client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=truncated_text
                )
                embedding = response.data[0].embedding
            else:
                # Fallback to older openai library
                response = self.openai_client.Embedding.create(
                    model="text-embedding-ada-002",
                    input=truncated_text
                )
                embedding = response['data'][0]['embedding']
            
            # Validate and format the vector
            return self._validate_and_format_vector(embedding)
        except Exception as e:
            print(f"Error generating embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * self.embedding_dim
    
    def _parse_datetime(self, dt_str: Optional[str]) -> int:
        """
        Convert datetime string to UNIX epoch seconds
        
        Args:
            dt_str (Optional[str]): ISO datetime string
            
        Returns:
            int: UNIX epoch seconds
        """
        if not dt_str:
            return 0
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return int(dt.timestamp())
        except Exception:
            return 0
    
    def _prepare_pr_data(self, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare PR-level data for insertion
        
        Args:
            pr_data (Dict[str, Any]): PR data from JSON
            
        Returns:
            Dict[str, Any]: Formatted PR data for Milvus
        """
        # Extract basic PR info
        repo_id = pr_data.get('repo_id', 0)
        repo_name = pr_data.get('repo_name', '')
        pr_number = pr_data.get('pr_number', 0)
        pr_id = pr_data.get('pr_id', 0)
        title = pr_data.get('title', '')
        body = pr_data.get('body', '')
        author_id = pr_data.get('user', {}).get('id', 0)
        author_name = pr_data.get('user', {}).get('login', '')
        created_at = self._parse_datetime(pr_data.get('created_at'))
        merged_at = self._parse_datetime(pr_data.get('merged_at'))
        is_merged = pr_data.get('is_merged', False)
        is_closed = pr_data.get('is_closed', False)
        status = pr_data.get('state', 'unknown')
        additions = pr_data.get('additions', 0)
        deletions = pr_data.get('deletions', 0)
        changed_files = pr_data.get('changed_files', 0)
        feature = pr_data.get('feature', '') or ''  # Ensure feature is always a string
        pr_summary = pr_data.get('pr_summary', '')
        
        # Extract labels with null safety
        labels = pr_data.get('labels', []) or []
        labels_full = []
        for label in labels:
            if label and isinstance(label, dict):
                labels_full.append({
                    'name': label.get('name', '') or '',
                    'color': label.get('color', '') or ''
                })
        
        # Extract risk assessment with null safety
        pr_risk_assessment = pr_data.get('pr_risk_assessment', {}) or {}
        risk_score = pr_risk_assessment.get('risk_score', 0.0) if pr_risk_assessment else 0.0
        risk_band = pr_risk_assessment.get('risk_band', 'low') if pr_risk_assessment else 'low'
        high_risk = pr_risk_assessment.get('high_risk', False) if pr_risk_assessment else False
        risk_reasons = pr_risk_assessment.get('risk_reasons', []) if pr_risk_assessment else []
        
        # Generate embedding for PR content
        # Get top 10 file paths from this PR
        files = pr_data.get('files', [])
        top_files = [f.get('filename', '') for f in files[:10]]
        file_paths_str = ', '.join(top_files)
        
        # Handle None values safely
        title = title or ''
        body = body or ''
        pr_summary = pr_summary or ''
        
        # Trim body to fit within Milvus VARCHAR limit (8192 chars)
        # Leave some buffer for safety
        max_body_length = 8000
        trimmed_body_for_embedding = body[:2000] if len(body) > 2000 else body
        trimmed_body_for_record = body[:max_body_length] if len(body) > max_body_length else body
        
        pr_content = f"PR #{pr_number}: {title}\n{trimmed_body_for_embedding}\nSummary: {pr_summary}\nFiles: {file_paths_str}"
        if len(pr_content) > 8000:
            pr_content = pr_content[:8000]
        
        vector = self._generate_embedding(pr_content)
        
        return {
            'vector': vector,
            'repo_id': repo_id,
            'repo_name': repo_name,
            'pr_number': pr_number,
            'pr_id': pr_id,
            'title': title,
            'body': trimmed_body_for_record,  # Use the trimmed body for the record
            'author_id': author_id,
            'author_name': author_name,
            'created_at': created_at,
            'merged_at': merged_at,
            'is_merged': is_merged,
            'labels_full': labels_full,
            'additions': additions,
            'is_closed': is_closed,
            'status': status,
            'deletions': deletions,
            'changed_files': changed_files,
            'feature': feature,
            'pr_summary': pr_summary,
            'risk_score': risk_score,
            'risk_band': risk_band,
            'high_risk': high_risk,
            'risk_reasons': risk_reasons
        }
    
    def _prepare_file_data(self, pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Prepare file-level data for insertion
        
        Args:
            pr_data (Dict[str, Any]): PR data from JSON
            
        Returns:
            List[Dict[str, Any]]: List of formatted file data for Milvus
        """
        file_records = []
        
        # Extract common PR info with null safety
        repo_id = pr_data.get('repo_id', 0)
        repo_name = pr_data.get('repo_name', '') or ''
        pr_number = pr_data.get('pr_number', 0)
        pr_id = pr_data.get('pr_id', 0)
        
        # Handle user object safely
        user_obj = pr_data.get('user', {}) or {}
        author_id = user_obj.get('id', 0) if user_obj else 0
        author_name = user_obj.get('login', '') or '' if user_obj else ''
        
        merged_at = self._parse_datetime(pr_data.get('merged_at'))
        
        # Process each file with null safety
        files = pr_data.get('files', []) or []
        for file_info in files:
            if not file_info or not isinstance(file_info, dict):
                continue
            file_id = file_info.get('filename', '')
            file_status = file_info.get('status', '')
            language = file_info.get('language', 'Unknown')
            additions = file_info.get('additions', 0)
            deletions = file_info.get('deletions', 0)
            lines_changed = file_info.get('changes', 0)
            is_binary = file_info.get('is_binary', False)
            is_config_file = file_info.get('is_config_file', False)
            is_documentation = file_info.get('is_documentation', False)
            is_test_file = file_info.get('is_test_file', False)
            is_source_code = file_info.get('is_source_code', False)
            patch = file_info.get('patch', '')
            ai_summary = file_info.get('ai_summary', '')
            
            # Extract risk assessment with null safety
            risk_assessment = file_info.get('risk_assessment', {}) or {}
            risk_score_file = risk_assessment.get('risk_score_file', 0.0) if risk_assessment else 0.0
            high_risk_flag = risk_assessment.get('high_risk_flag', False) if risk_assessment else False
            file_risk_reasons = risk_assessment.get('reasons', []) if risk_assessment else []
            
            # Generate embedding for file content
            # Get PR title for context
            pr_title = pr_data.get('title', '') or ''
            
            # Handle None values safely
            file_id = file_id or ''
            language = language or 'Unknown'
            file_status = file_status or ''
            ai_summary = ai_summary or ''
            patch = patch or ''
            
            # Trim patch to fit within Milvus VARCHAR limit (32768 chars)
            # Leave some buffer for safety
            max_patch_length = 32000
            trimmed_patch = patch[:max_patch_length] if len(patch) > max_patch_length else patch
            
            file_content = f"PATH: {file_id}  LANG: {language}  STATUS: {file_status}\nPR #{pr_number} — {pr_title}\nFILE SUMMARY: {ai_summary}\nDIFF (trimmed): {trimmed_patch}"
            if len(file_content) > 8000:
                file_content = file_content[:8000]
            
            vector = self._generate_embedding(file_content)
            
            file_records.append({
                'vector': vector,
                'repo_id': repo_id,
                'repo_name': repo_name,
                'pr_number': pr_number,
                'pr_id': pr_id,
                'author_id': author_id,
                'author_name': author_name,
                'merged_at': merged_at,
                'file_id': file_id,
                'file_status': file_status,
                'language': language,
                'additions': additions,
                'deletions': deletions,
                'lines_changed': lines_changed,
                'is_binary': is_binary,
                'is_config_file': is_config_file,
                'is_documentation': is_documentation,
                'is_test_file': is_test_file,
                'is_source_code': is_source_code,
                'patch': trimmed_patch,  # Use the trimmed patch for the record
                'ai_summary': ai_summary,
                'risk_score_file': risk_score_file,
                'high_risk_flag': high_risk_flag,
                'file_risk_reasons': file_risk_reasons
            })
        
        return file_records
    
    def load_data(self, json_file_path: str, batch_size: int = 50):
        """
        Load PR data from JSON file into both Milvus collections
        
        Args:
            json_file_path (str): Path to JSON file with PR data
            batch_size (int): Number of rows to insert in each batch
        """
        # Create collections if they don't exist
        self._create_pr_collection()
        self._create_file_collection()
        
        # Load JSON data
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        prs = data.get('pull_requests', [])
        print(f"Processing {len(prs)} pull requests...")
        
        # Get collections
        pr_collection = Collection(self.pr_collection_name)
        file_collection = Collection(self.file_collection_name)
        pr_collection.load()
        file_collection.load()
        
        total_pr_rows = 0
        total_file_rows = 0
        pr_batch_data = []
        file_batch_data = []
        
        for i, pr in enumerate(prs):
            print(f"Processing PR #{pr.get('pr_number', i+1)} ({i+1}/{len(prs)})")
            
            try:
                # Prepare PR data
                pr_record = self._prepare_pr_data(pr)
                pr_batch_data.append(pr_record)
                total_pr_rows += 1
                
                # Prepare file data
                file_records = self._prepare_file_data(pr)
                file_batch_data.extend(file_records)
                total_file_rows += len(file_records)
                
                # Insert batches when they reach the size limit
                if len(pr_batch_data) >= batch_size:
                    self._insert_pr_batch(pr_collection, pr_batch_data)
                    pr_batch_data = []
                
                if len(file_batch_data) >= batch_size:
                    self._insert_file_batch(file_collection, file_batch_data)
                    file_batch_data = []
                
                # Rate limiting for API calls
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error processing PR #{pr.get('pr_number', i+1)}: {e}")
                continue
        
        # Insert remaining batches
        if pr_batch_data:
            self._insert_pr_batch(pr_collection, pr_batch_data)
        
        if file_batch_data:
            self._insert_file_batch(file_collection, file_batch_data)
        
        print(f"[PASS] Successfully loaded {total_pr_rows} PR rows into '{self.pr_collection_name}'")
        print(f"[PASS] Successfully loaded {total_file_rows} file rows into '{self.file_collection_name}'")
        print(f"Both collections are ready for queries")
    
    def _insert_pr_batch(self, collection: Collection, batch_data: List[Dict[str, Any]]):
        """
        Insert a batch of PR data into Milvus collection
        
        Args:
            collection (Collection): Milvus collection
            batch_data (List[Dict[str, Any]]): Batch of PR data
        """
        try:
            for record in batch_data:
                # Validate and format the vector
                validated_vector = self._validate_and_format_vector(record['vector'])
                record['vector'] = validated_vector
                
                # Insert single record
                collection.insert([record])
            
            print(f"Inserted batch of {len(batch_data)} PR rows")
            
        except Exception as e:
            print(f"Error inserting PR batch: {e}")
            raise
    
    def _insert_file_batch(self, collection: Collection, batch_data: List[Dict[str, Any]]):
        """
        Insert a batch of file data into Milvus collection
        
        Args:
            collection (Collection): Milvus collection
            batch_data (List[Dict[str, Any]]): Batch of file data
        """
        try:
            for record in batch_data:
                # Validate and format the vector
                validated_vector = self._validate_and_format_vector(record['vector'])
                record['vector'] = validated_vector
                
                # Insert single record
                collection.insert([record])
            
            print(f"Inserted batch of {len(batch_data)} file rows")
            
        except Exception as e:
            print(f"Error inserting file batch: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Load GitHub PR data into Milvus collections')
    parser.add_argument('json_file', help='Path to JSON file with PR data')
    parser.add_argument('--url', help='Milvus URL (or set MILVUS_URL env var)')
    parser.add_argument('--token', help='Milvus API token (or set MILVUS_TOKEN env var)')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for insertion (default: 50)')
    
    args = parser.parse_args()
    
    # Check if JSON file exists
    if not os.path.exists(args.json_file):
        print(f"[ERROR] JSON file not found: {args.json_file}")
        return
    
    try:
        # Initialize loader
        loader = MilvusPRLoader(
            milvus_url=args.url,
            milvus_token=args.token
        )
        
        # Load data
        loader.load_data(args.json_file, args.batch_size)
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")

if __name__ == "__main__":
    main() 